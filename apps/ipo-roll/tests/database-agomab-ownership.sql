-- Complete reviewed AgomAb principal-shareholders table and named controller links.
-- Less-than-one-percent markers remain explicit unknowns; repeated fund/person rows and
-- the overlapping aggregate stay held. Disposable private reports and test identities roll back.
begin;
create temporary table agomab_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89900000-0000-4000-8000-000000000001','agomab-a@example.invalid'),
 ('89900000-0000-4000-8000-000000000002','agomab-b@example.invalid'),
 ('89900000-0000-4000-8000-000000000003','agomab-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89900000-%';
insert into app.reviewers(user_id) values
 ('89900000-0000-4000-8000-000000000001'),('89900000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89900000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; holder jsonb; r jsonb;
 offering constant uuid:='96ff3747-bf52-5767-834e-c3ec5427a836'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>40 then raise exception 'AgomAb subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id=offering)<>26 then raise exception 'AgomAb source positions incomplete'; end if;
 if (select count(*) from research.biographies b join research.roles rr on rr.person_id=b.person_id where rr.offering_id=offering and b.approved)<>11
  then raise exception 'AgomAb management biographies incomplete'; end if;
 if (select count(*) from research.ownership_attributions oa join research.ownerships o on o.id=oa.ownership_id where o.offering_id=offering and oa.approved)<>44
  then raise exception 'AgomAb holder-person attributions incomplete'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and holdings_as_of<>'2025-12-31')
  or (select count(distinct position_basis) from research.ownerships where offering_id=offering)<>2
  then raise exception 'AgomAb date or basis mismatch'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='LSP 7 Coöperatief U.A.';
 if holder->>'kind'<>'organization' or jsonb_array_length(holder->'ownershipGrid')<>2
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal'='4016992')<>2
  then raise exception 'AgomAb LSP organization failed or was duplicated'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Felice Verduyn—van Weegen';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}'='reported_beneficial_owner')<>2
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{reportedHolder,name}'<>'LSP 7 Coöperatief U.A.')
  then raise exception 'Felice repeated LSP row was duplicated or attribution failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Ming Fang';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}'='reported_beneficial_owner')<>2
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{reportedHolder,name}'<>'Redmile Biopharma Investments III, L.P.')
  then raise exception 'Ming repeated Redmile row was duplicated or attribution failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Brenton K. Ahrens';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}'='control_authority')<>2
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{reportedHolder,name}'<>'Canaan XII L.P.')
  then raise exception 'Canaan controller attribution failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='David R. Epstein';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x->>'reportedTotal' is not null)
  then raise exception 'AgomAb less-than-one-percent marker was promoted or omitted'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Tim Knotnerus';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x->>'reportedTotal'='668855')<>2
  or exists(select 1 from research.ownership_components c join research.ownerships o on o.id=c.ownership_id where o.offering_id=offering and o.party_id=(subject->>'id')::uuid)
  then raise exception 'Tim reported total/discrepant components were changed or duplicated'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and shares=10978838)
  then raise exception 'Overlapping twelve-person aggregate was imported'; end if;

 r:=public.ipo_roll_request_liquidity(offering,(subject->>'id')::uuid,'89910000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.4' or jsonb_array_length(r->'positions')<>2
  or exists(select 1 from jsonb_array_elements(r->'positions') x where x->>'category'<>'unknown' or x->>'marketValue' is not null)
  then raise exception 'AgomAb private report promoted unknown holdings'; end if;
 perform set_config('agomab.report',r->>'id',true);
end $$;

select set_config('request.jwt.claims','{"sub":"89900000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
 or exists(select 1 from app.liquidity_reports where id=current_setting('agomab.report')::uuid)
 then raise exception 'Cross-account AgomAb report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89900000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('96ff3747-bf52-5767-834e-c3ec5427a836') is not null then raise exception 'Internal AgomAb research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(current_setting('agomab.report')::uuid,gen_random_uuid());
  raise exception 'Anonymous guessed AgomAb report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline agomab_test_state; begin
 select * into baseline from agomab_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected AgomAb QA report count'; end if;
end $$;
select 'PASS: full AgomAb table, star/null semantics, audited overlaps, controller distinctions and private-report denial' result;
rollback;

