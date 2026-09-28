-- Generate Biomedicines final 424B4 beneficial-ownership table.
-- Preserve before/after alternatives, mixed instruments and Flagship attribution.
begin;
create temporary table generate_ownership_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89940000-0000-4000-8000-000000000001','generate-ownership-a@example.invalid'),
 ('89940000-0000-4000-8000-000000000002','generate-ownership-b@example.invalid'),
 ('89940000-0000-4000-8000-000000000003','generate-ownership-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89940000-%';
insert into app.reviewers(user_id) values
 ('89940000-0000-4000-8000-000000000001'),('89940000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89940000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; holder jsonb; subject jsonb; r jsonb;
 offering constant uuid:='b6ec0026-e141-5efa-abe9-59c2ab75306d'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>16 then raise exception 'Generate subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id=offering and approved)<>24
  or (select count(*) from research.ownership_attributions oa join research.ownerships o on o.id=oa.ownership_id where o.offering_id=offering and oa.approved)<>2
  then raise exception 'Generate source positions or Flagship attribution incomplete'; end if;
 if (select count(distinct b.person_id) from research.biographies b join research.roles rr on rr.person_id=b.person_id where rr.offering_id=offering and b.approved)<>15
  then raise exception 'Generate management biographies incomplete'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and
    (holdings_as_of<>date '2026-01-15' or share_class<>'common stock' or shares is null))
  or (select count(distinct position_basis) from research.ownerships where offering_id=offering)<>2
  then raise exception 'Generate date, class, quantity or basis mismatch'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='Entities affiliated with Flagship Funds';
 if holder->>'kind'<>'group' or jsonb_array_length(holder->'ownershipGrid')<>2
  or exists(select 1 from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal'<>'57985617')
  then raise exception 'Generate Flagship group snapshots failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Dr. Noubar B. Afeyan, Ph.D.';
 if subject->>'biography' is null or jsonb_array_length(subject->'ownershipGrid')<>4
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}'='control_authority')<>2
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{reportedHolder,name}'='Entities affiliated with Flagship Funds')<>2
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}' is null and x->>'reportedTotal'='58010304')<>2
  then raise exception 'Generate Afeyan direct/control overlap distinction failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Dr. Jason Silvers, M.D., J.D.';
 if subject->>'biography' is null or jsonb_array_length(subject->'ownershipGrid')<>2
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x->>'reportedTotal'<>'950132')
  then raise exception 'Generate option-only reported total failed'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and shares=70219989)
  then raise exception 'Generate overlapping fifteen-person aggregate was imported'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Dr. Noubar B. Afeyan, Ph.D.';
 r:=public.ipo_roll_request_liquidity(offering,(subject->>'id')::uuid,'89940000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.4' or jsonb_array_length(r->'positions')<>4
  or exists(select 1 from jsonb_array_elements(r->'positions') x where x->>'category'<>'unknown' or x->>'marketValue' is not null)
  then raise exception 'Generate private report promoted mixed or attributed totals to liquidity/value'; end if;
 perform set_config('generate_ownership.report',r->>'id',true);
end $$;

select set_config('request.jwt.claims','{"sub":"89940000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
 or exists(select 1 from app.liquidity_reports where id=current_setting('generate_ownership.report')::uuid)
 then raise exception 'Cross-account Generate report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89940000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('b6ec0026-e141-5efa-abe9-59c2ab75306d') is not null then raise exception 'Internal Generate research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(current_setting('generate_ownership.report')::uuid,gen_random_uuid());
  raise exception 'Anonymous guessed Generate report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline generate_ownership_test_state; begin
 select * into baseline from generate_ownership_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected Generate QA report count'; end if;
end $$;
select 'PASS: Generate complete biographies, before/after totals, mixed instruments, Flagship control overlap and private-report denial' result;
rollback;
