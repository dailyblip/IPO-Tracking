-- HMH full roster and selected non-overlapping ownership columns.
-- Disposable accounts and private-report writes are rolled back.
begin;
create temporary table hmh_test_state as select count(*) reports from app.liquidity_reports;
insert into auth.users(id,email) values
 ('87000000-0000-4000-8000-000000000001','hmh-a@example.invalid'),
 ('87000000-0000-4000-8000-000000000002','hmh-b@example.invalid'),
 ('87000000-0000-4000-8000-000000000003','hmh-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '87000000-%';
insert into app.reviewers(user_id) values
 ('87000000-0000-4000-8000-000000000001'),('87000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"87000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; entity jsonb; r jsonb;
 offering constant uuid:='2ffecdbe-0b15-5213-9b8d-6634d3a3ebba'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>15 then raise exception 'HMH roster/holder count incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from jsonb_array_elements(d->'people') x where x->>'biography' is not null)<>13
  then raise exception 'HMH complete biography count is not 13'; end if;
 if (select count(distinct x->>'id') from jsonb_array_elements(d->'people') x)<>15
  then raise exception 'HMH detail contains duplicate subjects'; end if;
 if (select coalesce(sum(jsonb_array_length(x->'ownershipGrid')),0) from jsonb_array_elements(d->'people') x)<>36
  then raise exception 'HMH selected position count is not 36'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Eirik Bergsvik';
 if jsonb_array_length(subject->'ownershipGrid')<>3
  or not exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') p
    where p->>'shareClass'='Class A common stock' and p->>'positionBasis'='post'
      and p->>'reportedTotal'='90127' and p->>'holdingsAsOf'='2026-03-23')
  then raise exception 'HMH conditional executive position lost: %',subject->'ownershipGrid'; end if;
 select x into strict entity from jsonb_array_elements(d->'people') x where x->>'name'='Baker Hughes Holdings LLC';
 if entity->>'kind'<>'organization' or jsonb_array_length(entity->'ownershipGrid')<>3
  or not exists(select 1 from jsonb_array_elements(entity->'ownershipGrid') p
    where p->>'shareClass'='Class B common stock' and p->>'positionBasis'='post'
      and p->>'reportedTotal'='16288748')
  then raise exception 'HMH principal stockholder positions lost: %',entity; end if;
 if exists(select 1 from jsonb_array_elements(d->'people') x,
    jsonb_array_elements(x->'ownershipGrid') p where p->>'marketValue' is not null)
  then raise exception 'HMH detail invented market value'; end if;
 r:=public.ipo_roll_request_liquidity(offering,(subject->>'id')::uuid,'87100000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.6' or jsonb_array_length(r->'positions')<>3
  or exists(select 1 from jsonb_array_elements(r->'positions') p
    where p->>'category'<>'unknown' or p->>'marketValue' is not null)
  then raise exception 'HMH report promoted conditional awards or value: %',r; end if;
 perform set_config('hmh.report',r->>'id',true);
end $$;
select set_config('request.jwt.claims','{"sub":"87000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
  or exists(select 1 from app.liquidity_reports where id=current_setting('hmh.report')::uuid)
 then raise exception 'Cross-account HMH report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"87000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('2ffecdbe-0b15-5213-9b8d-6634d3a3ebba') is not null
  then raise exception 'Internal HMH research exposed'; end if;
end $$;
reset role;
do $$ declare before_count bigint; begin
 select reports into before_count from hmh_test_state;
 if (select count(*) from app.liquidity_reports)<>before_count+1
  then raise exception 'Unexpected HMH private report mutation'; end if;
end $$;
select 'PASS: HMH 13-person biography roster, 36 selected positions, conditional-award safeguards, private report isolation and customer denial' result;
rollback;
