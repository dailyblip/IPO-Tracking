-- Complete Generate Biomedicines management and director biographies.
-- Source-supported institution text remains searchable without special branding.
begin;
create temporary table gen_report_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89940000-0000-4000-8000-000000000001','gen-reviewer@example.invalid'),
 ('89940000-0000-4000-8000-000000000002','gen-customer@example.invalid');
insert into app.entitlements(user_id,active) values
 ('89940000-0000-4000-8000-000000000001',true),
 ('89940000-0000-4000-8000-000000000002',true);
insert into app.reviewers(user_id) values ('89940000-0000-4000-8000-000000000001');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89940000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; s jsonb; begin
 d:=public.ipo_roll_detail('b6ec0026-e141-5efa-abe9-59c2ab75306d');
 if jsonb_array_length(d->'people')<>15 then raise exception 'Generate roster incomplete'; end if;
 if (select count(distinct r.person_id) from research.roles r where r.offering_id='b6ec0026-e141-5efa-abe9-59c2ab75306d' and r.verified)<>15
  then raise exception 'Generate roles incomplete'; end if;
 if (select count(distinct b.person_id) from research.biographies b join research.roles r on r.person_id=b.person_id where r.offering_id='b6ec0026-e141-5efa-abe9-59c2ab75306d' and b.approved and r.verified)<>15
  then raise exception 'Generate biographies incomplete'; end if;
 s:=public.ipo_roll_people_search('Stanford University School of Medicine');
 if not exists(select 1 from jsonb_array_elements(s->'items') x where x#>>'{person,name}'='Aarif Khakoo, M.D., M.B.A.')
  then raise exception 'Generate person-specific source biography not searchable'; end if;
 s:=public.ipo_roll_people_search('University of Michigan');
 if not exists(select 1 from jsonb_array_elements(s->'items') x where x#>>'{person,name}'='Sean Martin, J.D.')
  then raise exception 'Generate Michigan biography not searchable'; end if;
 if (public.ipo_roll_people_search('Stanford University School of Medicine','Beneficial owner')->>'total')::int<>0
  then raise exception 'Executive inferred to own shares'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89940000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('b6ec0026-e141-5efa-abe9-59c2ab75306d') is not null then raise exception 'Generate internal detail leaked'; end if;
 if (public.ipo_roll_people_search('Stanford University School of Medicine')->>'total')::int<>0 then raise exception 'Generate biography leaked'; end if;
end $$;
reset role;
do $$ declare s gen_report_state; begin
 select * into s from gen_report_state;
 if (select count(*) from app.liquidity_reports)<>s.reports
  or (select md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) from app.liquidity_reports r)<>s.checksum
 then raise exception 'Private reports changed'; end if;
end $$;
select 'PASS: Generate complete biographies, neutral evidence search and customer denial' result;
rollback;
