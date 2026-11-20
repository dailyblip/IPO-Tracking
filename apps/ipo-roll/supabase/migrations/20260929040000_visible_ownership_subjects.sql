-- Keep source-proven people visible even when no separate role was imported.
-- A neutral footnote mention does not imply issuer-stock ownership or control.
-- No research facts, saved snapshots, grants or RLS policies are changed.
alter table research.roles drop constraint roles_relationship_check;
alter table research.roles add constraint roles_relationship_check
 check(relationship in ('Beneficial owner','Director','Executive','Footnote controller','Footnote-named person'));

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
    select own.evidence_id from research.ownerships own where own.offering_id=c.id and own.party_id=p.id
     and own.approved and evidence.source_json(own.evidence_id) is not null order by own.id limit 1
   ) first_position on true
   where p.kind in ('organization','group','unresolved')
   union all
   select p.id,p.name,p.kind,'Disclosed shareholder','Beneficial owner',
    jsonb_build_array(jsonb_build_object(
      'title','Disclosed shareholder','relationship','Beneficial owner',
      'source',evidence.source_json(first_position.evidence_id)
    )),first_position.evidence_id,
    (select e.excerpt from research.biographies b join evidence.spans e on e.id=b.span_id
     where b.person_id=p.id and e.document_id=first_position.document_id
      and evidence.source_json(e.id) is not null order by b.id limit 1)
   from research.parties p join research.people pe on pe.id=p.id and pe.identity_verified
   join lateral(
    select own.evidence_id,sp.document_id from research.ownerships own
     join evidence.spans sp on sp.id=own.evidence_id
     join evidence.documents doc on doc.id=sp.document_id
     join evidence.sources es on es.id=doc.source_id
    where own.offering_id=c.id and own.party_id=p.id and own.approved
     and own.filing_id=o.current_filing_id and es.filing_id=own.filing_id
     and doc.source_id=o.source_id and evidence.source_json(own.evidence_id) is not null
    order by own.id limit 1
   ) first_position on true
   where p.kind='person' and not exists(
    select 1 from research.roles r where r.offering_id=c.id and r.person_id=p.id
     and evidence.source_json(r.evidence_id) is not null
   )
 ) subject),'[]'::jsonb))
 from research.offering_cards c join research.offerings o on o.id=c.id
 join evidence.sources s on s.id=o.source_id where c.id=p_id
$$;
