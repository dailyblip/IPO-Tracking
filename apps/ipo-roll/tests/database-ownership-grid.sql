begin;
insert into auth.users(id,email) values
 ('82000000-0000-4000-8000-000000000001','grid-a@example.invalid'),
 ('82000000-0000-4000-8000-000000000002','grid-b@example.invalid'),
 ('82000000-0000-4000-8000-000000000003','grid-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '82000000-%';
insert into app.reviewers(user_id) values('82000000-0000-4000-8000-000000000001'),('82000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"82000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; p jsonb; begin
 d:=public.ipo_roll_detail('080c3186-0a1e-5d63-a098-0173d5b162c5');
 select x into strict p from jsonb_array_elements(d->'people')x where x->>'name'='Michael A. Chapp';
 if jsonb_array_length(p->'ownershipGrid')<>1 or jsonb_array_length(p#>'{ownershipGrid,0,components,items}')<>4
  or p#>>'{ownershipGrid,0,quantityKind}'<>'beneficial_total' then raise exception 'Components missing/duplicated'; end if;
 if exists(select 1 from app.liquidity_reports) then raise exception 'Grid generated a private report'; end if;
 if d::text like '%requestId%' or d::text like '%user_id%' or d::text like '%asOf%' then raise exception 'Private metadata in grid'; end if;
 perform set_config('grid.before',d::text,true);
 perform public.ipo_roll_request_liquidity('080c3186-0a1e-5d63-a098-0173d5b162c5','f09c7a6d-d578-5b7f-b181-9d2ea546373f',gen_random_uuid());
 if public.ipo_roll_detail('080c3186-0a1e-5d63-a098-0173d5b162c5')<>d then raise exception 'Grid exposes existence of private report'; end if;
 p:=research.ownership_reference_json('4f9a9c1f-fcd6-541f-9e4a-d60caea7e7b9','0d37f6d4-861d-53a6-b83c-c66e36822fd8');
 if p#>>'{0,shareClass}'<>'Class B common stock' or p#>>'{0,restrictionTimeline,0,dayCount}'<>'180'
  or p#>>'{0,restrictionTimeline,0,boundaryDate}'<>'2027-03-16' then raise exception 'Class or conditional terms lost'; end if;
 if research.ownership_reference_json('28e5a499-d789-515d-8c96-1a939233b404','0d37f6d4-861d-53a6-b83c-c66e36822fd8')<>'[]'::jsonb then raise exception 'Cross-company person association'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"82000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('080c3186-0a1e-5d63-a098-0173d5b162c5')<>current_setting('grid.before')::jsonb
  or exists(select 1 from app.liquidity_reports) then raise exception 'Grid differs by private account activity'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"82000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('080c3186-0a1e-5d63-a098-0173d5b162c5') is not null
  or research.ownership_reference_json('080c3186-0a1e-5d63-a098-0173d5b162c5','f09c7a6d-d578-5b7f-b181-9d2ea546373f')<>'[]'::jsonb then raise exception 'Internal holdings exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform research.ownership_reference_json(gen_random_uuid(),gen_random_uuid());
  raise exception 'Anonymous grid allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
select 'PASS: shared facts, correct components/classes/timelines, no automatic reports or private metadata, isolated accounts and access denial' result;
rollback;
