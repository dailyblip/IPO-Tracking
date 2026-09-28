-- Complete reviewed Eikon management biographies and principal-stockholder table.
-- Repeated Lux/Joshua and aggregate rows stay held; disposable reports roll back.
begin;
create temporary table eikon_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89400000-0000-4000-8000-000000000001','eikon-a@example.invalid'),
 ('89400000-0000-4000-8000-000000000002','eikon-b@example.invalid'),
 ('89400000-0000-4000-8000-000000000003','eikon-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89400000-%';
insert into app.reviewers(user_id) values
 ('89400000-0000-4000-8000-000000000001'),('89400000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89400000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; holder jsonb; r jsonb;
 offering constant uuid:='6d9e3d3f-3ad7-57b7-8402-6f53e9c2fb94'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>25 then raise exception 'Eikon subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id=offering)<>13 then raise exception 'Eikon source positions incomplete'; end if;
 if (select count(*) from research.biographies b join research.roles rr on rr.person_id=b.person_id where rr.offering_id=offering and b.approved)<>10
  then raise exception 'Eikon management biographies incomplete'; end if;
 if (select count(*) from research.ownership_attributions oa join research.ownerships o on o.id=oa.ownership_id where o.offering_id=offering and oa.approved)<>10
  then raise exception 'Eikon holder-person attributions incomplete'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and holdings_as_of<>'2025-12-31')
  or exists(select 1 from research.ownerships where offering_id=offering and position_basis<>'pre')
  then raise exception 'Eikon date or basis mismatch'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='Entities affiliated with Lux';
 if holder->>'kind'<>'group' or jsonb_array_length(holder->'ownershipGrid')<>1
  or holder#>>'{ownershipGrid,0,reportedTotal}'<>'5695010'
  then raise exception 'Lux reported group failed or was duplicated'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Joshua Wolfe';
 if jsonb_array_length(subject->'ownershipGrid')<>1
  or subject#>>'{ownershipGrid,0,attribution,kind}'<>'reported_beneficial_owner'
  or subject#>>'{ownershipGrid,0,reportedHolder,name}'<>'Entities affiliated with Lux'
  then raise exception 'Joshua repeated Lux row was duplicated or attribution failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Peter Hébert';
 if subject#>>'{ownershipGrid,0,attribution,kind}'<>'control_authority'
  or subject#>>'{ownershipGrid,0,reportedHolder,name}'<>'Entities affiliated with Lux'
  then raise exception 'Lux control attribution failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Leon Chen, Ph.D.';
 if jsonb_array_length(subject->'ownershipGrid')<>1
  or subject#>>'{ownershipGrid,0,reportedTotal}' is not null
  or subject#>>'{ownershipGrid,0,attribution,kind}' is not null
  then raise exception 'Leon dash/no-control disclosure was promoted'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Chau, Hoi Shuen Solina Holly';
 if subject#>>'{ownershipGrid,0,attribution,kind}'<>'beneficial_entitlement'
  or subject#>>'{ownershipGrid,0,reportedHolder,name}'<>'Mahler International Limited'
  then raise exception 'Mahler ultimate-beneficiary attribution failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Benjamin Thorner';
 if jsonb_array_length(subject->'ownershipGrid')<>0 or subject->>'biography' is null
  then raise exception 'Management person outside ownership table disappeared'; end if;

 r:=public.ipo_roll_request_liquidity(offering,(select (x->>'id')::uuid from jsonb_array_elements(d->'people')x where x->>'name'='Joshua Wolfe'),'89500000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.4' or jsonb_array_length(r->'positions')<>1
  or r#>>'{positions,0,category}'<>'unknown'
  or r#>>'{positions,0,attribution,kind}'<>'reported_beneficial_owner'
  then raise exception 'Eikon private report promoted or incomplete'; end if;
 perform set_config('eikon.report',r->>'id',true);
end $$;

select set_config('request.jwt.claims','{"sub":"89400000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
 or exists(select 1 from app.liquidity_reports where id=current_setting('eikon.report')::uuid)
 then raise exception 'Cross-account Eikon report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89400000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('6d9e3d3f-3ad7-57b7-8402-6f53e9c2fb94') is not null then raise exception 'Internal Eikon research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(gen_random_uuid(),gen_random_uuid());
  raise exception 'Anonymous private report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline eikon_test_state; begin
 select * into baseline from eikon_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected Eikon QA report count'; end if;
end $$;
select 'PASS: full Eikon roster, audited overlaps, fund/controller distinctions and private-report denial' result;
rollback;

