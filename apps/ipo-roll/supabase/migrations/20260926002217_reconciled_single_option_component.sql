-- One option component can explain an entire option-only beneficial total.
-- Retain exact-sum, visible same-document evidence and invoker/RLS safeguards.
-- No grants, classifications, reports or source facts are rewritten.
create or replace function research.ownership_components_json(p_id uuid) returns jsonb language sql stable security invoker set search_path='' as $$
 select case when o.quantity_kind<>'beneficial_total' then jsonb_build_object('status','not_reviewed','items','[]'::jsonb)
 when o.shares is null or coalesce(c.total,0)<>o.shares
   or (c.n<2 and not (c.n=1 and c.only_options))
 then jsonb_build_object('status','incomplete','items','[]'::jsonb)
 else jsonb_build_object('status','reconciled','items',c.items) end
 from research.ownerships o
 left join lateral(
 select sum(x.quantity) total,count(*) n,bool_and(x.instrument='option') only_options,
 jsonb_agg(jsonb_build_object(
 'ordinal',x.ordinal,'instrument',x.instrument,'quantity',x.quantity,'attribution',x.attribution,
 'description',x.description,'source',evidence.source_json(x.evidence_id)) order by x.ordinal) items
 from research.ownership_components x
 join evidence.spans sp on sp.id=x.evidence_id
 join evidence.spans parent_span on parent_span.id=o.evidence_id and parent_span.document_id=sp.document_id
 where x.ownership_id=o.id and x.approved and evidence.source_json(x.evidence_id) is not null
 ) c on true where o.id=p_id and o.approved
$$;
