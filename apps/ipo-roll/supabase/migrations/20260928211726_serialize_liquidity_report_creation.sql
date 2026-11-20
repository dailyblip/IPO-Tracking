-- Serialize every report write for an account before checking rolling quotas.
-- Updating one private mutex row also makes stale REPEATABLE READ / SERIALIZABLE
-- transactions fail with 40001, rather than using an old count after a lock wait.
-- No existing report, research fact, source right or public RPC grant is changed.
create table app.liquidity_report_accounts (
 user_id uuid primary key references auth.users(id) on delete cascade,
 touched_at timestamptz not null default clock_timestamp()
);
alter table app.liquidity_report_accounts enable row level security;
revoke all on app.liquidity_report_accounts from public,anon,authenticated;

-- Narrow internal definer: callers can lock only auth.uid(), never a supplied
-- account. It returns no private data and cannot edit reports or research.
create function app.lock_liquidity_report_account() returns void
language plpgsql volatile security definer set search_path='' as $$
declare account_id uuid:=auth.uid();
begin
 if account_id is null or not app.has_access() then raise insufficient_privilege; end if;
 insert into app.liquidity_report_accounts(user_id,touched_at)
 values(account_id,clock_timestamp())
 on conflict(user_id) do update set touched_at=excluded.touched_at;
end $$;
revoke all on function app.lock_liquidity_report_account() from public,anon,authenticated;
grant execute on function app.lock_liquidity_report_account() to authenticated;

-- This non-callable trigger counts only the requesting account, including its
-- now-hidden reports. Research/report RLS cannot accidentally reset a quota.
create function app.enforce_liquidity_report_quota() returns trigger
language plpgsql volatile security definer set search_path='' as $$
declare account_id uuid:=auth.uid(); quota_time timestamptz;
begin
 perform app.lock_liquidity_report_account();
 quota_time:=clock_timestamp();
 if (select count(*) from app.liquidity_reports
     where user_id=account_id and created_at>=quota_time-interval '24 hours')>=100 then
  raise exception 'Liquidity report daily quota reached' using errcode='54000';
 end if;
 if (select count(*) from app.liquidity_reports
     where user_id=account_id and offering_id=new.offering_id and person_id=new.person_id
       and created_at>=quota_time-interval '24 hours')>=10 then
  raise exception 'Liquidity report subject quota reached' using errcode='54000';
 end if;
 return new;
end $$;
revoke all on function app.enforce_liquidity_report_quota() from public,anon,authenticated;
-- BEFORE triggers run alphabetically: quota/serialization precedes the expensive
-- invoker snapshot trigger for RPC, bulk and direct Data API insertion alike.
create trigger liquidity_report_quota before insert on app.liquidity_reports
for each row execute function app.enforce_liquidity_report_quota();
create index liquidity_reports_owner_created on app.liquidity_reports(user_id,created_at);

