-- Real staging option-only cohort. All test accounts/reports/mutations roll back.
begin;
insert into auth.users(id,email) values
 ('81000000-0000-4000-8000-000000000001','options-a@example.invalid'),
 ('81000000-0000-4000-8000-000000000002','options-b@example.invalid'),
 ('81000000-0000-4000-8000-000000000003','options-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '81000000-%';
insert into app.reviewers(user_id) values('81000000-0000-4000-8000-000000000001'),('81000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"81000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare s record; r jsonb; p jsonb; n int:=0; begin
 for s in select * from research.ownerships where offering_id='28e5a499-d789-515d-8c96-1a939233b404' loop
  n:=n+1;
  r:=public.ipo_roll_request_liquidity(s.offering_id,s.party_id,gen_random_uuid());
  p:=r#>'{positions,0}';
  if jsonb_array_length(r->'positions')<>1 or p->>'quantityKind'<>'beneficial_total'
   or p->>'shares' is not null or p->>'marketValue' is not null or p->>'category'<>'unknown'
   or p->>'positionBasis'<>'pre' or p->>'holdingsAsOf'<>'2026-08-01'
   or p->>'filingDate'<>'2026-09-18' or p#>>'{components,status}'<>'reconciled'
   or jsonb_array_length(p#>'{components,items}')<>1
   or p#>>'{components,items,0,instrument}'<>'option'
   or p#>>'{components,items,0,attribution}'<>'unknown'
   or p#>>'{components,items,0,quantity}'<>p->>'reportedTotal'
   or jsonb_array_length(p->'restrictionTimeline')<>0 then
   raise exception 'Option-only disclosure promoted, misdated, duplicated or unreconciled';
  end if;
  if s.party_id='aad7ec75-9071-570c-a3ba-2def0480644e' then
   if p->>'reportedTotal'<>'1399175' then raise exception 'Post distribution included in pre total'; end if;
   perform set_config('options.report',r->>'id',true);
  elsif s.party_id='08bfa883-8ca7-5e19-a566-efd0a750e431' then
   if p->>'reportedTotal'<>'380837' then raise exception 'Post distribution included in pre total'; end if;
  else raise exception 'Unreviewed identity imported'; end if;
  if public.ipo_roll_request_liquidity(s.offering_id,s.party_id,gen_random_uuid())<>r then raise exception 'Reopen recalculated'; end if;
 end loop;
 if n<>2 then raise exception 'Expected two option-only disclosures'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"81000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ declare r jsonb; begin
 if exists(select 1 from app.liquidity_reports where id=current_setting('options.report')::uuid)
  or public.ipo_roll_liquidity_report('28e5a499-d789-515d-8c96-1a939233b404','aad7ec75-9071-570c-a3ba-2def0480644e') is not null then raise exception 'Cross-account existence leak'; end if;
 begin
  perform public.ipo_roll_request_liquidity('28e5a499-d789-515d-8c96-1a939233b404','aad7ec75-9071-570c-a3ba-2def0480644e',gen_random_uuid(),current_setting('options.report')::uuid);
  raise exception 'Guessed report ID accepted' using errcode='ZX001';
 exception when no_data_found then null; end;
 r:=public.ipo_roll_request_liquidity('28e5a499-d789-515d-8c96-1a939233b404','aad7ec75-9071-570c-a3ba-2def0480644e',gen_random_uuid());
 if r->>'id'=current_setting('options.report') then raise exception 'Accounts share a report'; end if;
 begin update app.liquidity_reports set user_id='81000000-0000-4000-8000-000000000001';
  raise exception 'Customer can reassign report' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
-- A lone ordinary-share component must not silently explain an award total.
update research.ownership_components set instrument='common_share' where ownership_id in
 (select id from research.ownerships where party_id='aad7ec75-9071-570c-a3ba-2def0480644e');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"81000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from research.ownerships o where o.party_id='aad7ec75-9071-570c-a3ba-2def0480644e'
  and research.ownership_components_json(o.id)->>'status'<>'incomplete') then raise exception 'Singleton common shares accepted'; end if;
end $$;
reset role;
update research.ownership_components set instrument='option' where ownership_id in
 (select id from research.ownerships where party_id='aad7ec75-9071-570c-a3ba-2def0480644e');
-- Missing source components cannot rewrite an existing static snapshot.
update research.ownership_components set approved=false where ownership_id in
 (select id from research.ownerships where party_id='aad7ec75-9071-570c-a3ba-2def0480644e');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"81000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare old jsonb; r jsonb; begin
 old:=public.ipo_roll_liquidity_report('28e5a499-d789-515d-8c96-1a939233b404','aad7ec75-9071-570c-a3ba-2def0480644e');
 if old#>>'{positions,0,components,status}'<>'reconciled' then raise exception 'Saved report rewritten'; end if;
 r:=public.ipo_roll_request_liquidity('28e5a499-d789-515d-8c96-1a939233b404','aad7ec75-9071-570c-a3ba-2def0480644e',gen_random_uuid(),(old->>'id')::uuid);
 if r->>'id'=old->>'id' or r#>>'{positions,0,components,status}'<>'incomplete'
  or r#>>'{positions,0,category}'<>'unknown' then raise exception 'Explicit refresh failed closed behavior'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"81000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from research.ownerships where offering_id='28e5a499-d789-515d-8c96-1a939233b404')
  or exists(select 1 from app.liquidity_reports) then raise exception 'Customer visibility leak'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report('28e5a499-d789-515d-8c96-1a939233b404','aad7ec75-9071-570c-a3ba-2def0480644e');
  raise exception 'Anonymous access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
select 'PASS: option-only pre totals, no post-distribution double counting, unknown saleability, account isolation, immutable saved snapshot and explicit refresh' result;
rollback;
