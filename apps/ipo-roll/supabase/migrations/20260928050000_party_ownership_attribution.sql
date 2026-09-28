-- Preserve the filing's reported holder while linking expressly named people to
-- beneficiary/control footnotes. A control relationship is never converted into
-- personal economic ownership. Existing private snapshots remain immutable.
create table research.ownership_attributions (
 ownership_id uuid not null references research.ownerships(id),
 person_id uuid not null references research.people(id),
 kind text not null check(kind in ('beneficial_entitlement','control_authority')),
 description text not null check(length(description) between 1 and 6000),
 evidence_id uuid not null references evidence.spans(id),
 approved boolean not null default false,
 primary key(ownership_id,person_id)
);
create index ownership_attributions_person on research.ownership_attributions(person_id,ownership_id);
alter table research.ownership_attributions enable row level security;
revoke all on research.ownership_attributions from public,anon,authenticated;
grant select on research.ownership_attributions to authenticated;
create policy ownership_attribution_read on research.ownership_attributions for select to authenticated using(
 (select app.has_access()) and approved and evidence.source_json(evidence_id) is not null
 and exists(select 1 from research.ownerships o join evidence.spans os on os.id=o.evidence_id
  join evidence.spans ats on ats.id=ownership_attributions.evidence_id
  where o.id=ownership_id and o.approved and os.document_id=ats.document_id)
);

create or replace function research.ownership_reference_json(p_offering uuid,p_person uuid)
returns jsonb language sql stable security invoker set search_path='' as $$
 select coalesce(jsonb_agg(jsonb_build_object(
  'id',o.id,'shareClass',o.share_class,'reportedTotal',o.shares,'quantityKind',o.quantity_kind,
  'positionBasis',o.position_basis,'holdingsAsOf',o.holdings_as_of,'filingDate',f.filed_on,
  'filingAccession',f.accession,'source',evidence.source_json(o.evidence_id),
  'reportedHolder',jsonb_build_object('id',holder.id,'name',holder.name,'kind',holder.kind),
  'attribution',case when oa.person_id is null then null else jsonb_build_object(
    'kind',oa.kind,'description',oa.description,'source',evidence.source_json(oa.evidence_id)) end,
  'components',research.ownership_components_json(o.id),
  'restrictionTimeline',research.lockup_timeline_json(o.id),
  'conditions',coalesce(a.conditions,''),'explanation',coalesce(a.explanation,''),
  'assessmentDate',a.assessed_on,
  'evidence',coalesce((select jsonb_agg(evidence.source_json(e)) from unnest(a.evidence_ids) e
    where evidence.source_json(e) is not null),'[]'::jsonb)
 ) order by o.position_basis,o.share_class,o.id),'[]'::jsonb)
 from research.ownerships o join research.filings f on f.id=o.filing_id
 join research.parties holder on holder.id=o.party_id
 left join research.ownership_attributions oa on oa.ownership_id=o.id and oa.person_id=p_person and oa.approved
 left join research.liquidity_assessments a on a.ownership_id=o.id
 where o.offering_id=p_offering and o.approved
 and (o.party_id=p_person or oa.person_id is not null)
 and auth.uid() is not null and app.has_access()
 and evidence.source_json(o.evidence_id) is not null
 and (oa.person_id is null or evidence.source_json(oa.evidence_id) is not null)
$$;

create or replace function public.ipo_roll_detail(p_id uuid) returns jsonb
language sql stable security invoker set search_path='' as $$
 select to_jsonb(c)||jsonb_build_object(
 'source',jsonb_build_object('title',s.title,'url',s.url,'date',s.published_on,'excerpt','','locator','Offering document'),
 'people',coalesce((select jsonb_agg(jsonb_build_object(
   'id',subject.id,'name',subject.name,'kind',subject.kind,'role',subject.role,
   'relationship',subject.relationship,'shares',null,'percent',null,
   'source',evidence.source_json(subject.evidence_id),
   'ownershipGrid',research.ownership_reference_json(c.id,subject.id),
   'biography',subject.biography
 ) order by case subject.kind when 'person' then 0 else 1 end,subject.name) from (
   select p.id,p.name,p.kind,r.title role,r.relationship,r.evidence_id,
    (select e.excerpt from research.biographies b join evidence.spans e on e.id=b.span_id
     where b.person_id=p.id order by b.id limit 1) biography
   from research.roles r join research.people pe on pe.id=r.person_id join research.parties p on p.id=pe.id
   where r.offering_id=c.id and evidence.source_json(r.evidence_id) is not null
   union all
   select p.id,p.name,p.kind,'Disclosed shareholder','Beneficial owner',first_position.evidence_id,null
   from research.parties p join lateral(
    select o.evidence_id from research.ownerships o where o.offering_id=c.id and o.party_id=p.id
     and o.approved and evidence.source_json(o.evidence_id) is not null order by o.id limit 1
   ) first_position on true
   where p.kind in ('organization','group','unresolved')
 ) subject),'[]'::jsonb))
 from research.offering_cards c join research.offerings o on o.id=c.id
 join evidence.sources s on s.id=o.source_id where c.id=p_id
$$;

-- Existing person subjects remain valid because research.people is a subset of
-- research.parties. This enables account-private reports for disclosed entities
-- without modifying any saved report row or JSON snapshot.
alter table app.liquidity_reports drop constraint liquidity_reports_person_id_fkey;
alter table app.liquidity_reports add constraint liquidity_reports_person_id_fkey
 foreign key(person_id) references research.parties(id);

create or replace function app.prepare_liquidity_report() returns trigger language plpgsql security invoker set search_path='' as $$
declare d jsonb; p jsonb; positions jsonb;
begin
 if auth.uid() is null or not app.has_access() then raise insufficient_privilege; end if;
 d:=public.ipo_roll_detail(new.offering_id);
 select x into p from jsonb_array_elements(d->'people') x where x->>'id'=new.person_id::text;
 if p is null then raise exception 'Subject not available' using errcode='P0002'; end if;
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
  'id',new.id,'version','liquidity/1.4','asOf',new.created_at,'method','Evidence review; no AI inference',
  'offeringId',new.offering_id,'personId',new.person_id,'company',d->>'company','person',p->>'name',
  'relationship',p->>'relationship','relationshipSource',p->'source','positions',positions,
  'notice','Static private snapshot. Reported holders, beneficiary entitlement and control authority remain distinct. Unknown is not zero. Future liquidity is conditional; lock-up expiry alone does not establish saleability. Market value is not cash proceeds.'
 );
 return new;
end $$;

