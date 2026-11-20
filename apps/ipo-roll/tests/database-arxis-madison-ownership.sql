-- Current-source management/ownership backfill QA. All disposable data rolls back.
begin;
create temporary table am_prior_reports as select id,to_jsonb(r) body from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('88000000-0000-4000-8000-000000000001','am-a@example.invalid'),
 ('88000000-0000-4000-8000-000000000002','am-b@example.invalid'),
 ('88000000-0000-4000-8000-000000000003','am-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '88000000-%';
insert into app.reviewers(user_id) values ('88000000-0000-4000-8000-000000000001'),('88000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"88000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; entity jsonb; r jsonb; again jsonb; begin
 d:=public.ipo_roll_detail('52c64385-d676-5305-ae2d-520638003939');
 if jsonb_array_length(d->'people')<>10 or (select count(*) from jsonb_array_elements(d->'people') x where x->>'biography' is not null)<>9 then raise exception 'Arxis roster/bios incomplete'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Rajeev Amara';
 if jsonb_array_length(subject->'ownershipGrid')<>12 then raise exception 'Arxis controller attribution missing'; end if;
 select x into strict entity from jsonb_array_elements(d->'people') x where x->>'name'='Arcline Investment Management';
 if entity->>'kind'<>'organization' or jsonb_array_length(entity->'ownershipGrid')<>6 then raise exception 'Arxis entity/classes lost'; end if;
 if not exists(select 1 from jsonb_array_elements(entity->'ownershipGrid') p where p->>'shareClass'='Class B Common Stock' and p->>'positionBasis'='pre' and p->>'reportedTotal'='340676786') then raise exception 'Arxis source quantity mismatch'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Jason Roth';
 if subject->>'biography' not like '%Jason Roth%' or length(subject->>'biography')<500 then raise exception 'Arxis biography continuation lost'; end if;
 d:=public.ipo_roll_detail('16d79814-ff9b-5080-8170-0b4752112ca1');
 if jsonb_array_length(d->'people')<>19 or (select count(*) from jsonb_array_elements(d->'people') x where x->>'biography' is not null)<>15 then raise exception 'Madison roster/bios incomplete'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Larry Gies';
 if jsonb_array_length(subject->'ownershipGrid')<>8 then raise exception 'Madison controller lost or overlapping personal row added'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Ernesto Bertarelli';
 if subject->>'biography' is not null or jsonb_array_length(subject->'ownershipGrid')<>4 then raise exception 'Missing-bio owner dropped or biography fabricated'; end if;
 select x into strict entity from jsonb_array_elements(d->'people') x where x->>'name'='Kedge';
 if entity->>'kind'<>'group' then raise exception 'Two-fund aggregate mislabeled'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Jill Wyant';
 if not exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') p where p->>'positionBasis'='pre' and p->>'shareClass'='Class A common stock' and p->>'reportedTotal'='1123711' and p->>'holdingsAsOf'='2026-04-06') then raise exception 'Madison excluded awards added or basis lost'; end if;
 r:=public.ipo_roll_request_liquidity('16d79814-ff9b-5080-8170-0b4752112ca1',(subject->>'id')::uuid,'88100000-0000-4000-8000-000000000001');
 if jsonb_array_length(r->'positions')<>4 or exists(select 1 from jsonb_array_elements(r->'positions') p where p->>'category'<>'unknown' or p->>'marketValue' is not null) then raise exception 'Unsupported value/liquidity inferred'; end if;
 again:=public.ipo_roll_request_liquidity('16d79814-ff9b-5080-8170-0b4752112ca1',(subject->>'id')::uuid,'88100000-0000-4000-8000-000000000002');
 if r<>again then raise exception 'Repeated request regenerated static report'; end if;
 perform set_config('am.report',r->>'id',true);
end $$;
select set_config('request.jwt.claims','{"sub":"88000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports where id=current_setting('am.report')::uuid) or exists(select 1 from app.liquidity_reports) then raise exception 'Cross-account report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"88000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('52c64385-d676-5305-ae2d-520638003939') is not null or public.ipo_roll_detail('16d79814-ff9b-5080-8170-0b4752112ca1') is not null then raise exception 'Internal review source exposed to ordinary customer'; end if;
end $$;
reset role;
do $$ begin
 if exists(select 1 from am_prior_reports p left join app.liquidity_reports r on r.id=p.id where r.id is null or p.body<>to_jsonb(r)) then raise exception 'Saved private report changed'; end if;
end $$;
select 'PASS: Arxis/Madison rosters, class/basis totals, control attribution, unknown valuation, static reports, account isolation and ordinary-customer denial' result;
rollback;
