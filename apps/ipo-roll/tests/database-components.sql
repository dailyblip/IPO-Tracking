-- Source-backed staging assertions. Disposable identities and mutations roll back.
begin;
insert into auth.users(id,email) values('80000000-0000-4000-8000-000000000001','components-a@example.invalid'),('80000000-0000-4000-8000-000000000002','components-b@example.invalid'),('80000000-0000-4000-8000-000000000003','components-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '80000000-%';
insert into app.reviewers(user_id) values('80000000-0000-4000-8000-000000000001'),('80000000-0000-4000-8000-000000000002');
create temporary table component_subject as select h.id,h.offering_id,h.party_id from research.ownerships h join research.parties p on p.id=h.party_id where p.name='Michael A. Chapp' and h.quantity_kind='beneficial_total';
grant select on component_subject to authenticated;
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"80000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare s record; r jsonb; p jsonb; n int:=0; begin
 for s in select h.*,p.name from research.ownerships h join research.parties p on p.id=h.party_id where h.quantity_kind='beneficial_total' loop
  r:=public.ipo_roll_request_liquidity(s.offering_id,s.party_id,gen_random_uuid()); n:=n+1; p:=r#>'{positions,0}';
  if jsonb_array_length(r->'positions')<>1 then raise exception 'Duplicate aggregate/components'; end if;
  if p->>'quantityKind'<>'beneficial_total' or p->>'shares' is not null or p->>'marketValue' is not null or p->>'category'<>'unknown' then raise exception 'Mixed award total presented as liquid shares'; end if;
  if p->>'holdingsAsOf'<>'2026-09-15' or p->>'filingDate'<>'2026-09-21' or p#>>'{components,status}'<>'reconciled' then raise exception 'Date or reconciliation mismatch'; end if;
  if (select sum((x->>'quantity')::numeric) from jsonb_array_elements(p#>'{components,items}')x)<>(p->>'reportedTotal')::numeric then raise exception 'Component sum mismatch'; end if;
  if s.name='Michael A. Chapp' then
   if p->>'reportedTotal'<>'7007291' or jsonb_array_length(p#>'{components,items}')<>4 or p#>>'{components,items,3,instrument}'<>'option' or p#>>'{components,items,3,quantity}'<>'5452768' or p#>>'{components,items,1,attribution}'<>'trust_or_family' then raise exception 'Mixed components wrong'; end if;
   perform set_config('components.report',r->>'id',true);
  elsif s.name='Sean Brecker' then
   if p->>'reportedTotal'<>'622772' or p#>>'{components,items,1,attribution}'<>'trust_or_family' or p#>>'{components,items,1,instrument}'<>'rsu' then raise exception 'Trust RSU attribution wrong'; end if;
  elsif s.name='Thomas Hale' then
   if p->>'reportedTotal'<>'3554065' or p#>>'{components,items,0,quantity}'<>'3423829' then raise exception 'Direct common component wrong'; end if;
  else raise exception 'Unexpected mixed cohort'; end if;
  if public.ipo_roll_request_liquidity(s.offering_id,s.party_id,gen_random_uuid())<>r then raise exception 'Reopen regenerated'; end if;
 end loop;
 if n<>3 then raise exception 'Expected three mixed positions'; end if;
 begin update research.ownership_components set quantity=1; raise exception 'Customer modified facts' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
select set_config('request.jwt.claims','{"sub":"80000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ declare s record; begin
 select * into strict s from component_subject;
 if exists(select 1 from app.liquidity_reports where id=current_setting('components.report')::uuid) or public.ipo_roll_liquidity_report(s.offering_id,s.party_id) is not null then raise exception 'Another reviewer sees report or existence'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"80000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin if exists(select 1 from research.ownership_components) or exists(select 1 from app.liquidity_reports) then raise exception 'Internal facts/private reports leaked to ordinary customer'; end if; end $$;
reset role;
-- A reviewed passage from another filing is not evidence for this component.
update research.ownership_components set evidence_id=(
 select h.evidence_id from research.ownerships h where h.id not in(select id from component_subject)
 and h.quantity_kind='reported_shares' limit 1
) where ownership_id in(select id from component_subject) and ordinal=1;
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"80000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare s record; begin
 select * into strict s from component_subject;
 if exists(select 1 from research.ownership_components where ownership_id=s.id and ordinal=1)
 or research.ownership_components_json(s.id)->>'status'<>'incomplete' then raise exception 'Cross-document evidence accepted'; end if;
end $$;
reset role;
update research.ownership_components c set evidence_id=a.evidence_ids[array_length(a.evidence_ids,1)]
 from research.liquidity_assessments a where a.ownership_id=c.ownership_id
 and c.ownership_id in(select id from component_subject) and c.ordinal=1;
update research.ownership_components set approved=false where ownership_id in(select id from component_subject) and ordinal=4;
-- Even an erroneous liquid classification cannot promote mixed instrument totals.
update research.liquidity_assessments set classification='liquid',current_position_confirmed=true,personal_interest_confirmed=true,valid_through=current_date+1 where ownership_id in(select id from component_subject);
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"80000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare s record; r jsonb; old jsonb; begin
 select * into strict s from component_subject;
 old:=public.ipo_roll_liquidity_report(s.offering_id,s.party_id);
 if old#>>'{positions,0,components,status}'<>'reconciled' or jsonb_array_length(old#>'{positions,0,components,items}')<>4 then raise exception 'Static report rewritten'; end if;
 r:=public.ipo_roll_request_liquidity(s.offering_id,s.party_id,gen_random_uuid(),(old->>'id')::uuid);
 if r#>>'{positions,0,components,status}'<>'incomplete' or jsonb_array_length(r#>'{positions,0,components,items}')<>0 or r#>>'{positions,0,category}'<>'unknown' then raise exception 'Incomplete evidence or mixed total promoted'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform research.ownership_components_json(gen_random_uuid()); raise exception 'Anonymous components allowed' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
reset role;
select 'PASS: three reconciled totals/eight components, no double counting, instrument/trust separation, private reports, static snapshots and incomplete-evidence denial' result;
rollback;
