-- Complete reviewed SpyGlass management biographies and principal-stockholder table.
-- Repeated fund/person and aggregate rows stay held; disposable reports roll back.
begin;
create temporary table spyglass_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89600000-0000-4000-8000-000000000001','spyglass-a@example.invalid'),
 ('89600000-0000-4000-8000-000000000002','spyglass-b@example.invalid'),
 ('89600000-0000-4000-8000-000000000003','spyglass-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89600000-%';
insert into app.reviewers(user_id) values
 ('89600000-0000-4000-8000-000000000001'),('89600000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89600000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; holder jsonb; r jsonb;
 offering constant uuid:='0e5fdbc6-eefa-58d3-aa45-2f3cdaa9e9b2'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>35 then raise exception 'SpyGlass subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id=offering)<>14 then raise exception 'SpyGlass source positions incomplete'; end if;
 if (select count(*) from research.biographies b join research.roles rr on rr.person_id=b.person_id where rr.offering_id=offering and b.approved)<>14
  then raise exception 'SpyGlass management biographies incomplete'; end if;
 if (select count(*) from research.ownership_attributions oa join research.ownerships o on o.id=oa.ownership_id where o.offering_id=offering and oa.approved)<>18
  then raise exception 'SpyGlass holder-person attributions incomplete'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and holdings_as_of<>'2025-12-31')
  or exists(select 1 from research.ownerships where offering_id=offering and position_basis<>'pre')
  then raise exception 'SpyGlass date or basis mismatch'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='Coöperatieve Gilde Healthcare VG VI U.A.';
 if holder->>'kind'<>'organization' or jsonb_array_length(holder->'ownershipGrid')<>1
  or holder#>>'{ownershipGrid,0,reportedTotal}'<>'1875013'
  then raise exception 'Gilde reported organization failed or was duplicated'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Geoff Pardo';
 if jsonb_array_length(subject->'ownershipGrid')<>1
  or subject#>>'{ownershipGrid,0,attribution,kind}'<>'reported_beneficial_owner'
  or subject#>>'{ownershipGrid,0,reportedHolder,name}'<>'Coöperatieve Gilde Healthcare VG VI U.A.'
  then raise exception 'Geoff repeated Gilde row was duplicated or attribution failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Ali Behbahani, M.D.';
 if jsonb_array_length(subject->'ownershipGrid')<>1
  or subject#>>'{ownershipGrid,0,attribution,kind}'<>'reported_beneficial_owner'
  or subject#>>'{ownershipGrid,0,reportedHolder,name}'<>'Entities affiliated with New Enterprise Associates'
  then raise exception 'Ali repeated NEA row was duplicated or attribution failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Srinivas Akkaraju';
 if subject#>>'{ownershipGrid,0,attribution,kind}'<>'control_authority'
  or subject#>>'{ownershipGrid,0,reportedHolder,name}'<>'Samsara BioCapital, L.P.'
  then raise exception 'Samsara control attribution failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Habib J. Dable';
 if jsonb_array_length(subject->'ownershipGrid')<>1
  or subject#>>'{ownershipGrid,0,reportedTotal}' is not null
  then raise exception 'Habib filing dash was promoted'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Glenn Sussman';
 if jsonb_array_length(subject->'ownershipGrid')<>0 or subject->>'biography' is null
  then raise exception 'Key employee outside ownership table disappeared'; end if;

 r:=public.ipo_roll_request_liquidity(offering,(select (x->>'id')::uuid from jsonb_array_elements(d->'people')x where x->>'name'='Ali Behbahani, M.D.'),'89700000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.6' or jsonb_array_length(r->'positions')<>1
  or r#>>'{positions,0,category}'<>'unknown'
  or r#>>'{positions,0,attribution,kind}'<>'reported_beneficial_owner'
  then raise exception 'SpyGlass private report promoted or incomplete'; end if;
 perform set_config('spyglass.report',r->>'id',true);
end $$;

select set_config('request.jwt.claims','{"sub":"89600000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
 or exists(select 1 from app.liquidity_reports where id=current_setting('spyglass.report')::uuid)
 then raise exception 'Cross-account SpyGlass report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89600000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('0e5fdbc6-eefa-58d3-aa45-2f3cdaa9e9b2') is not null then raise exception 'Internal SpyGlass research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(gen_random_uuid(),gen_random_uuid());
  raise exception 'Anonymous private report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline spyglass_test_state; begin
 select * into baseline from spyglass_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected SpyGlass QA report count'; end if;
end $$;
select 'PASS: full SpyGlass roster, audited overlaps, fund/controller distinctions and private-report denial' result;
rollback;
