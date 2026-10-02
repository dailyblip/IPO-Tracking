-- Reviewed facts are shared research; generated snapshots belong to one account.
create table research.liquidity_assessments (
 id uuid primary key default gen_random_uuid(),
 ownership_id uuid not null unique references research.ownerships(id),
 reviewed boolean not null default false,
 assessed_on date not null,
 valid_through date not null check(valid_through >= assessed_on),
 classification text not null check(classification in ('liquid','future','illiquid','unknown')),
 current_position_confirmed boolean not null default false,
 personal_interest_confirmed boolean not null default false,
 lockup_start date,
 lockup_end date,
 explanation text not null check(length(explanation) between 1 and 12000),
 conditions text not null default '',
 evidence_ids uuid[] not null check(cardinality(evidence_ids) > 0),
 check(lockup_start is null or lockup_end is null or lockup_end >= lockup_start)
);
alter table research.liquidity_assessments enable row level security;
revoke all on research.liquidity_assessments from public,anon,authenticated;
grant select on research.liquidity_assessments to authenticated;
create policy liquidity_assessment_read on research.liquidity_assessments for select to authenticated using (
 (select app.has_access()) and reviewed
 and exists(select 1 from research.ownerships o where o.id=ownership_id and o.approved)
 and not exists(select 1 from unnest(evidence_ids) e where evidence.source_json(e) is null)
);

create table app.liquidity_reports (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
 offering_id uuid not null references research.offerings(id),
 person_id uuid not null references research.people(id),
 request_id uuid not null,
 created_at timestamptz not null default now(),
 report jsonb not null default '{}'::jsonb,
 unique(user_id,request_id)
);
create index liquidity_reports_owner_subject on app.liquidity_reports(user_id,offering_id,person_id,created_at desc,id);
create index liquidity_reports_offering on app.liquidity_reports(offering_id);
create index liquidity_reports_person on app.liquidity_reports(person_id);
alter table app.liquidity_reports enable row level security;
revoke all on app.liquidity_reports from public,anon,authenticated;
grant select on app.liquidity_reports to authenticated;
-- Callers submit subject and idempotency key only, never report contents or owner.
grant insert(offering_id,person_id,request_id) on app.liquidity_reports to authenticated;
create policy liquidity_report_read on app.liquidity_reports for select to authenticated using (
 user_id=(select auth.uid()) and (select app.has_access())
 and exists(select 1 from research.offerings o where o.id=offering_id)
);
create policy liquidity_report_insert on app.liquidity_reports for insert to authenticated with check (
 user_id=(select auth.uid()) and (select app.has_access())
 and exists(select 1 from research.offerings o where o.id=offering_id)
);

-- Invoker trigger builds authoritative snapshots even for a direct insert.
create function app.prepare_liquidity_report() returns trigger language plpgsql security invoker set search_path='' as $$
declare d jsonb; p jsonb; positions jsonb;
begin
 if auth.uid() is null or not app.has_access() then raise insufficient_privilege; end if;
 d:=public.ipo_roll_detail(new.offering_id);
 select x into p from jsonb_array_elements(d->'people') x where x->>'id'=new.person_id::text;
 if p is null then raise exception 'Subject not available' using errcode='P0002'; end if;
 new.id:=gen_random_uuid(); new.user_id:=auth.uid(); new.created_at:=clock_timestamp();
 select coalesce(jsonb_agg(jsonb_build_object(
  'id',o.id,'shareClass',o.share_class,'shares',o.shares,'positionBasis',o.position_basis,
  'filingAccession',f.accession,'documentHash',(select doc.content_sha256 from evidence.spans sp join evidence.documents doc on doc.id=sp.document_id where sp.id=o.evidence_id),'holdingsDate',f.filed_on,'source',evidence.source_json(o.evidence_id),
  'category',case
   when a.id is null or a.assessed_on>current_date or a.valid_through<current_date then 'unknown'
   when a.classification='liquid' and (d->>'stage'<>'Priced' or not a.current_position_confirmed or not a.personal_interest_confirmed or coalesce(a.lockup_end>current_date,false)) then 'unknown'
   when a.classification='future' and (a.lockup_end is null or a.lockup_end<=current_date) then 'unknown'
   else a.classification end,
  'assessmentDate',a.assessed_on,'validThrough',a.valid_through,
  'lockupStart',a.lockup_start,'lockupEnd',a.lockup_end,
  'explanation',coalesce(a.explanation,'Ownership evidence alone does not establish liquidity. Restriction and footnote review is incomplete.'),
  'conditions',coalesce(a.conditions,''),
  'evidence',coalesce((select jsonb_agg(evidence.source_json(e)) from unnest(a.evidence_ids) e),'[]'::jsonb),
  'marketValue',null,'valuationReason','No licensed, security-matched quote and reconciled position are available.'
 ) order by o.id),'[]'::jsonb) into positions
 from research.ownerships o join research.filings f on f.id=o.filing_id
 left join research.liquidity_assessments a on a.ownership_id=o.id
 where o.offering_id=new.offering_id and o.party_id=new.person_id and o.approved and evidence.source_json(o.evidence_id) is not null;
 new.report:=jsonb_build_object(
  'id',new.id,'version','liquidity/1','asOf',new.created_at,'method','Evidence review; no AI inference',
  'offeringId',new.offering_id,'personId',new.person_id,'company',d->>'company','person',p->>'name',
  'relationship',p->>'relationship','relationshipSource',p->'source','positions',positions,
  'notice','Static private snapshot. Unknown is not zero. Future liquidity is conditional; lock-up expiry alone does not establish saleability. Market value is not cash proceeds.'
 );
 return new;
end $$;
revoke all on function app.prepare_liquidity_report() from public,anon,authenticated;
create trigger liquidity_report_snapshot before insert on app.liquidity_reports for each row execute function app.prepare_liquidity_report();

create function public.ipo_roll_liquidity_report(p_offering uuid,p_person uuid) returns jsonb language sql stable security invoker set search_path='' as $$
 select report from app.liquidity_reports where user_id=auth.uid() and offering_id=p_offering and person_id=p_person order by created_at desc,id desc limit 1
$$;
create function public.ipo_roll_request_liquidity(p_offering uuid,p_person uuid,p_request uuid,p_previous uuid default null) returns jsonb language plpgsql security invoker set search_path='' as $$
declare existing app.liquidity_reports; latest app.liquidity_reports;
begin
 if auth.uid() is null or not app.has_access() then raise insufficient_privilege; end if;
 perform pg_advisory_xact_lock(hashtextextended(auth.uid()::text || p_offering::text || p_person::text,0));
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
revoke all on function public.ipo_roll_liquidity_report(uuid,uuid),public.ipo_roll_request_liquidity(uuid,uuid,uuid,uuid) from public,anon;
grant execute on function public.ipo_roll_liquidity_report(uuid,uuid),public.ipo_roll_request_liquidity(uuid,uuid,uuid,uuid) to authenticated;
