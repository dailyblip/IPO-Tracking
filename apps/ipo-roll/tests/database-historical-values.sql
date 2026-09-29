-- Synthetic facts and disposable accounts only; the whole transaction rolls back.
begin;
create temporary table historical_prior_reports as select id,to_jsonb(r) body from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('f1000000-0000-4000-8000-000000000001','historical-a@example.invalid'),
 ('f1000000-0000-4000-8000-000000000002','historical-b@example.invalid'),
 ('f1000000-0000-4000-8000-000000000003','historical-c@example.invalid');
insert into app.entitlements(user_id,active) values
 ('f1000000-0000-4000-8000-000000000001',true),
 ('f1000000-0000-4000-8000-000000000002',true),
 ('f1000000-0000-4000-8000-000000000003',true);
insert into app.reviewers(user_id) values
 ('f1000000-0000-4000-8000-000000000001'),('f1000000-0000-4000-8000-000000000002');
create temporary table historical_test_subject as
 select o.id offering_id,r.person_id,o.current_filing_id,o.final_price,o.pricing_date,o.currency,
  doc.id document_id,doc.content_sha256,o.source_id
 from research.offerings o join research.roles r on r.offering_id=o.id
 join evidence.sources src on src.id=o.source_id
 join research.filings f on f.id=src.filing_id
 join evidence.documents doc on doc.source_id=src.id
 where o.stage='Priced' and src.rights_status='internal_review' and f.filed_on>=o.pricing_date
 and doc.retrieved_at<now() and r.verified
 order by o.id,doc.id,r.person_id limit 1;
do $$ begin if not exists(select 1 from historical_test_subject) then raise exception 'No private priced source fixture'; end if; end $$;
grant select on historical_test_subject to authenticated;
insert into evidence.spans(id,document_id,excerpt,locator,approved)
 select ('f1100000-0000-4000-8000-'||lpad(n::text,12,'0'))::uuid,document_id,
  case when n=1 then 'SYNTHETIC TEST ONLY: named holder personally owns 100 Class A issued common shares, with no overlap; compatible final IPO price basis.'
   else 'SYNTHETIC TEST ONLY: named holder completed a sale of 10 Class A common shares at the stated sale price. Not company proceeds.' end,
  'Synthetic test fixture; rolled back',true from historical_test_subject cross join generate_series(1,2)n;
insert into research.ownerships(id,offering_id,party_id,filing_id,share_class,position_basis,shares,source_row_key,evidence_id,approved,holdings_as_of,quantity_kind)
 select 'f1200000-0000-4000-8000-000000000001',offering_id,person_id,current_filing_id,'Synthetic Class A','pre',100,
  'historical-value-rollback-test','f1100000-0000-4000-8000-000000000001',true,pricing_date,'reported_shares' from historical_test_subject;

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"f1000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare s record; report jsonb; begin
 select * into s from historical_test_subject;
 report:=public.ipo_roll_request_liquidity(s.offering_id,s.person_id,'f1300000-0000-4000-8000-000000000001');
 if report->'historicalValues'->>'version' is distinct from 'historical-value-snapshot/1'
  or jsonb_array_length(report->'historicalValues'->'holdings') is distinct from 0
  or jsonb_array_length(report->'historicalValues'->'sales') is distinct from 0 then raise exception 'Missing claims did not remain unknown'; end if;
 perform set_config('historical.test.empty',report::text,true);
end $$;
reset role;

