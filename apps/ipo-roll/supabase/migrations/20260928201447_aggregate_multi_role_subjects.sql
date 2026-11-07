-- Present one subject per party even when a person has more than one verified
-- relationship to an offering. Role rows remain separately evidenced in the
-- nested roles array; the legacy summaries are deterministic display fields.
-- Existing account-private snapshots remain immutable.
create or replace function public.ipo_roll_detail(p_id uuid) returns jsonb
language sql stable security invoker set search_path='' as $$
 select to_jsonb(c)||jsonb_build_object(
 'source',jsonb_build_object('title',s.title,'url',s.url,'date',s.published_on,'excerpt','','locator','Offering document'),
 'people',coalesce((select jsonb_agg(jsonb_build_object(
   'id',subject.id,'name',subject.name,'kind',subject.kind,'role',subject.role,
   'relationship',subject.relationship,'roles',subject.roles,
   'shares',null,'percent',null,
   'source',evidence.source_json(subject.evidence_id),
   'ownershipGrid',research.ownership_reference_json(c.id,subject.id),
   'biography',subject.biography
 ) order by case subject.kind when 'person' then 0 else 1 end,subject.name,subject.id) from (
   select p.id,p.name,p.kind,
    array_to_string(array_agg(distinct r.title order by r.title),' · ') role,
    array_to_string(array_agg(distinct r.relationship order by r.relationship),' / ') relationship,
    jsonb_agg(jsonb_build_object(
      'title',r.title,'relationship',r.relationship,
      'source',evidence.source_json(r.evidence_id)
    ) order by r.relationship,r.title,r.id) roles,
    (array_agg(r.evidence_id order by r.relationship,r.title,r.id))[1] evidence_id,
    (select e.excerpt from research.biographies b join evidence.spans e on e.id=b.span_id
     where b.person_id=p.id order by b.id limit 1) biography
   from research.roles r join research.people pe on pe.id=r.person_id join research.parties p on p.id=pe.id
   where r.offering_id=c.id and evidence.source_json(r.evidence_id) is not null
   group by p.id,p.name,p.kind
   union all
   select p.id,p.name,p.kind,'Disclosed shareholder','Beneficial owner',
    jsonb_build_array(jsonb_build_object(
      'title','Disclosed shareholder','relationship','Beneficial owner',
      'source',evidence.source_json(first_position.evidence_id)
    )),first_position.evidence_id,null
   from research.parties p join lateral(
    select o.evidence_id from research.ownerships o where o.offering_id=c.id and o.party_id=p.id
     and o.approved and evidence.source_json(o.evidence_id) is not null order by o.id limit 1
   ) first_position on true
   where p.kind in ('organization','group','unresolved')
 ) subject),'[]'::jsonb))
 from research.offering_cards c join research.offerings o on o.id=c.id
 join evidence.sources s on s.id=o.source_id where c.id=p_id
$$;

create or replace function app.prepare_liquidity_report() returns trigger language plpgsql security invoker set search_path='' as $$
declare d jsonb; p jsonb; positions jsonb;
begin
 if auth.uid() is null or not app.has_access() then raise insufficient_privilege; end if;
 d:=public.ipo_roll_detail(new.offering_id);
 select x into strict p from jsonb_array_elements(d->'people') x where x->>'id'=new.person_id::text;
 new.id:=gen_random_uuid(); new.user_id:=auth.uid(); new.created_at:=clock_timestamp();
 select coalesce(jsonb_agg(jsonb_build_object(
  'id',o.id,'shareClass',o.share_class,'shares',case when o.quantity_kind='beneficial_total' then null else o.shares end,
  'reportedTotal',o.shares,'quantityKind',o.quantity_kind,'components',research.ownership_components_json(o.id),
  'positionBasis',o.position_basis,'filingAccession',f.accession,
  'documentHash',(select doc.content_sha256 from evidence.spans sp join evidence.documents doc on doc.id=sp.document_id where sp.id=o.evidence_id),
  'holdingsDate',f.filed_on,'filingDate',f.filed_on,'holdingsAsOf',o.holdings_as_of,
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
  'id',new.id,'version','liquidity/1.5','asOf',new.created_at,'method','Evidence review; no AI inference',
  'offeringId',new.offering_id,'personId',new.person_id,'company',d->>'company','person',p->>'name',
  'relationship',p->>'relationship','relationshipSource',p->'source','roles',p->'roles','positions',positions,
  'notice','Static private snapshot. Reported holders, beneficiary entitlement and control authority remain distinct. Unknown is not zero. Future liquidity is conditional; lock-up expiry alone does not establish saleability. Market value is not cash proceeds.'
 );
 return new;
exception when no_data_found then
 raise exception 'Subject not available' using errcode='P0002';
end $$;
