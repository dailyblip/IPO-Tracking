-- Complete reviewed AGI principal-shareholders grid.
-- Classes, pre/base-post alternatives, explicit dashes, duplicate rows and
-- entity-control attribution remain distinct and private.
begin;
create temporary table agi_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89920000-0000-4000-8000-000000000001','agi-a@example.invalid'),
 ('89920000-0000-4000-8000-000000000002','agi-b@example.invalid'),
 ('89920000-0000-4000-8000-000000000003','agi-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89920000-%';
insert into app.reviewers(user_id) values
 ('89920000-0000-4000-8000-000000000001'),('89920000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89920000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; holder jsonb; r jsonb;
 offering constant uuid:='a6935279-ac96-546f-91e2-d762570bcb1b'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>17 then raise exception 'AGI subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id=offering and approved)<>68
  then raise exception 'AGI source positions incomplete'; end if;
 if (select count(*) from research.ownerships where offering_id=offering and approved and shares is null)<>40
  then raise exception 'AGI explicit dash positions incomplete'; end if;
 if (select count(*) from research.biographies b join research.roles rr on rr.person_id=b.person_id where rr.offering_id=offering and b.approved)<>14
  then raise exception 'AGI management biographies incomplete'; end if;
 if (select count(*) from research.ownership_attributions oa join research.ownerships o on o.id=oa.ownership_id where o.offering_id=offering and oa.approved)<>4
  then raise exception 'AGI controller attribution incomplete'; end if;
 if (select count(distinct position_basis) from research.ownerships where offering_id=offering)<>2
  or (select count(distinct share_class) from research.ownerships where offering_id=offering)<>2
  or exists(select 1 from research.ownerships where offering_id=offering and holdings_as_of is not null)
  then raise exception 'AGI basis, class or intentionally unknown holdings date mismatch'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Marciano Testa';
 if subject->>'biography' is null or jsonb_array_length(subject->'ownershipGrid')<>8
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{reportedHolder,name}'='Marciano Testa' and x#>>'{attribution,kind}' is null)<>4
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{reportedHolder,name}'='AGI Partners Limited' and x#>>'{attribution,kind}'='control_authority')<>4
  then raise exception 'AGI Testa aggregate/control distinction failed'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='AGI Partners Limited';
 if holder->>'kind'<>'organization' or jsonb_array_length(holder->'ownershipGrid')<>4
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal'='4993480')<>2
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal'='3684140')<>2
  then raise exception 'AGI Partners two-class positions failed'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x
  where x->>'name'='LCM Bigbang Fundo de Investimento em Participações Multiestratégia Responsabilidade Limitada';
 if jsonb_array_length(holder->'ownershipGrid')<>4
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal'='8045726')<>2
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal' is null)<>2
  then raise exception 'AGI Lumina fund Class A/Class B dash distinction failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Gabriel Felzenszwalb';
 if subject->>'biography' is null or jsonb_array_length(subject->'ownershipGrid')<>4
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x->>'reportedTotal' is not null)
  then raise exception 'AGI director explicit-dash visibility failed'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and shares=3822449)
  then raise exception 'AGI overlapping fourteen-person aggregate was imported'; end if;

 r:=public.ipo_roll_request_liquidity(offering,(holder->>'id')::uuid,'89920000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.4' or jsonb_array_length(r->'positions')<>4
  or exists(select 1 from jsonb_array_elements(r->'positions') x where x->>'category'<>'unknown' or x->>'marketValue' is not null)
  then raise exception 'AGI private report promoted beneficial totals or market value'; end if;
 perform set_config('agi.report',r->>'id',true);
end $$;

select set_config('request.jwt.claims','{"sub":"89920000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
 or exists(select 1 from app.liquidity_reports where id=current_setting('agi.report')::uuid)
 then raise exception 'Cross-account AGI report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89920000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('a6935279-ac96-546f-91e2-d762570bcb1b') is not null then raise exception 'Internal AGI research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(current_setting('agi.report')::uuid,gen_random_uuid());
  raise exception 'Anonymous guessed AGI report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline agi_test_state; begin
 select * into baseline from agi_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected AGI QA report count'; end if;
end $$;
select 'PASS: full AGI class/basis/null/overlap/controller grid and private-report denial' result;
rollback;