insert into research.historical_value_reviews(id,kind,offering_id,party_id,ownership_id,quantity,holdings_date,position_basis,
 holder_kind,attribution,source_security_id,source_share_class,price_security_id,price_share_class,price,currency,price_date,
 compatibility_method,reconciled_through,exposure_id,quantity_evidence_id,holder_evidence_id,price_evidence_id,
 compatibility_evidence_id,overlap_evidence_id,source_hashes,reviewed_at,approved,completed_sale_confirmed,sale_price_confirmed)
 select ('f1400000-0000-4000-8000-'||lpad(n::text,12,'0'))::uuid,
  case when n=1 then 'holding' else 'completed_sale' end,offering_id,person_id,'f1200000-0000-4000-8000-000000000001',
  case when n=1 then 100 else 10 end,pricing_date,case when n=1 then 'actual_disclosed' else 'completed_holder_sale' end,
  'person','personal_economic','synthetic-class-a','Synthetic Class A','synthetic-class-a','Synthetic Class A',
  final_price,currency,pricing_date,'same_security',pricing_date,'synthetic-exposure-'||n,
  ('f1100000-0000-4000-8000-'||lpad(n::text,12,'0'))::uuid,
  'f1100000-0000-4000-8000-000000000001','f1100000-0000-4000-8000-000000000001',
  'f1100000-0000-4000-8000-000000000001','f1100000-0000-4000-8000-000000000001',
  jsonb_build_object(document_id::text,content_sha256),now(),true,n=2,n=2
 from historical_test_subject cross join generate_series(1,2)n;

