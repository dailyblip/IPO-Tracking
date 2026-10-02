begin;
savepoint qa;
insert into auth.users(id,email) values
 ('86000000-0000-4000-8000-000000000001','holding-review-a@example.invalid'),
 ('86000000-0000-4000-8000-000000000002','holding-review-b@example.invalid'),
 ('86000000-0000-4000-8000-000000000003','holding-customer@example.invalid');
insert into app.entitlements(user_id,active) values ('86000000-0000-4000-8000-000000000001',true),('86000000-0000-4000-8000-000000000002',true),('86000000-0000-4000-8000-000000000003',true);
insert into app.reviewers(user_id) values('86000000-0000-4000-8000-000000000001'),('86000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"86000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb;p jsonb;g jsonb;r jsonb;r2 jsonb; begin
 d:=public.ipo_roll_detail('13aac6f0-b45e-5585-a7a5-b58385936068');
 select x into strict p from jsonb_array_elements(d->'people') x where x->>'id'='5d0c5c17-d520-5c87-9da9-814ba66a5333';
 select x into strict g from jsonb_array_elements(p->'ownershipGrid') x where x->>'positionBasis'='pre';
 if g#>>'{components,status}' <> 'reconciled' or jsonb_array_length(g#>'{components,items}')<>5 then raise exception 'Component breakdown missing';end if;
 if (select sum((x->>'quantity')::numeric) from jsonb_array_elements(g#>'{components,items}') x) is distinct from (g->>'reportedTotal')::numeric then raise exception 'Component arithmetic mismatch';end if;
 if not exists(select 1 from jsonb_array_elements(g#>'{components,items}') x where x->>'instrument'='preferred_conversion' and x->>'attribution'='trust_or_family' and x#>>'{source,url}' is not null) then raise exception 'Conversion mislabeled or unsourced';end if;
 r:=public.ipo_roll_request_liquidity('13aac6f0-b45e-5585-a7a5-b58385936068','5d0c5c17-d520-5c87-9da9-814ba66a5333','86100000-0000-4000-8000-000000000010');
 if exists(select 1 from jsonb_array_elements(r->'positions')x where x->>'category'<>'unknown' or x->>'shares' is not null or x->>'marketValue' is not null) then raise exception 'Component decomposition became liquid or valuable';end if;
 if not exists(select 1 from jsonb_array_elements(r->'positions')x where x->>'positionBasis'='pre' and x#>>'{components,status}'='reconciled') then raise exception 'New snapshot omitted components';end if;
 if not exists(select 1 from jsonb_array_elements(r->'positions')x where x->>'positionBasis'='post' and x#>>'{components,status}'='incomplete') then raise exception 'Post components inferred';end if;
 r2:=public.ipo_roll_request_liquidity('13aac6f0-b45e-5585-a7a5-b58385936068','5d0c5c17-d520-5c87-9da9-814ba66a5333','86100000-0000-4000-8000-000000000011');
 if r2 is distinct from r then raise exception 'Reopen rewrote snapshot';end if;
 r2:=public.ipo_roll_request_liquidity('13aac6f0-b45e-5585-a7a5-b58385936068','5d0c5c17-d520-5c87-9da9-814ba66a5333','86100000-0000-4000-8000-000000000012',(r->>'id')::uuid);
 if r2->>'id'=r->>'id' or (select report from app.liquidity_reports where id=(r->>'id')::uuid) is distinct from r then raise exception 'Refresh lost snapshot';end if;
 perform set_config('qa.other_report_id',r->>'id',true);
end $$;
select set_config('request.jwt.claims','{"sub":"86000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
if exists(select 1 from app.liquidity_reports where id=current_setting('qa.other_report_id')::uuid) or public.ipo_roll_liquidity_report('13aac6f0-b45e-5585-a7a5-b58385936068','5d0c5c17-d520-5c87-9da9-814ba66a5333') is not null then raise exception 'Cross-account report existence leaked'; end if;
begin update app.liquidity_reports set report='{}'::jsonb where id=current_setting('qa.other_report_id')::uuid;raise exception 'Report write unexpectedly allowed' using errcode='ZX001';exception when insufficient_privilege then null;end;
end $$;
select set_config('request.jwt.claims','{"sub":"86000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin if public.ipo_roll_detail('13aac6f0-b45e-5585-a7a5-b58385936068') is not null then raise exception 'Customer access widened'; end if;end $$;
set local role anon;
do $$ begin begin perform public.ipo_roll_detail('13aac6f0-b45e-5585-a7a5-b58385936068');raise exception 'Anonymous allowed' using errcode='ZX001';exception when insufficient_privilege then null;end;end $$;
reset role;rollback to qa;

rollback;
