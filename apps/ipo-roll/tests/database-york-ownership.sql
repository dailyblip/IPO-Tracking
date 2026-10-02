-- Complete reviewed York Space Systems table: named people, aggregate holder
-- groups, controller attribution, audited overlap and account-private reports.
-- Disposable accounts/reports always roll back.
begin;
create temporary table york_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('88000000-0000-4000-8000-000000000001','york-a@example.invalid'),
 ('88000000-0000-4000-8000-000000000002','york-b@example.invalid'),
 ('88000000-0000-4000-8000-000000000003','york-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '88000000-%';
insert into app.reviewers(user_id) values
 ('88000000-0000-4000-8000-000000000001'),('88000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"88000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; holder jsonb; r jsonb;
 offering constant uuid:='dee71bb3-ceb8-59b3-94a8-d016fbf74c6e'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>14 then raise exception 'York subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id=offering)<>22 then raise exception 'York source positions incomplete'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Dirk Wallinger';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid')x where x->>'reportedTotal'='11168593')<>1
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid')x where x->'reportedTotal'='null'::jsonb)<>1
  then raise exception 'Dirk pre/post position split failed'; end if;
 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Kirk Konert';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid')x where x->'reportedTotal'<>'null'::jsonb)
  then raise exception 'York filing dashes became quantities or disappeared'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='Entities Affiliated with AE Industrial Partners';
 if holder->>'kind'<>'group' or jsonb_array_length(holder->'ownershipGrid')<>2
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid')x where x->>'reportedTotal' in ('99558713','30196088'))<>2
  then raise exception 'AE Industrial reported group failed'; end if;
 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Michael Greene';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or subject#>>'{ownershipGrid,0,attribution,kind}'<>'control_authority'
  or subject#>>'{ownershipGrid,0,reportedHolder,name}'<>'Entities Affiliated with AE Industrial Partners'
  then raise exception 'AE Industrial controller attribution failed'; end if;
 r:=public.ipo_roll_request_liquidity(offering,(subject->>'id')::uuid,'88100000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.6' or jsonb_array_length(r->'positions')<>2
  or exists(select 1 from jsonb_array_elements(r->'positions')x where x->>'category'<>'unknown')
  or r#>>'{positions,0,attribution,kind}'<>'control_authority'
  then raise exception 'York controller private report promoted or incomplete'; end if;
 perform set_config('york.report',r->>'id',true);

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='Entities Affiliated with BlackRock';
 if holder->>'kind'<>'group' or jsonb_array_length(holder->'ownershipGrid')<>2
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid')x where x->>'reportedTotal'='17094434')<>1
  then raise exception 'BlackRock aggregate group failed'; end if;
end $$;

select set_config('request.jwt.claims','{"sub":"88000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports) or exists(select 1 from app.liquidity_reports where id=current_setting('york.report')::uuid)
  then raise exception 'Cross-account York report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"88000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('dee71bb3-ceb8-59b3-94a8-d016fbf74c6e') is not null then raise exception 'Internal York research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(gen_random_uuid(),gen_random_uuid());
  raise exception 'Anonymous private report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline york_test_state; begin
 select * into baseline from york_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected York QA report count'; end if;
end $$;
select 'PASS: full York holder grid, audited overlap, aggregate groups, controller attribution and private-report denial' result;
rollback;
