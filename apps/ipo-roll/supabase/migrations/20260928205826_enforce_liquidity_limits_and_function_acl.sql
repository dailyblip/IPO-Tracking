-- Bound account-private snapshot generation at the database boundary. These
-- checks cover both the public RPC and direct Data API inserts. Existing static
-- reports remain unchanged.
alter role authenticated set statement_timeout = '15s';

-- Schema-scoped default revokes do not remove PostgreSQL's global PUBLIC
-- function default. Fix the owner default and remove inherited PUBLIC execute
-- from existing internal helpers. Explicit authenticated grants remain intact.
alter default privileges for role postgres revoke execute on functions from public;
revoke execute on all functions in schema research,evidence,app,ops from public;

create or replace function app.prepare_liquidity_report() returns trigger language plpgsql security invoker set search_path='' as $$
declare d jsonb; p jsonb; positions jsonb; snapshot_time timestamptz:=clock_timestamp();
begin
 if auth.uid() is null or not app.has_access() then raise insufficient_privilege; end if;
 if (select count(*) from app.liquidity_reports
     where user_id=auth.uid() and created_at>=snapshot_time-interval '24 hours')>=100 then
  raise exception 'Liquidity report daily quota reached' using errcode='54000';
 end if;
 if (select count(*) from app.liquidity_reports
     where user_id=auth.uid() and offering_id=new.offering_id and person_id=new.person_id
       and created_at>=snapshot_time-interval '24 hours')>=10 then
  raise exception 'Liquidity report subject quota reached' using errcode='54000';
 end if;
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
