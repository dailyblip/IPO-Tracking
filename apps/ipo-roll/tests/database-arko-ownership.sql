-- ARKO projected class grid: retain explicit dashes and hold out the
-- overlapping Class A conversion scenario. Saved reports remain private.
begin;
create temporary table arko_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89930000-0000-4000-8000-000000000001','arko-a@example.invalid'),
 ('89930000-0000-4000-8000-000000000002','arko-b@example.invalid'),
 ('89930000-0000-4000-8000-000000000003','arko-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89930000-%';
insert into app.reviewers(user_id) values
 ('89930000-0000-4000-8000-000000000001'),('89930000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89930000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; holder jsonb; r jsonb;
 offering constant uuid:='834536a8-8476-59db-ba61-f62daab71a5b'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>9 then raise exception 'ARKO subject roster incomplete'; end if;
 if (select count(*) from research.ownerships where offering_id=offering and approved)<>17
  or (select count(*) from research.ownerships where offering_id=offering and shares is null)<>16
  then raise exception 'ARKO explicit undisclosed positions incomplete'; end if;
 if (select count(distinct b.person_id) from research.biographies b join research.roles rr on rr.person_id=b.person_id where rr.offering_id=offering and b.approved)<>8
  then raise exception 'ARKO management biographies incomplete'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and (position_basis<>'post' or holdings_as_of is not null))
  then raise exception 'ARKO projected basis or unknown date lost'; end if;
 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='ARKO Corp.';
 if holder->>'kind'<>'organization' or jsonb_array_length(holder->'ownershipGrid')<>1
  or (holder->'ownershipGrid'->0->>'reportedTotal')<>'35000000'
  or (holder->'ownershipGrid'->0->>'shareClass')<>'Class B common stock'
  then raise exception 'ARKO conversion amount double counted or parent class lost'; end if;
 if (select sum(shares) from research.ownerships where offering_id=offering)<>35000000
  then raise exception 'ARKO conversion overlap imported'; end if;
 r:=public.ipo_roll_request_liquidity(offering,(holder->>'id')::uuid,'89930000-0000-4000-8000-000000000001');
 if jsonb_array_length(r->'positions')<>1
  or exists(select 1 from jsonb_array_elements(r->'positions') x where x->>'category'<>'unknown' or x->>'marketValue' is not null)
  then raise exception 'ARKO source totals promoted to liquidity or market value'; end if;
 perform set_config('arko.report',r->>'id',true);
end $$;

select set_config('request.jwt.claims','{"sub":"89930000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
 or exists(select 1 from app.liquidity_reports where id=current_setting('arko.report')::uuid)
 then raise exception 'Cross-account ARKO report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89930000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('834536a8-8476-59db-ba61-f62daab71a5b') is not null then raise exception 'Internal ARKO research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(current_setting('arko.report')::uuid,gen_random_uuid());
  raise exception 'Anonymous guessed ARKO report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline arko_test_state; begin
 select * into baseline from arko_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected ARKO QA report count'; end if;
end $$;
select 'PASS: ARKO projected/null/conversion grid and private-report denial' result;
rollback;
