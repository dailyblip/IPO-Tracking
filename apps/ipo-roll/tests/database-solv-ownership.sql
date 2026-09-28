-- Complete reviewed SOLV Energy management biographies and principal-stockholders table.
-- Up-C classes, pre/base-post alternatives, group attribution and explicit dash rows stay distinct.
begin;
create temporary table solv_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89900000-0000-4000-8000-000000000001','solv-a@example.invalid'),
 ('89900000-0000-4000-8000-000000000002','solv-b@example.invalid'),
 ('89900000-0000-4000-8000-000000000003','solv-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89900000-%';
insert into app.reviewers(user_id) values
 ('89900000-0000-4000-8000-000000000001'),('89900000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89900000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; holder jsonb; r jsonb;
 offering constant uuid:='944df127-9e7b-5b01-a1ba-a8c799cbdf50'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>24 then raise exception 'SOLV subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id=offering and approved)<>68
  then raise exception 'SOLV source positions incomplete'; end if;
 if (select count(*) from research.biographies b join research.roles rr on rr.person_id=b.person_id where rr.offering_id=offering and b.approved)<>19
  then raise exception 'SOLV management biographies incomplete'; end if;
 if (select count(*) from research.ownership_attributions oa join research.ownerships o on o.id=oa.ownership_id where o.offering_id=offering and oa.approved)<>20
  then raise exception 'SOLV controller/deemed-owner attributions incomplete'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and holdings_as_of is not null)
  or (select count(distinct position_basis) from research.ownerships where offering_id=offering)<>2
  or (select count(distinct share_class) from research.ownerships where offering_id=offering)<>2
  then raise exception 'SOLV projected basis, class or intentionally unknown holdings date mismatch'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='American Securities';
 if holder->>'kind'<>'group' or jsonb_array_length(holder->'ownershipGrid')<>4
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal'='91773571')<>2
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal'='57838430')<>2
  then raise exception 'SOLV American Securities group/class snapshots failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Michael G. Fisch';
 if jsonb_array_length(subject->'ownershipGrid')<>4
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}'<>'control_authority')
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{reportedHolder,name}'<>'American Securities')
  then raise exception 'SOLV upstream controller attribution failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Kevin S. Penn';
 if subject->>'biography' is null or jsonb_array_length(subject->'ownershipGrid')<>8
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}'='reported_beneficial_owner')<>4
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}' is null and x->>'reportedTotal' is null)<>4
  then raise exception 'SOLV director dash/deemed-owner distinction failed'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='SOLV Energy Management Holdings LP';
 if holder->>'kind'<>'organization' or jsonb_array_length(holder->'ownershipGrid')<>4
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal'='25164146')<>2
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal' is null)<>2
  then raise exception 'SOLV Management Holdings Class A dash/Class B total failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Benjamin Catalano';
 if subject->>'biography' is not null or jsonb_array_length(subject->'ownershipGrid')<>4
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x->>'reportedTotal'='1229448')<>2
  then raise exception 'SOLV former executive visibility or holdings failed'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and shares=13275526)
  then raise exception 'SOLV overlapping nineteen-person aggregate was imported'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='George Hershman';
 r:=public.ipo_roll_request_liquidity(offering,(subject->>'id')::uuid,'89910000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.4' or jsonb_array_length(r->'positions')<>4
  or exists(select 1 from jsonb_array_elements(r->'positions') x where x->>'category'<>'unknown' or x->>'marketValue' is not null)
  then raise exception 'SOLV private report promoted projected Up-C holdings or a market value'; end if;
 perform set_config('solv.report',r->>'id',true);
end $$;

select set_config('request.jwt.claims','{"sub":"89900000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
 or exists(select 1 from app.liquidity_reports where id=current_setting('solv.report')::uuid)
 then raise exception 'Cross-account SOLV report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89900000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('944df127-9e7b-5b01-a1ba-a8c799cbdf50') is not null then raise exception 'Internal SOLV research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(current_setting('solv.report')::uuid,gen_random_uuid());
  raise exception 'Anonymous guessed SOLV report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline solv_test_state; begin
 select * into baseline from solv_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected SOLV QA report count'; end if;
end $$;
select 'PASS: full SOLV roster, class/basis/null/group/controller distinctions, held overlap and private-report denial' result;
rollback;
