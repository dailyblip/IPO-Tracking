-- PicPay source-backed entity holders and named individual attributions.
-- All private-report writes and disposable users are rolled back.
begin;
create temporary table attribution_test_state as select count(*) reports from app.liquidity_reports;
insert into auth.users(id,email) values
 ('86000000-0000-4000-8000-000000000001','attribution-a@example.invalid'),
 ('86000000-0000-4000-8000-000000000002','attribution-b@example.invalid'),
 ('86000000-0000-4000-8000-000000000003','attribution-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '86000000-%';
insert into app.reviewers(user_id) values
 ('86000000-0000-4000-8000-000000000001'),('86000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"86000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; entity jsonb; r jsonb; offering constant uuid:='425a47a3-a3f8-5014-b56b-9865bd456646'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>19 then raise exception 'PicPay person/holder roster incomplete: %',jsonb_array_length(d->'people'); end if;
 select x into strict entity from jsonb_array_elements(d->'people')x where x->>'name'='J&F International B.V.';
 if entity->>'kind'<>'organization' or entity#>>'{ownershipGrid,0,reportedTotal}'<>'86451624'
  or entity#>>'{ownershipGrid,0,shareClass}'<>'Class B common shares' then raise exception 'Reported entity holding lost'; end if;
 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='José Antonio Batista Costa';
 if subject#>>'{ownershipGrid,0,reportedHolder,name}'<>'Stichting JAB'
  or subject#>>'{ownershipGrid,0,attribution,kind}'<>'beneficial_entitlement'
  or subject#>>'{ownershipGrid,0,reportedTotal}'<>'4269216' then raise exception 'Beneficiary attribution lost'; end if;
 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Joesley Mendonça Batista';
 if subject#>>'{ownershipGrid,0,reportedHolder,name}'<>'J&F International B.V.'
  or subject#>>'{ownershipGrid,0,attribution,kind}'<>'control_authority' then raise exception 'Control attribution lost'; end if;
 r:=public.ipo_roll_request_liquidity(offering,(subject->>'id')::uuid,'86100000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.4' or r#>>'{positions,0,category}'<>'unknown'
  or r#>>'{positions,0,reportedHolder,name}'<>'J&F International B.V.'
  or r#>>'{positions,0,attribution,kind}'<>'control_authority' then raise exception 'Control report promoted or incomplete'; end if;
 select x into strict entity from jsonb_array_elements(d->'people')x where x->>'name'='Stichting ACC Family';
 r:=public.ipo_roll_request_liquidity(offering,(entity->>'id')::uuid,'86100000-0000-4000-8000-000000000002');
 if r#>>'{positions,0,reportedTotal}'<>'3201912' or r#>>'{positions,0,category}'<>'unknown' then raise exception 'Entity private report failed'; end if;
 perform set_config('attribution.report',r->>'id',true);
end $$;
select set_config('request.jwt.claims','{"sub":"86000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports) or exists(select 1 from app.liquidity_reports where id=current_setting('attribution.report')::uuid)
  then raise exception 'Cross-account report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"86000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('425a47a3-a3f8-5014-b56b-9865bd456646') is not null then raise exception 'Internal research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(gen_random_uuid(),gen_random_uuid());
  raise exception 'Anonymous private report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare before_count bigint; begin
 select reports into before_count from attribution_test_state;
 if (select count(*) from app.liquidity_reports)<>before_count+2 then raise exception 'Unexpected private report mutation'; end if;
end $$;
select 'PASS: entity holders, beneficiary/control attribution, unknown liquidity, private entity reports and cross-account/unauthenticated denial' result;
rollback;
