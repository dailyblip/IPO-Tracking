-- Add explicit holdings-date provenance; never substitute the filing date.
-- Existing static reports are intentionally untouched. holdingsDate remains a
-- deprecated filing-date alias for older deployed clients until their upgrade.
alter table research.ownerships add column holdings_as_of date;
comment on column research.ownerships.holdings_as_of is 'Explicit ownership table as-of date, not filing date or present ownership confirmation. See reviewed evidence.';

create or replace function app.prepare_liquidity_report() returns trigger language plpgsql security invoker set search_path='' as $$
declare d jsonb; p jsonb; positions jsonb;
begin
 if auth.uid() is null or not app.has_access() then raise insufficient_privilege; end if;
 d:=public.ipo_roll_detail(new.offering_id);
 select x into p from jsonb_array_elements(d->'people') x where x->>'id'=new.person_id::text;
 if p is null then raise exception 'Subject not available' using errcode='P0002'; end if;
 new.id:=gen_random_uuid(); new.user_id:=auth.uid(); new.created_at:=clock_timestamp();
 select coalesce(jsonb_agg(jsonb_build_object(
  'id',o.id,'shareClass',o.share_class,'shares',o.shares,'positionBasis',o.position_basis,
  'filingAccession',f.accession,'documentHash',(select doc.content_sha256 from evidence.spans sp join evidence.documents doc on doc.id=sp.document_id where sp.id=o.evidence_id),'holdingsDate',f.filed_on,'filingDate',f.filed_on,'holdingsAsOf',o.holdings_as_of,'source',evidence.source_json(o.evidence_id),
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
  'id',new.id,'version','liquidity/1.1','asOf',new.created_at,'method','Evidence review; no AI inference',
  'offeringId',new.offering_id,'personId',new.person_id,'company',d->>'company','person',p->>'name',
  'relationship',p->>'relationship','relationshipSource',p->'source','positions',positions,
  'notice','Static private snapshot. Unknown is not zero. Future liquidity is conditional; lock-up expiry alone does not establish saleability. Market value is not cash proceeds.'
 );
 return new;
end $$;
