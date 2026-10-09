-- Search returns one person/offering subject even when several separately
-- evidenced role rows qualify. The complete role set remains visible.
create or replace function public.ipo_roll_people_search(p_query text,p_relationship text default '',p_page int default 1)
returns jsonb language sql stable security invoker set search_path='' as $$
 with role_subjects as (
  select p.id person_id,p.name,o.id offering_id,c.name company,o.stage,
   array_to_string(array_agg(distinct r.title order by r.title),' · ') role,
   array_to_string(array_agg(distinct r.relationship order by r.relationship),' / ') relationship,
   array_agg(distinct r.relationship order by r.relationship) relationships,
   jsonb_agg(jsonb_build_object(
    'title',r.title,'relationship',r.relationship,'source',evidence.source_json(r.evidence_id)
   ) order by r.relationship,r.title,r.id) roles,
   (array_agg(r.evidence_id order by r.relationship,r.title,r.id))[1] evidence_id
  from research.roles r join research.people pe on pe.id=r.person_id
   join research.parties p on p.id=pe.id join research.offerings o on o.id=r.offering_id
   join research.companies c on c.id=o.company_id
  where evidence.source_json(r.evidence_id) is not null
  group by p.id,p.name,o.id,c.name,o.stage
 ), biography_matches as (
  select distinct on(rs.person_id,rs.offering_id)
   b.id::text||':'||rs.person_id::text||':'||rs.offering_id::text id,
   jsonb_build_object('id',rs.person_id,'name',rs.name,'role',rs.role,
    'relationship',rs.relationship,'roles',rs.roles,'shares',null,'percent',null,
    'source',evidence.source_json(rs.evidence_id),'biography',e.excerpt) person,
   rs.company,rs.offering_id "offeringId",rs.stage,
   case when position(lower(p_query) in lower(rs.name))>0 then 'Name match' else 'Biography text match' end "matchType",
   evidence.source_json(e.id) evidence
  from role_subjects rs join research.biographies b on b.person_id=rs.person_id
   join evidence.spans e on e.id=b.span_id
  where length(p_query) between 2 and 160
   and (p_relationship='' or p_relationship=any(rs.relationships))
   and evidence.source_json(e.id) is not null
   and (position(lower(p_query) in lower(rs.name))>0 or
    (to_tsvector('simple',e.excerpt) @@ phraseto_tsquery('simple',p_query)
     and exists(select 1 from research.claims cl where cl.biography_id=b.id
      and exists(select 1 from evidence.spans ce where ce.id=cl.evidence_id and ce.document_id=e.document_id)
      and position(lower(p_query) in lower(cl.object_text))>0
      and evidence.source_json(cl.evidence_id) is not null)))
  order by rs.person_id,rs.offering_id,b.id
 ), role_only_matches as (
  select 'role:'||rs.person_id::text||':'||rs.offering_id::text id,
   jsonb_build_object('id',rs.person_id,'name',rs.name,'role',rs.role,
    'relationship',rs.relationship,'roles',rs.roles,'shares',null,'percent',null,
    'source',evidence.source_json(rs.evidence_id),'biography',null) person,
   rs.company,rs.offering_id "offeringId",rs.stage,'Name match' "matchType",
   evidence.source_json(rs.evidence_id) evidence
  from role_subjects rs
  where length(p_query) between 2 and 160
   and (p_relationship='' or p_relationship=any(rs.relationships))
   and position(lower(p_query) in lower(rs.name))>0
   and not exists(select 1 from research.biographies b join evidence.spans e on e.id=b.span_id
    where b.person_id=rs.person_id and evidence.source_json(e.id) is not null)
 ), matches as (
  select * from biography_matches union all select * from role_only_matches
 ), paged as (
  select * from matches order by company,id limit 25 offset(greatest(1,least(p_page,1000))-1)*25
 )
 select jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(p)) from paged p),'[]'::jsonb),
  'total',(select count(*) from matches),'page',p_page,'pageSize',25)
$$;
revoke all on function public.ipo_roll_people_search(text,text,int) from public,anon;
grant execute on function public.ipo_roll_people_search(text,text,int) to authenticated;
