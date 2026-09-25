-- Disposable identities and synthetic ownership fixtures; always rolled back.
begin;
insert into auth.users(id,email) values('60000000-0000-4000-8000-000000000001','liquidity-a@example.invalid'),('60000000-0000-4000-8000-000000000002','liquidity-b@example.invalid'),('60000000-0000-4000-8000-000000000003','liquidity-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id in ('60000000-0000-4000-8000-000000000001','60000000-0000-4000-8000-000000000002','60000000-0000-4000-8000-000000000003');
insert into app.reviewers(user_id) values('60000000-0000-4000-8000-000000000001'),('60000000-0000-4000-8000-000000000002');
create temporary table liquidity_test_subject as select r.offering_id,r.person_id,r.evidence_id,o.current_filing_id from research.roles r join research.offerings o on o.id=r.offering_id where o.stage='Priced' and not exists(select 1 from research.ownerships h where h.offering_id=r.offering_id and h.party_id=r.person_id) limit 1;
grant select on liquidity_test_subject to authenticated;
insert into research.ownerships(id,offering_id,party_id,filing_id,share_class,position_basis,shares,source_row_key,evidence_id,approved)
 select ('61000000-0000-4000-8000-'||lpad(n::text,12,'0'))::uuid,offering_id,person_id,current_filing_id,'Test class '||n,'post',100,'liquidity-test-'||n,evidence_id,true from liquidity_test_subject cross join generate_series(1,5) n;
insert into research.liquidity_assessments(ownership_id,reviewed,assessed_on,valid_through,classification,current_position_confirmed,personal_interest_confirmed,lockup_end,explanation,evidence_ids)
 select ('61000000-0000-4000-8000-'||lpad(n::text,12,'0'))::uuid,true,current_date-1,case when n=5 then current_date-1 else current_date+1 end,
 case when n in(1,4) then 'liquid' when n=2 then 'future' else 'illiquid' end,n<>4,true,
 case when n in(2,4) then current_date+180 else null end,'Synthetic assessment fixture',array[evidence_id]
 from liquidity_test_subject cross join generate_series(1,5)n;
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"60000000-0000-4000-8000-000000000001","role":"authenticated","is_anonymous":false}',true);
do $$ declare s record; r jsonb; r2 jsonb; begin
 select * into s from liquidity_test_subject;
 if s.offering_id is null then raise exception 'No subject fixture'; end if;
 if public.ipo_roll_liquidity_report(s.offering_id,s.person_id) is not null then raise exception 'Pre-existing report'; end if;
 r:=public.ipo_roll_request_liquidity(s.offering_id,s.person_id,'62000000-0000-4000-8000-000000000001');
 if jsonb_array_length(r->'positions')<>5 then raise exception 'Missing fixture positions'; end if;
 if (select count(*) from jsonb_array_elements(r->'positions')x where x->>'category'='unknown')<>2 then raise exception 'Stale/unconfirmed holdings not held'; end if;
 if (select count(*) from jsonb_array_elements(r->'positions')x where x->>'category'='liquid')<>1 then raise exception 'Liquid classification wrong'; end if;
 if exists(select 1 from jsonb_array_elements(r->'positions')x where x->>'marketValue' is not null) then raise exception 'Invented value'; end if;
 if r->>'version'<>'liquidity/1.3' or exists(select 1 from jsonb_array_elements(r->'positions')x where x->>'holdingsAsOf' is not null or x->>'filingDate' is null) then raise exception 'Filing date used as holdings date'; end if;
 r2:=public.ipo_roll_request_liquidity(s.offering_id,s.person_id,'62000000-0000-4000-8000-000000000002');
 if r<>r2 then raise exception 'Reopen regenerated report'; end if;
 perform set_config('liquidity.test.first',r->>'id',true);
 r2:=public.ipo_roll_request_liquidity(s.offering_id,s.person_id,'62000000-0000-4000-8000-000000000003',(r->>'id')::uuid);
 if r2->>'id'=r->>'id' then raise exception 'Refresh not versioned'; end if;
 if public.ipo_roll_request_liquidity(s.offering_id,s.person_id,'62000000-0000-4000-8000-000000000003',(r->>'id')::uuid)<>r2 then raise exception 'Retry duplicated'; end if;
 if public.ipo_roll_request_liquidity(s.offering_id,s.person_id,'62000000-0000-4000-8000-000000000004',(r->>'id')::uuid)<>r2 then raise exception 'Stale refresh duplicated'; end if;
 begin
  insert into app.liquidity_reports(user_id,offering_id,person_id,request_id,report) values(auth.uid(),s.offering_id,s.person_id,gen_random_uuid(),'{"forged":true}');
  raise exception 'Client authored report' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
 begin update app.liquidity_reports set user_id='60000000-0000-4000-8000-000000000002'; raise exception 'Owner changed' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
select set_config('request.jwt.claims','{"sub":"60000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ declare s record; r jsonb; begin
 select * into s from liquidity_test_subject;
 if exists(select 1 from app.liquidity_reports) then raise exception 'Cross-account leak'; end if;
 if exists(select 1 from app.liquidity_reports where id=current_setting('liquidity.test.first')::uuid) then raise exception 'Guessed ID leak'; end if;
 if public.ipo_roll_liquidity_report(s.offering_id,s.person_id) is not null then raise exception 'Report existence leaked'; end if;
 r:=public.ipo_roll_request_liquidity(s.offering_id,s.person_id,'62000000-0000-4000-8000-000000000001');
 if r->>'id'=current_setting('liquidity.test.first') then raise exception 'Shared report'; end if;
 begin delete from app.liquidity_reports; raise exception 'Report deleted' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
select set_config('request.jwt.claims','{"sub":"60000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ declare s record; begin
 select * into s from liquidity_test_subject;
 begin perform public.ipo_roll_request_liquidity(s.offering_id,s.person_id,gen_random_uuid()); raise exception 'Nonreviewer accessed subject' using errcode='ZX001'; exception when no_data_found then null; end;
end $$;
reset role;
update research.liquidity_assessments set explanation='Changed after snapshot' where ownership_id::text like '61000000-%';
update research.ownerships set holdings_as_of=current_date-7 where id::text like '61000000-%';
update app.entitlements set active=false where user_id='60000000-0000-4000-8000-000000000001';
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"60000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ begin if exists(select 1 from app.liquidity_reports) then raise exception 'Revoked entitlement leaked report'; end if; end $$;
reset role;
update app.entitlements set active=true where user_id='60000000-0000-4000-8000-000000000001';
set local role authenticated;
do $$ declare r jsonb; begin
 select report into r from app.liquidity_reports where id=current_setting('liquidity.test.first')::uuid;
 if r is null or r::text like '%Changed after snapshot%' then raise exception 'Snapshot changed or disappeared'; end if;
 if exists(select 1 from jsonb_array_elements(r->'positions')x where x->>'holdingsAsOf' is not null) then raise exception 'Holdings date silently updated in static report'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(gen_random_uuid(),gen_random_uuid()); raise exception 'Anonymous RPC allowed' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
reset role;
select 'PASS: private liquidity snapshots, classification safeguards, replay, explicit refresh, tamper denial, user isolation and revoked access' result;
rollback;
