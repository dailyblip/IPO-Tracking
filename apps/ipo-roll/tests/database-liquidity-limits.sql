-- Database-bound report limits cover both direct Data API inserts and the RPC.
-- Disposable identities and rows are always rolled back.
begin;
insert into auth.users(id,email) values
 ('64000000-0000-4000-8000-000000000001','limits-subject@example.invalid'),
 ('64000000-0000-4000-8000-000000000002','limits-user@example.invalid');
insert into app.entitlements(user_id,active) values
 ('64000000-0000-4000-8000-000000000001',true),
 ('64000000-0000-4000-8000-000000000002',true);
insert into app.reviewers(user_id) values
 ('64000000-0000-4000-8000-000000000001'),
 ('64000000-0000-4000-8000-000000000002');
create temporary table liquidity_limit_subject as
 select r.offering_id,r.person_id from research.roles r
 where evidence.source_json(r.evidence_id) is not null order by r.offering_id,r.person_id limit 1;
grant select on liquidity_limit_subject to authenticated;

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"64000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare s record; latest_id uuid; n integer; begin
 select * into s from liquidity_limit_subject;
 if s.offering_id is null then raise exception 'No subject fixture'; end if;
 for n in 1..10 loop
  insert into app.liquidity_reports(offering_id,person_id,request_id)
  values(s.offering_id,s.person_id,gen_random_uuid());
 end loop;
 begin
  insert into app.liquidity_reports(offering_id,person_id,request_id)
  values(s.offering_id,s.person_id,gen_random_uuid());
  raise exception 'Direct insert exceeded subject quota' using errcode='ZX001';
 exception when program_limit_exceeded then
  if sqlerrm<>'Liquidity report subject quota reached' then raise; end if;
 end;
 select id into latest_id from app.liquidity_reports order by created_at desc,id desc limit 1;
 if public.ipo_roll_request_liquidity(s.offering_id,s.person_id,gen_random_uuid())->>'id' <> latest_id::text then
  raise exception 'Quota blocked reopening the saved report';
 end if;
 begin perform * from app.liquidity_report_accounts;
  raise exception 'Private mutex table exposed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
 begin perform app.enforce_liquidity_report_quota();
  raise exception 'Quota trigger directly callable' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
 begin
  perform public.ipo_roll_request_liquidity(s.offering_id,s.person_id,gen_random_uuid(),latest_id);
  raise exception 'RPC exceeded subject quota' using errcode='ZX001';
 exception when program_limit_exceeded then
  if sqlerrm<>'Liquidity report subject quota reached' then raise; end if;
 end;
end $$;
reset role;

-- Seed the second synthetic account as an administrator so the next
-- authenticated insert reaches the independent account-wide boundary.
alter table app.liquidity_reports disable trigger liquidity_report_quota;
alter table app.liquidity_reports disable trigger liquidity_report_snapshot;
insert into app.liquidity_reports(user_id,offering_id,person_id,request_id,created_at,report)
 select '64000000-0000-4000-8000-000000000002',s.offering_id,s.person_id,
  gen_random_uuid(),clock_timestamp(),'{}'::jsonb
 from liquidity_limit_subject s cross join generate_series(1,100);
alter table app.liquidity_reports enable trigger liquidity_report_snapshot;
alter table app.liquidity_reports enable trigger liquidity_report_quota;
create policy test_hide_liquidity_reports on app.liquidity_reports as restrictive for select to authenticated using(false);
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"64000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ declare s record; begin
 select * into s from liquidity_limit_subject;
 begin
  insert into app.liquidity_reports(offering_id,person_id,request_id)
  values(s.offering_id,s.person_id,gen_random_uuid());
  raise exception 'Direct insert exceeded daily quota' using errcode='ZX001';
 exception when program_limit_exceeded then
  if sqlerrm<>'Liquidity report daily quota reached' then raise; end if;
 end;
end $$;
reset role;
select 'PASS: direct/RPC quotas, reopen at quota, internal ACLs, hidden reports still counted' result;
rollback;
