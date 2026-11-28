-- Shared source components, not private customer reports. No customer writes.
alter table research.ownerships add column quantity_kind text not null default 'reported_shares'
 check(quantity_kind in ('reported_shares','beneficial_total'));
create table research.ownership_components(
 ownership_id uuid not null references research.ownerships(id),
 ordinal int not null check(ordinal between 1 and 32),
 instrument text not null check(instrument in ('common_share','rsu','option','warrant')),
 quantity numeric not null check(quantity>0 and quantity=trunc(quantity) and quantity<=9007199254740991),
 attribution text not null check(attribution in ('direct','trust_or_family','fund_or_control','unknown')),
 description text not null check(length(description) between 1 and 6000),
 evidence_id uuid not null references evidence.spans(id),
 approved boolean not null default false,
 primary key(ownership_id,ordinal)
);
create index ownership_components_evidence on research.ownership_components(evidence_id);
alter table research.ownership_components enable row level security;
revoke all on research.ownership_components from public,anon,authenticated;
grant select on research.ownership_components to authenticated;
create policy ownership_component_read on research.ownership_components for select to authenticated using(
 (select app.has_access()) and approved and evidence.source_json(evidence_id) is not null
 and exists(select 1 from research.ownerships o
 join evidence.spans parent_span on parent_span.id=o.evidence_id
 join evidence.spans component_span on component_span.id=ownership_components.evidence_id
 where o.id=ownership_id and o.approved and o.quantity_kind='beneficial_total'
 and parent_span.document_id=component_span.document_id)
);

-- Missing/hidden/changed components must not appear to be a complete breakdown.
create function research.ownership_components_json(p_id uuid) returns jsonb language sql stable security invoker set search_path='' as $$
 select case when o.quantity_kind<>'beneficial_total' then jsonb_build_object('status','not_reviewed','items','[]'::jsonb)
 when o.shares is null or coalesce(c.total,0)<>o.shares or c.n<2 then jsonb_build_object('status','incomplete','items','[]'::jsonb)
 else jsonb_build_object('status','reconciled','items',c.items) end
 from research.ownerships o
 left join lateral(
 select sum(x.quantity) total,count(*) n,jsonb_agg(jsonb_build_object(
 'ordinal',x.ordinal,'instrument',x.instrument,'quantity',x.quantity,'attribution',x.attribution,
 'description',x.description,'source',evidence.source_json(x.evidence_id)) order by x.ordinal) items
 from research.ownership_components x
 join evidence.spans sp on sp.id=x.evidence_id
 join evidence.spans parent_span on parent_span.id=o.evidence_id and parent_span.document_id=sp.document_id
 where x.ownership_id=o.id and x.approved and evidence.source_json(x.evidence_id) is not null
 ) c on true where o.id=p_id and o.approved
$$;
revoke all on function research.ownership_components_json(uuid) from public,anon;
grant execute on function research.ownership_components_json(uuid) to authenticated;

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
  'id',new.id,'version','liquidity/1.2','asOf',new.created_at,'method','Evidence review; no AI inference',
  'offeringId',new.offering_id,'personId',new.person_id,'company',d->>'company','person',p->>'name',
  'relationship',p->>'relationship','relationshipSource',p->'source','positions',positions,
  'notice','Static private snapshot. Unknown is not zero. Future liquidity is conditional; lock-up expiry alone does not establish saleability. Market value is not cash proceeds.'
 );
 return new;
end $$;
