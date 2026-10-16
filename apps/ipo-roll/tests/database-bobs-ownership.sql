-- Complete reviewed Bob's Discount Furniture management biographies and ownership table.
-- Alternative option scenarios remain held; disposable private reports roll back.
begin;
create temporary table bobs_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89200000-0000-4000-8000-000000000001','bobs-a@example.invalid'),
 ('89200000-0000-4000-8000-000000000002','bobs-b@example.invalid'),
 ('89200000-0000-4000-8000-000000000003','bobs-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89200000-%';
insert into app.reviewers(user_id) values
 ('89200000-0000-4000-8000-000000000001'),('89200000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89200000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; holder jsonb; no_row jsonb; r jsonb;
 offering constant uuid:='40d72939-4545-5754-922a-f2ae6f88aeaa'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>20 then raise exception 'Bob''s subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id=offering)<>32 then raise exception 'Bob''s source positions incomplete'; end if;
 if (select count(*) from research.biographies b join research.roles rr on rr.person_id=b.person_id where rr.offering_id=offering and b.approved)<>19
  then raise exception 'Bob''s management biographies incomplete'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and holdings_as_of<>'2026-01-23')
  or exists(select 1 from research.ownerships where offering_id=offering and position_basis not in ('pre','post'))
  then raise exception 'Bob''s date or basis mismatch'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and shares=95370751)
  then raise exception 'Alternative full-option Bain scenario was imported'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='Entities affiliated with Bain Capital';
 if holder->>'kind'<>'group' or jsonb_array_length(holder->'ownershipGrid')<>2
  or holder#>>'{ownershipGrid,0,reportedTotal}'<>'98288251'
  or holder#>>'{ownershipGrid,1,reportedTotal}'<>'98288251'
  then raise exception 'Bain group total failed or option scenario duplicated'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='William G. (“Bill”) Barton';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or subject#>>'{ownershipGrid,0,reportedTotal}'<>'2098735'
  or subject#>>'{ownershipGrid,1,reportedTotal}'<>'2098735'
  then raise exception 'Barton option totals failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Joshua Bekenstein';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or subject#>>'{ownershipGrid,0,reportedTotal}' is not null
  or subject#>>'{ownershipGrid,0,attribution,kind}' is not null
  then raise exception 'Bekenstein dash or Bain non-attribution failed'; end if;

 select x into strict no_row from jsonb_array_elements(d->'people')x where x->>'name'='Stephen Nesle';
 if jsonb_array_length(no_row->'ownershipGrid')<>0
  or no_row->>'biography' is null
  then raise exception 'Management person outside ownership table disappeared'; end if;

 r:=public.ipo_roll_request_liquidity(offering,(subject->>'id')::uuid,'89300000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.6' or jsonb_array_length(r->'positions')<>2
  or exists(select 1 from jsonb_array_elements(r->'positions') p where p->>'category'<>'unknown' or p->>'reportedTotal' is not null)
  then raise exception 'Bob''s private report promoted a dash or incomplete'; end if;
 perform set_config('bobs.report',r->>'id',true);
end $$;

select set_config('request.jwt.claims','{"sub":"89200000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
 or exists(select 1 from app.liquidity_reports where id=current_setting('bobs.report')::uuid)
 then raise exception 'Cross-account Bob''s report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89200000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('40d72939-4545-5754-922a-f2ae6f88aeaa') is not null then raise exception 'Internal Bob''s research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(gen_random_uuid(),gen_random_uuid());
  raise exception 'Anonymous private report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline bobs_test_state; begin
 select * into baseline from bobs_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected Bob''s QA report count'; end if;
end $$;
select 'PASS: full Bob''s roster, option-only/dash distinctions, held alternative scenario and private-report denial' result;
rollback;
