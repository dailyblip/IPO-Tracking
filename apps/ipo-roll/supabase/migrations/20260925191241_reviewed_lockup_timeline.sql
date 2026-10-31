-- Reviewed date-only contractual terms, separate from actual release/saleability.
create table research.lockup_terms(
 id uuid primary key default gen_random_uuid(),
 ownership_id uuid not null unique references research.ownerships(id),
 trigger_date date not null check(trigger_date between date '2000-01-01' and date '2100-12-31'),
 day_count integer not null check(day_count between 1 and 730),
 boundary_date date generated always as (trigger_date + day_count) stored,
 reviewed_on date not null check(reviewed_on>=trigger_date),
 conditions text not null check(length(conditions) between 1 and 6000),
 evidence_ids uuid[] not null check(cardinality(evidence_ids)>=4 and array_position(evidence_ids,null) is null),
 approved boolean not null default false
);
alter table research.lockup_terms enable row level security;
revoke all on research.lockup_terms from public,anon,authenticated;
grant select on research.lockup_terms to authenticated;
create policy lockup_term_read on research.lockup_terms for select to authenticated using(
 (select app.has_access()) and approved and reviewed_on<=current_date
 and exists(select 1 from research.ownerships o where o.id=ownership_id and o.approved)
 and not exists(select 1 from unnest(evidence_ids) e where evidence.source_json(e) is null
 or not exists(select 1 from evidence.spans s join evidence.spans parent on parent.document_id=s.document_id
 join research.ownerships o on o.evidence_id=parent.id where s.id=e and o.id=ownership_id))
);
create function research.lockup_timeline_json(p_id uuid) returns jsonb language sql stable security invoker set search_path='' as $$
 select coalesce(jsonb_agg(jsonb_build_object('id',t.id,'trigger','Prospectus date',
 'triggerDate',t.trigger_date,'dayCount',t.day_count,'boundaryDate',t.boundary_date,
 'method','calendar-days-after/1','reviewedOn',t.reviewed_on,'conditions',t.conditions,
 'evidence',(select jsonb_agg(evidence.source_json(e) order by ord) from unnest(t.evidence_ids) with ordinality u(e,ord))) order by t.id),'[]'::jsonb)
 from research.lockup_terms t where t.ownership_id=p_id
$$;
revoke all on function research.lockup_timeline_json(uuid) from public,anon;
grant execute on function research.lockup_timeline_json(uuid) to authenticated;

create or replace function app.prepare_liquidity_report() returns trigger language plpgsql security invoker set search_path='' as $$
declare d jsonb; p jsonb; positions jsonb;
begin
 if auth.uid() is null or not app.has_access() then raise insufficient_privilege; end if;
 d:=public.ipo_roll_detail(new.offering_id);
 select x into p from jsonb_array_elements(d->'people') x where x->>'id'=new.person_id::text;
 if p is null then raise exception 'Subject not available' using errcode='P0002'; end if;
 new.id:=gen_random_uuid(); new.user_id:=auth.uid(); new.created_at:=clock_timestamp();
 select coalesce(jsonb_agg(jsonb_build_object(
  'id',o.id,'shareClass',o.share_class,'shares',case when o.quantity_kind='beneficial_total' then null else o.shares end,'reportedTotal',o.shares,'quantityKind',o.quantity_kind,'components',research.ownership_components_json(o.id),'positionBasis',o.position_basis,
  'filingAccession',f.accession,'documentHash',(select doc.content_sha256 from evidence.spans sp join evidence.documents doc on doc.id=sp.document_id where sp.id=o.evidence_id),'holdingsDate',f.filed_on,'filingDate',f.filed_on,'holdingsAsOf',o.holdings_as_of,'source',evidence.source_json(o.evidence_id),
  'category',case
   when o.quantity_kind='beneficial_total' then 'unknown'
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
 ) order by o.id),'[]'::jsonb) into positions
 from research.ownerships o join research.filings f on f.id=o.filing_id
 left join research.liquidity_assessments a on a.ownership_id=o.id
 where o.offering_id=new.offering_id and o.party_id=new.person_id and o.approved and evidence.source_json(o.evidence_id) is not null;
 new.report:=jsonb_build_object(
  'id',new.id,'version','liquidity/1.3','asOf',new.created_at,'method','Evidence review; no AI inference',
  'offeringId',new.offering_id,'personId',new.person_id,'company',d->>'company','person',p->>'name',
  'relationship',p->>'relationship','relationshipSource',p->'source','positions',positions,
  'notice','Static private snapshot. Unknown is not zero. Future liquidity is conditional; lock-up expiry alone does not establish saleability. Market value is not cash proceeds.'
 );
 return new;
end $$;
