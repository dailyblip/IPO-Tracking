-- Shared, authorized source facts only. Never reads or creates private reports.
create function research.ownership_reference_json(p_offering uuid,p_person uuid)
returns jsonb language sql stable security invoker set search_path='' as $$
 select coalesce(jsonb_agg(jsonb_build_object(
  'id',o.id,'shareClass',o.share_class,'reportedTotal',o.shares,'quantityKind',o.quantity_kind,
  'positionBasis',o.position_basis,'holdingsAsOf',o.holdings_as_of,'filingDate',f.filed_on,
  'filingAccession',f.accession,'source',evidence.source_json(o.evidence_id),
  'components',research.ownership_components_json(o.id),
  'restrictionTimeline',research.lockup_timeline_json(o.id),
  'conditions',coalesce(a.conditions,''),'explanation',coalesce(a.explanation,''),
  'assessmentDate',a.assessed_on,
  'evidence',coalesce((select jsonb_agg(evidence.source_json(e)) from unnest(a.evidence_ids) e
    where evidence.source_json(e) is not null),'[]'::jsonb)
 ) order by o.share_class,o.id),'[]'::jsonb)
 from research.ownerships o join research.filings f on f.id=o.filing_id
 left join research.liquidity_assessments a on a.ownership_id=o.id
 where o.offering_id=p_offering and o.party_id=p_person and o.approved
 and auth.uid() is not null and app.has_access()
 and evidence.source_json(o.evidence_id) is not null
$$;
revoke all on function research.ownership_reference_json(uuid,uuid) from public,anon;
grant execute on function research.ownership_reference_json(uuid,uuid) to authenticated;

create or replace function public.ipo_roll_detail(p_id uuid) returns jsonb
language sql stable security invoker set search_path='' as $$
 select to_jsonb(c)||jsonb_build_object(
 'source',jsonb_build_object('title',s.title,'url',s.url,'date',s.published_on,'excerpt','','locator','Offering document'),
 'people',coalesce((select jsonb_agg(jsonb_build_object(
   'id',p.id,'name',p.name,'role',r.title,'relationship',r.relationship,'shares',null,'percent',null,
   'source',evidence.source_json(r.evidence_id),
   'ownershipGrid',research.ownership_reference_json(c.id,p.id),
   'biography',(select e.excerpt from research.biographies b join evidence.spans e on e.id=b.span_id where b.person_id=p.id order by b.id limit 1)
 )) from research.roles r join research.people pe on pe.id=r.person_id join research.parties p on p.id=pe.id
 where r.offering_id=c.id and evidence.source_json(r.evidence_id) is not null),'[]'::jsonb))
 from research.offering_cards c join research.offerings o on o.id=c.id
 join evidence.sources s on s.id=o.source_id where c.id=p_id
$$;
