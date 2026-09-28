-- Complete reviewed Veradermics management biographies and ownership table.
-- Conflicting source dates remain null/unspecified; disposable reports roll back.
begin;
create temporary table veradermics_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89000000-0000-4000-8000-000000000001','veradermics-a@example.invalid'),
 ('89000000-0000-4000-8000-000000000002','veradermics-b@example.invalid'),
 ('89000000-0000-4000-8000-000000000003','veradermics-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89000000-%';
insert into app.reviewers(user_id) values
 ('89000000-0000-4000-8000-000000000001'),('89000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; holder jsonb; r jsonb;
 offering constant uuid:='0a9515d4-675b-5c09-bb5b-4f75bcb0afe3'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>23 then raise exception 'Veradermics subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id=offering)<>13 then raise exception 'Veradermics source positions incomplete'; end if;
 if (select count(*) from research.biographies b join research.roles rr on rr.person_id=b.person_id where rr.offering_id=offering and b.approved)<>11
  then raise exception 'Veradermics management biographies incomplete'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Reid Waldman, M.D.';
 if jsonb_array_length(subject->'ownershipGrid')<>1
  or subject#>>'{ownershipGrid,0,reportedTotal}'<>'499121'
  or subject#>>'{ownershipGrid,0,positionBasis}'<>'unspecified'
  or subject#>'{ownershipGrid,0,holdingsAsOf}'<>'null'::jsonb
  then raise exception 'Reid source-date conflict was promoted or position failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Patrick Enright';
 if jsonb_array_length(subject->'ownershipGrid')<>1
  or subject#>>'{ownershipGrid,0,reportedTotal}'<>'3578873'
  or subject#>>'{ownershipGrid,0,attribution,kind}'<>'control_authority'
  or subject#>>'{ownershipGrid,0,reportedHolder,name}'<>'Entities affiliated with Longitude Capital'
  then raise exception 'Patrick near-duplicate row was duplicated or attribution failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='John W. Childs';
 if jsonb_array_length(subject->'ownershipGrid')<>1
  or subject#>>'{ownershipGrid,0,reportedTotal}'<>'1907889'
  or subject#>>'{ownershipGrid,0,reportedHolder,name}'<>'Entities affiliated with J.W. Childs Associates'
  then raise exception 'Childs repeated organization total was duplicated or lost'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Katarina Pance, Ph.D.';
 if jsonb_array_length(subject->'ownershipGrid')<>1
  or subject#>>'{ownershipGrid,0,reportedTotal}' is not null
  or subject#>>'{ownershipGrid,0,attribution,kind}' is not null
  then raise exception 'Katarina dash/no-control disclosure was promoted'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Simeon George, M.D.';
 if jsonb_array_length(subject->'ownershipGrid')<>1
  or subject#>>'{ownershipGrid,0,reportedTotal}'<>'1951868'
  or subject#>>'{ownershipGrid,0,attribution,kind}'<>'control_authority'
  then raise exception 'SR One control attribution failed'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='Entities affiliated with Viking Global';
 if holder->>'kind'<>'group' or holder#>>'{ownershipGrid,0,reportedTotal}'<>'1561494'
  then raise exception 'Viking reported group failed'; end if;

 r:=public.ipo_roll_request_liquidity(offering,(subject->>'id')::uuid,'89100000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.4' or jsonb_array_length(r->'positions')<>1
  or r#>>'{positions,0,category}'<>'unknown'
  or r#>>'{positions,0,positionBasis}'<>'unspecified'
  then raise exception 'Veradermics private report promoted or incomplete'; end if;
 perform set_config('veradermics.report',r->>'id',true);
end $$;

select set_config('request.jwt.claims','{"sub":"89000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
 or exists(select 1 from app.liquidity_reports where id=current_setting('veradermics.report')::uuid)
 then raise exception 'Cross-account Veradermics report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('0a9515d4-675b-5c09-bb5b-4f75bcb0afe3') is not null then raise exception 'Internal Veradermics research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(gen_random_uuid(),gen_random_uuid());
  raise exception 'Anonymous private report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline veradermics_test_state; begin
 select * into baseline from veradermics_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected Veradermics QA report count'; end if;
end $$;
select 'PASS: full Veradermics roster, date-conflicted single quantities, audited overlaps, controller attribution and private-report denial' result;
rollback;
