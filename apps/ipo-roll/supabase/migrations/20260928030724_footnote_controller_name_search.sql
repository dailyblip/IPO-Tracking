-- Named control relationships are not personal economic ownership. Existing RLS,
-- evidence approval and audience rules remain in force; no quantities are added.
alter table research.roles drop constraint roles_relationship_check;
alter table research.roles add constraint roles_relationship_check
 check(relationship in ('Beneficial owner','Director','Executive','Footnote controller'));

-- An evidenced person must remain findable by name without a biography. Only
-- reviewed biography claims may match biography text; a shared fund footnote
-- must never act as a biography for each person named in it.
create or replace function public.ipo_roll_people_search(p_query text,p_relationship text default '',p_page int default 1)
returns jsonb language sql stable security invoker set search_path='' as $$
 with matches as (
  select b.id::text||':'||r.id::text id,
   jsonb_build_object('id',p.id,'name',p.name,'role',r.title,'relationship',r.relationship,
    'shares',null,'percent',null,'source',evidence.source_json(r.evidence_id),'biography',e.excerpt) person,
   c.name company,o.id "offeringId",o.stage,
   case when position(lower(p_query) in lower(p.name))>0 then 'Name match' else 'Biography text match' end "matchType",
   evidence.source_json(e.id) evidence
  from research.biographies b join research.people pe on pe.id=b.person_id
   join research.parties p on p.id=pe.id join evidence.spans e on e.id=b.span_id
   join research.roles r on r.person_id=p.id join research.offerings o on o.id=r.offering_id
   join research.companies c on c.id=o.company_id
  where length(p_query) between 2 and 160 and (p_relationship='' or r.relationship=p_relationship)
   and evidence.source_json(r.evidence_id) is not null and evidence.source_json(e.id) is not null
   and (position(lower(p_query) in lower(p.name))>0 or
    (to_tsvector('simple',e.excerpt) @@ phraseto_tsquery('simple',p_query)
     and exists(select 1 from research.claims cl where cl.biography_id=b.id
      and exists(select 1 from evidence.spans ce where ce.id=cl.evidence_id and ce.document_id=e.document_id)
      and position(lower(p_query) in lower(cl.object_text))>0 and evidence.source_json(cl.evidence_id) is not null)))
  union all
  select 'role:'||r.id::text,
   jsonb_build_object('id',p.id,'name',p.name,'role',r.title,'relationship',r.relationship,
    'shares',null,'percent',null,'source',evidence.source_json(r.evidence_id),'biography',null),
   c.name,o.id,o.stage,'Name match',evidence.source_json(r.evidence_id)
  from research.roles r join research.people pe on pe.id=r.person_id
   join research.parties p on p.id=pe.id join research.offerings o on o.id=r.offering_id
   join research.companies c on c.id=o.company_id
  where length(p_query) between 2 and 160 and (p_relationship='' or r.relationship=p_relationship)
   and evidence.source_json(r.evidence_id) is not null and position(lower(p_query) in lower(p.name))>0
   and not exists(select 1 from research.biographies b join evidence.spans e on e.id=b.span_id
    where b.person_id=p.id and evidence.source_json(e.id) is not null)
 ), paged as(select * from matches order by company,id limit 25 offset(greatest(1,least(p_page,1000))-1)*25)
 select jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(p)) from paged p),'[]'::jsonb),
  'total',(select count(*) from matches),'page',p_page,'pageSize',25)
$$;
revoke all on function public.ipo_roll_people_search(text,text,int) from public,anon;
grant execute on function public.ipo_roll_people_search(text,text,int) to authenticated;