create or replace function app.prepare_liquidity_report() returns trigger language plpgsql security invoker set search_path='' as $$
declare d jsonb; p jsonb; positions jsonb; snapshot_time timestamptz:=clock_timestamp();
begin
 if auth.uid() is null or not app.has_access() then raise insufficient_privilege; end if;
 d:=public.ipo_roll_detail(new.offering_id);
 select x into strict p from jsonb_array_elements(d->'people') x where x->>'id'=new.person_id::text;
 new.id:=gen_random_uuid(); new.user_id:=auth.uid(); new.created_at:=snapshot_time;
 select coalesce(jsonb_agg(jsonb_build_object(
  'id',o.id,'shareClass',o.share_class,'shares',case when o.quantity_kind='beneficial_total' then null else o.shares end,
  'reportedTotal',o.shares,'quantityKind',o.quantity_kind,'components',research.ownership_components_json(o.id),
  'positionBasis',o.position_basis,'filingAccession',f.accession,
  'documentHash',(select doc.content_sha256 from evidence.spans sp join evidence.documents doc on doc.id=sp.document_id where sp.id=o.evidence_id),
  'filingDate',f.filed_on,'holdingsAsOf',o.holdings_as_of,
  'source',evidence.source_json(o.evidence_id),
  'reportedHolder',jsonb_build_object('id',holder.id,'name',holder.name,'kind',holder.kind),
  'attribution',case when oa.person_id is null then null else jsonb_build_object(
    'kind',oa.kind,'description',oa.description,'source',evidence.source_json(oa.evidence_id)) end,
  'category',case
   when o.quantity_kind='beneficial_total' or o.party_id<>new.person_id then 'unknown'
   when a.id is null or a.assessed_on>current_date or a.valid_through<current_date then 'unknown'
   when a.classification='liquid' and (d->>'stage'<>'Priced' or not a.current_position_confirmed or not a.personal_interest_confirmed or coalesce(a.lockup_end>current_date,false)) then 'unknown'
   when a.classification='future' and (a.lockup_end is null or a.lockup_end<=current_date) then 'unknown'
   else a.classification end,
  'assessmentDate',a.assessed_on,'validThrough',a.valid_through,
  'lockupStart',a.lockup_start,'lockupEnd',a.lockup_end,'restrictionTimeline',research.lockup_timeline_json(o.id),
  'explanation',coalesce(a.explanation,'Ownership evidence alone does not establish liquidity. Restriction and footnote review is incomplete.'),
  'conditions',coalesce(a.conditions,''),
  'evidence',coalesce((select jsonb_agg(evidence.source_json(e)) from unnest(a.evidence_ids) e),'[]'::jsonb),
  'marketValue',null,'valuationReason','No licensed, security-matched quote and reconciled position are available.'
 ) order by o.position_basis,o.share_class,o.id),'[]'::jsonb) into positions
 from research.ownerships o join research.filings f on f.id=o.filing_id
 join research.parties holder on holder.id=o.party_id
 left join research.ownership_attributions oa on oa.ownership_id=o.id and oa.person_id=new.person_id and oa.approved
 left join research.liquidity_assessments a on a.ownership_id=o.id
 where o.offering_id=new.offering_id and o.approved
 and (o.party_id=new.person_id or oa.person_id is not null)
 and evidence.source_json(o.evidence_id) is not null
 and (oa.person_id is null or evidence.source_json(oa.evidence_id) is not null);
 new.report:=jsonb_build_object(
  'id',new.id,'version','liquidity/1.6','asOf',new.created_at,'method','Evidence review; no AI inference',
  'offeringId',new.offering_id,'personId',new.person_id,'company',d->>'company','person',p->>'name',
  'relationship',p->>'relationship','relationshipSource',p->'source','roles',p->'roles','positions',positions,
  'notice','Static private snapshot. Reported holders, beneficiary entitlement and control authority remain distinct. Unknown is not zero. Future liquidity is conditional; lock-up expiry alone does not establish saleability. Market value is not cash proceeds.'
 );
 return new;
exception when no_data_found then
 raise exception 'Subject not available' using errcode='P0002';
end $$;

revoke all on function app.prepare_liquidity_report() from public,anon,authenticated;

-- Take the same account mutex before idempotency/latest-version reads. Reopen
-- and replay return before INSERT, so reaching quota does not block reading.
create or replace function public.ipo_roll_request_liquidity(p_offering uuid,p_person uuid,p_request uuid,p_previous uuid default null) returns jsonb language plpgsql security invoker set search_path='' as $$
declare existing app.liquidity_reports; latest app.liquidity_reports;
begin
 if auth.uid() is null or not app.has_access() then raise insufficient_privilege; end if;
 perform app.lock_liquidity_report_account();
 select * into existing from app.liquidity_reports where user_id=auth.uid() and request_id=p_request;
 if found then
  if existing.offering_id<>p_offering or existing.person_id<>p_person then raise exception 'Request already used' using errcode='22023'; end if;
  return existing.report;
 end if;
 select * into latest from app.liquidity_reports where user_id=auth.uid() and offering_id=p_offering and person_id=p_person order by created_at desc,id desc limit 1;
 if found and (p_previous is null or latest.id<>p_previous) then return latest.report; end if;
 if latest.id is null and p_previous is not null then raise exception 'Report not available' using errcode='P0002'; end if;
 insert into app.liquidity_reports(offering_id,person_id,request_id) values(p_offering,p_person,p_request) returning * into existing;
 return existing.report;
end $$;
