-- Complete reviewed Once Upon a Farm management biographies and ownership table.
-- Null quantities, entity/controller attribution, alternative pre/post snapshots and
-- proposed-versus-completed sale distinctions remain explicit. Disposable reports roll back.
begin;
create temporary table once_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89800000-0000-4000-8000-000000000001','once-a@example.invalid'),
 ('89800000-0000-4000-8000-000000000002','once-b@example.invalid'),
 ('89800000-0000-4000-8000-000000000003','once-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89800000-%';
insert into app.reviewers(user_id) values
 ('89800000-0000-4000-8000-000000000001'),('89800000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89800000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; holder jsonb; r jsonb;
 offering constant uuid:='fe32ad7d-839f-5c49-95fb-41237d7cd8ee'; begin
 d:=public.ipo_roll_detail(offering);
 if jsonb_array_length(d->'people')<>30 then raise exception 'Once subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id=offering and approved)<>58
  then raise exception 'Once source positions incomplete'; end if;
 if (select count(*) from research.biographies b join research.roles rr on rr.person_id=b.person_id where rr.offering_id=offering and b.approved)<>10
  then raise exception 'Once management biographies incomplete'; end if;
 if (select count(*) from research.ownership_attributions oa join research.ownerships o on o.id=oa.ownership_id where o.offering_id=offering and oa.approved)<>4
  then raise exception 'Once controller attributions incomplete'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and holdings_as_of<>'2026-01-05')
  or (select count(distinct position_basis) from research.ownerships where offering_id=offering)<>2
  then raise exception 'Once holdings date or basis mismatch'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='Cambridge';
 if holder->>'kind'<>'group' or jsonb_array_length(holder->'ownershipGrid')<>2
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal'='3760066')<>2
  then raise exception 'Once Cambridge group failed or duplicated'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Filipp Chebotarev';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}'='control_authority')<>2
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{reportedHolder,name}'<>'Cambridge')
  then raise exception 'Once Cambridge controller attribution failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Brett Thomas';
 if jsonb_array_length(subject->'ownershipGrid')<>4
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}'='control_authority' and x->>'reportedTotal'='11063595')<>2
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}' is null and x->>'reportedTotal' is null)<>2
  then raise exception 'Once CAVU attribution or direct dash distinction failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Dara Bazzano';
 if subject->>'biography' is null or jsonb_array_length(subject->'ownershipGrid')<>2
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x->>'reportedTotal' is not null)
  then raise exception 'Once management biography or null holdings disappeared'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Jennifer Garner';
 if jsonb_array_length(subject->'ownershipGrid')<>2
  or (select array_agg((x->>'reportedTotal')::bigint order by x->>'positionBasis') from jsonb_array_elements(subject->'ownershipGrid') x)<>array[3057280,2702672]::bigint[]
  then raise exception 'Once distinct Garner pre/post quantities failed'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x where x->>'name'='Other selling stockholders with 120,001 to 125,000 shares';
 if holder->>'kind'<>'group' or jsonb_array_length(holder->'ownershipGrid')<>2
  or (select count(*) from jsonb_array_elements(holder->'ownershipGrid') x where x->>'reportedTotal' in ('246634','26722'))<>2
  then raise exception 'Once anonymized source bucket failed'; end if;
 if exists(select 1 from research.ownerships where offering_id=offering and shares in (6760944,7115552))
  then raise exception 'Once overlapping ten-person aggregate was imported'; end if;

 r:=public.ipo_roll_request_liquidity(offering,(subject->>'id')::uuid,'89810000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.6' or jsonb_array_length(r->'positions')<>2
  or exists(select 1 from jsonb_array_elements(r->'positions') x where x->>'category'<>'unknown' or x->>'marketValue' is not null)
  then raise exception 'Once private report promoted incomplete holdings or a market value'; end if;
 perform set_config('once.report',r->>'id',true);
end $$;

select set_config('request.jwt.claims','{"sub":"89800000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
 or exists(select 1 from app.liquidity_reports where id=current_setting('once.report')::uuid)
 then raise exception 'Cross-account Once report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89800000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('fe32ad7d-839f-5c49-95fb-41237d7cd8ee') is not null then raise exception 'Internal Once research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(current_setting('once.report')::uuid,gen_random_uuid());
  raise exception 'Anonymous guessed Once report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline once_test_state; begin
 select * into baseline from once_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected Once QA report count'; end if;
end $$;
select 'PASS: full Once roster, all holder rows, null/basis/controller distinctions, held overlap and private-report denial' result;
rollback;