set local role authenticated;
select set_config('request.jwt.claims','{"sub":"f1000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare s record; first_report jsonb; report jsonb; holding jsonb; sale jsonb; begin
 select * into s from historical_test_subject;
 first_report:=current_setting('historical.test.empty')::jsonb;
 if public.ipo_roll_request_liquidity(s.offering_id,s.person_id,'f1300000-0000-4000-8000-000000000002')<>first_report then
  raise exception 'Reopen silently recalculated after new shared facts'; end if;
 report:=public.ipo_roll_request_liquidity(s.offering_id,s.person_id,'f1300000-0000-4000-8000-000000000003',(first_report->>'id')::uuid);
 if report->>'id'=first_report->>'id' then raise exception 'Explicit refresh not versioned'; end if;
 holding:=report->'historicalValues'->'holdings'->0; sale:=report->'historicalValues'->'sales'->0;
 if jsonb_array_length(report->'historicalValues'->'holdings') is distinct from 1
  or jsonb_array_length(report->'historicalValues'->'sales') is distinct from 1 then raise exception 'Reviewed value rows missing'; end if;
 if holding->'output'->>'status' is distinct from 'established' or (holding->'output'->>'grossAmount')::numeric is distinct from 100*s.final_price
  or holding->'output'->>'valueScope' is distinct from 'personal_economic_holding' then raise exception 'Historical amount incorrect: %',holding; end if;
 if sale->'output'->>'status' is distinct from 'established' or (sale->'output'->>'grossAmount')::numeric is distinct from 10*s.final_price
  then raise exception 'Completed holder sale amount incorrect'; end if;
 if holding->'output'->>'holdingsDate' is distinct from s.pricing_date::text or holding->'output'->>'priceDate' is distinct from s.pricing_date::text
  or holding->'position'->'evidence'->0->>'documentHash' is distinct from s.content_sha256 then raise exception 'Frozen provenance missing'; end if;
 if exists(select 1 from jsonb_array_elements(report->'positions')p where p->>'marketValue' is not null) then raise exception 'Historical value became current quote'; end if;
 if (select saved.report from app.liquidity_reports saved where saved.id=(first_report->>'id')::uuid) is distinct from first_report then raise exception 'Prior unknown report changed'; end if;
 if public.ipo_roll_request_liquidity(s.offering_id,s.person_id,'f1300000-0000-4000-8000-000000000003',(first_report->>'id')::uuid)<>report then raise exception 'Retry changed snapshot'; end if;
 perform set_config('historical.test.established',report::text,true);
 begin update research.historical_value_reviews set price=1; raise exception 'Client changed shared claim' using errcode='ZX001'; exception when insufficient_privilege then null; end;
 begin insert into research.historical_value_reviews default values; raise exception 'Client inserted shared claim' using errcode='ZX001'; exception when insufficient_privilege then null; end;
 begin insert into app.liquidity_reports(offering_id,person_id,request_id,report) values(s.offering_id,s.person_id,gen_random_uuid(),'{"historicalValues":{"forged":true}}');
  raise exception 'Client authored output' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;

select set_config('request.jwt.claims','{"sub":"f1000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ declare s record; report jsonb; begin
 select * into s from historical_test_subject;
 if exists(select 1 from app.liquidity_reports saved where saved.id=(current_setting('historical.test.established')::jsonb->>'id')::uuid)
  or public.ipo_roll_liquidity_report(s.offering_id,s.person_id) is not null then raise exception 'Other account learned report existence'; end if;
 report:=public.ipo_roll_request_liquidity(s.offering_id,s.person_id,'f1300000-0000-4000-8000-000000000003');
 if report->>'id'=current_setting('historical.test.established')::jsonb->>'id' then raise exception 'Users shared a report'; end if;
 begin update app.liquidity_reports set report='{}'; raise exception 'Report overwritten' using errcode='ZX001'; exception when insufficient_privilege then null; end;
 begin delete from app.liquidity_reports; raise exception 'Report deleted' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
select set_config('request.jwt.claims','{"sub":"f1000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from research.historical_value_reviews) then raise exception 'Ordinary customer read private source claims'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform research.historical_value_snapshot(gen_random_uuid(),gen_random_uuid(),now());
  raise exception 'Anonymous historical access' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
reset role;

-- Change shared price evidence after generation: the old report remains bytewise
-- identical and only a new explicit version can reflect an unknown calculation.
update research.historical_value_reviews set price=price+1 where id='f1400000-0000-4000-8000-000000000001';
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"f1000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare s record; old jsonb; fresh jsonb; begin
 select * into s from historical_test_subject; old:=current_setting('historical.test.established')::jsonb;
 if (select saved.report from app.liquidity_reports saved where saved.id=(old->>'id')::uuid) is distinct from old then raise exception 'Shared change rewrote saved report'; end if;
 fresh:=public.ipo_roll_request_liquidity(s.offering_id,s.person_id,'f1300000-0000-4000-8000-000000000004',(old->>'id')::uuid);
 if fresh->'historicalValues'->'holdings'->0->'output'->>'reason' is distinct from 'non_final_price'
  or fresh->'historicalValues'->'holdings'->0->'output'->>'grossAmount' is not null then raise exception 'Mismatched final price calculated'; end if;
end $$;
reset role;

-- A duplicated exposure must be held on every representation, not picked or summed.
update research.historical_value_reviews r set price=s.final_price from historical_test_subject s
 where r.id='f1400000-0000-4000-8000-000000000001';
insert into research.historical_value_reviews
 select (jsonb_populate_record(null::research.historical_value_reviews,to_jsonb(r)||jsonb_build_object('id','f1400000-0000-4000-8000-000000000003'))).*
 from research.historical_value_reviews r where id='f1400000-0000-4000-8000-000000000001';
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"f1000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare s record; v jsonb; begin
 select * into s from historical_test_subject; v:=research.historical_value_snapshot(s.offering_id,s.person_id,clock_timestamp());
 if jsonb_array_length(v->'holdings') is distinct from 2 or exists(select 1 from jsonb_array_elements(v->'holdings')h
  where h->'output'->>'reason' is distinct from 'duplicate_exposure' or h->'output'->>'grossAmount' is not null) then raise exception 'Duplicate exposure not fully held'; end if;
end $$;
reset role;
delete from research.historical_value_reviews where id='f1400000-0000-4000-8000-000000000003';
update research.historical_value_reviews set completed_sale_confirmed=false where kind='completed_sale' and id='f1400000-0000-4000-8000-000000000002';
update research.ownerships set quantity_kind='beneficial_total' where id='f1200000-0000-4000-8000-000000000001';
set local role authenticated;
do $$ declare s record; v jsonb; begin
 select * into s from historical_test_subject; v:=research.historical_value_snapshot(s.offering_id,s.person_id,clock_timestamp());
 if v->'holdings'->0->'output'->>'reason' is distinct from 'aggregate_or_unknown_quantity'
  or v->'sales'->0->'output'->>'reason' is distinct from 'sale_not_completed' then raise exception 'Aggregate total or proposed sale qualified'; end if;
end $$;
reset role;
insert into research.ownership_components(ownership_id,ordinal,instrument,quantity,attribution,description,evidence_id,approved) values
 ('f1200000-0000-4000-8000-000000000001',1,'common_share',80,'direct','SYNTHETIC TEST ONLY: 80 issued common shares','f1100000-0000-4000-8000-000000000001',true),
 ('f1200000-0000-4000-8000-000000000001',2,'option',20,'direct','SYNTHETIC TEST ONLY: 20 option shares excluded from value','f1100000-0000-4000-8000-000000000001',true);
update research.historical_value_reviews set component_ordinal=1,quantity=80
 where id='f1400000-0000-4000-8000-000000000001';
set local role authenticated;
do $$ declare s record; v jsonb; begin
 select * into s from historical_test_subject; v:=research.historical_value_snapshot(s.offering_id,s.person_id,clock_timestamp());
 if v->'holdings'->0->'output'->>'status' is distinct from 'established'
  or (v->'holdings'->0->'output'->>'grossAmount')::numeric is distinct from 80*s.final_price then raise exception 'Reviewed common component did not calculate separately'; end if;
end $$;
reset role;
update research.ownership_components set attribution='fund_or_control'
 where ownership_id='f1200000-0000-4000-8000-000000000001' and ordinal=1;
set local role authenticated;
do $$ declare s record; v jsonb; begin
 select * into s from historical_test_subject; v:=research.historical_value_snapshot(s.offering_id,s.person_id,clock_timestamp());
 if v->'holdings'->0->'output'->>'reason' is distinct from 'unsupported_holder_attribution' then raise exception 'Fund component became personal value'; end if;
end $$;
reset role;
update research.ownership_components set instrument='option'
 where ownership_id='f1200000-0000-4000-8000-000000000001' and ordinal=1;
set local role authenticated;
do $$ declare s record; v jsonb; begin
 select * into s from historical_test_subject; v:=research.historical_value_snapshot(s.offering_id,s.person_id,clock_timestamp());
 if v->'holdings'->0->'output'->>'reason' is distinct from 'unsupported_instrument' then raise exception 'Option component multiplied by IPO price'; end if;
end $$;
reset role;
update research.ownership_components set instrument='common_share',attribution='direct'
 where ownership_id='f1200000-0000-4000-8000-000000000001' and ordinal=1;
update research.ownerships set position_basis='post' where id='f1200000-0000-4000-8000-000000000001';
update research.historical_value_reviews set position_basis='projected_post_offering',projection_conditions='Synthetic projection: subject to IPO completion.'
 where id='f1400000-0000-4000-8000-000000000001';
set local role authenticated;
do $$ declare s record; v jsonb; begin
 select * into s from historical_test_subject; v:=research.historical_value_snapshot(s.offering_id,s.person_id,clock_timestamp());
 if v->'holdings'->0->'output'->>'status' is distinct from 'established'
  or v->'holdings'->0->'output'->>'positionBasis' is distinct from 'projected_post_offering'
  or coalesce(v->'holdings'->0->'output'->>'label','') not like 'Projected%'
  or coalesce(v->'holdings'->0->'output'->>'conditions','') not like 'Synthetic projection%' then raise exception 'Projected quantity became actual holding'; end if;
end $$;
reset role;
update research.historical_value_reviews set source_hashes='{}' where id::text like 'f1400000-%';
set local role authenticated;
do $$ declare s record; v jsonb; begin
 select * into s from historical_test_subject; v:=research.historical_value_snapshot(s.offering_id,s.person_id,clock_timestamp());
 if jsonb_array_length(v->'holdings') is distinct from 0 or jsonb_array_length(v->'sales') is distinct from 0 then raise exception 'Stale source hashes visible'; end if;
end $$;
reset role;
do $$ begin
 if exists(select 1 from historical_prior_reports p left join app.liquidity_reports r on r.id=p.id where r.id is null or to_jsonb(r)<>p.body)
  then raise exception 'Existing private report mutated'; end if;
 if (select string_agg(tgname,',' order by tgname) from pg_trigger where tgrelid='app.liquidity_reports'::regclass and not tgisinternal)
  not like '%liquidity_report_quota,liquidity_report_snapshot,liquidity_report_snapshot_valuation%' then raise exception 'Unsafe report trigger order'; end if;
end $$;
select 'PASS: historical values require reviewed matching evidence, immutable outputs, explicit refresh, duplicate holds, and account isolation; all fixtures rolled back' result;
rollback;
