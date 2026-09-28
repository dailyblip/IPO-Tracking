-- MiniMed final 424B4 management and principal-stockholder coverage.
-- Preserve null disclosures, the indeterminable RSU conversion, and alternatives.
begin;
create temporary table minimed_ownership_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89950000-0000-4000-8000-000000000001','minimed-ownership-a@example.invalid'),
 ('89950000-0000-4000-8000-000000000002','minimed-ownership-b@example.invalid'),
 ('89950000-0000-4000-8000-000000000003','minimed-ownership-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89950000-%';
insert into app.reviewers(user_id) values
 ('89950000-0000-4000-8000-000000000001'),('89950000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89950000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; holder jsonb; subject jsonb; r jsonb;
 offering constant uuid:='723a882e-2690-5bba-ad83-7ef8fde0259b'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>14 then raise exception 'MiniMed subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id=offering and approved)<>28
  or (select count(*) from research.liquidity_assessments a join research.ownerships o on o.id=a.ownership_id
      where o.offering_id=offering and a.reviewed and a.classification='unknown')<>28
  then raise exception 'MiniMed positions or reviewed unknowns incomplete'; end if;
 if (select count(distinct b.person_id) from research.biographies b join research.roles rr on rr.person_id=b.person_id
     where rr.offering_id=offering and b.approved)<>13
  then raise exception 'MiniMed management biographies incomplete'; end if;
 if (select count(distinct position_basis) from research.ownerships where offering_id=offering)<>2
  or (select count(*) from research.ownerships where offering_id=offering and shares=252813348)<>2
  or (select count(*) from research.ownerships where offering_id=offering and shares is null)<>26
  then raise exception 'MiniMed selected bases or null quantities mismatch'; end if;
 if exists(select 1 from research.parties p join research.ownerships o on o.party_id=p.id
           where o.offering_id=offering and p.name like 'All Directors and Executive Officers%')
  then raise exception 'MiniMed overlapping aggregate was imported'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='Medtronic plc';
 if holder->>'kind'<>'organization' or jsonb_array_length(holder->'ownershipGrid')<>2
  or exists(select 1 from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal'<>'252813348')
  then raise exception 'MiniMed parent organization snapshots failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Que Dallara';
 if subject->>'biography' is null or jsonb_array_length(subject->'ownershipGrid')<>2
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x->>'reportedTotal' is not null)
  then raise exception 'MiniMed indeterminable Dallara quantities failed'; end if;
 r:=public.ipo_roll_request_liquidity(offering,(subject->>'id')::uuid,'89950000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.4' or jsonb_array_length(r->'positions')<>2
  or exists(select 1 from jsonb_array_elements(r->'positions') x
            where x->>'category'<>'unknown' or x->>'marketValue' is not null or x->>'historicalIpoValue' is not null)
  then raise exception 'MiniMed private report promoted null RSU quantities to value or liquidity'; end if;
 perform set_config('minimed_ownership.report',r->>'id',true);
end $$;

select set_config('request.jwt.claims','{"sub":"89950000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
 or exists(select 1 from app.liquidity_reports where id=current_setting('minimed_ownership.report')::uuid)
 then raise exception 'Cross-account MiniMed report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89950000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('723a882e-2690-5bba-ad83-7ef8fde0259b') is not null then raise exception 'Internal MiniMed research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(current_setting('minimed_ownership.report')::uuid,gen_random_uuid());
  raise exception 'Anonymous guessed MiniMed report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline minimed_ownership_test_state; begin
 select * into baseline from minimed_ownership_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected MiniMed QA report count'; end if;
end $$;
select 'PASS: MiniMed complete biographies, parent ownership, null rows, indeterminable RSUs and private-report denial' result;
rollback;
