-- Complete reviewed Ethos table: direct holders, entity/group rows, controllers,
-- audited duplicates and SEC-reported beneficial-owner attribution.
-- Disposable accounts/reports always roll back.
begin;
create temporary table ethos_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('87000000-0000-4000-8000-000000000001','ethos-a@example.invalid'),
 ('87000000-0000-4000-8000-000000000002','ethos-b@example.invalid'),
 ('87000000-0000-4000-8000-000000000003','ethos-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '87000000-%';
insert into app.reviewers(user_id) values
 ('87000000-0000-4000-8000-000000000001'),('87000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"87000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; holder jsonb; r jsonb;
 offering constant uuid:='033718b9-242e-5d02-b0de-16ae4ce39d31'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>42 then raise exception 'Ethos subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id=offering)<>53 then raise exception 'Ethos source positions incomplete'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Peter Colis';
 if jsonb_array_length(subject->'ownershipGrid')<>2 then raise exception 'Repeated Peter row was double counted or lost'; end if;
 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Roelof Botha';
 if jsonb_array_length(subject->'ownershipGrid')<>3
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid')x where x#>>'{reportedHolder,name}'='Entities affiliated with Sequoia Capital')<>2
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid')x where x#>>'{reportedHolder,name}'='Roelof Botha' and x->>'reportedTotal'='260525')<>1
  then raise exception 'Roelof entity attribution/direct purchase split failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Nathan J. Niparko';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or subject#>>'{ownershipGrid,0,attribution,kind}'<>'reported_beneficial_owner'
  or subject#>>'{ownershipGrid,0,reportedHolder,name}'<>'Entities affiliated with Accel'
  then raise exception 'Niparko repeated SEC holder attribution failed'; end if;
 r:=public.ipo_roll_request_liquidity(offering,(subject->>'id')::uuid,'87100000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.4' or jsonb_array_length(r->'positions')<>2
  or exists(select 1 from jsonb_array_elements(r->'positions')x where x->>'category'<>'unknown')
  or r#>>'{positions,0,attribution,kind}'<>'reported_beneficial_owner'
  then raise exception 'Reported-beneficial-owner private report promoted or incomplete'; end if;
 perform set_config('ethos.report',r->>'id',true);

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Andrew G. Braccia';
 if jsonb_array_length(subject->'ownershipGrid')<>2 or subject#>>'{ownershipGrid,0,attribution,kind}'<>'control_authority'
  then raise exception 'Accel controller attribution failed'; end if;
 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='General Catalyst Group X – Endurance, L.P.';
 if holder->>'kind'<>'organization' or jsonb_array_length(holder->'ownershipGrid')<>2 then raise exception 'Organization holder missing'; end if;
 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='Other selling stockholders: 10,001–50,000 share range';
 if holder->>'kind'<>'group' or jsonb_array_length(holder->'ownershipGrid')<>2 then raise exception 'Anonymous holder group missing'; end if;
end $$;

select set_config('request.jwt.claims','{"sub":"87000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports) or exists(select 1 from app.liquidity_reports where id=current_setting('ethos.report')::uuid)
  then raise exception 'Cross-account report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"87000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('033718b9-242e-5d02-b0de-16ae4ce39d31') is not null then raise exception 'Internal Ethos research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(gen_random_uuid(),gen_random_uuid());
  raise exception 'Anonymous private report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline ethos_test_state; begin
 select * into baseline from ethos_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected QA report count'; end if;
end $$;
select 'PASS: full Ethos holder grid, audited overlap, entity/group/control/reporting attribution and private-report denial' result;
rollback;
