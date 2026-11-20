-- Run against staging with an administrative test connection. Everything rolls back.
begin;
insert into auth.users(id,email) values('10000000-0000-4000-8000-000000000001','test-a@example.invalid'),('10000000-0000-4000-8000-000000000002','test-b@example.invalid');
insert into app.entitlements(user_id,active) values('10000000-0000-4000-8000-000000000001',true),('10000000-0000-4000-8000-000000000002',false);
insert into app.watchlists(user_id,name) values('10000000-0000-4000-8000-000000000001','Private A');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"10000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_has_access() then raise exception 'Non-entitled account admitted'; end if;
 begin perform app.lock_liquidity_report_account(); raise exception 'Non-entitled quota mutex admitted' using errcode='ZX001'; exception when insufficient_privilege then null; end;
 if (select count(*) from app.watchlists)<>0 then raise exception 'Cross-user watchlist visible'; end if;
 if (public.ipo_roll_offerings()->>'total')::int<>0 then raise exception 'Research visible without entitlement'; end if;
 begin insert into app.entitlements(user_id,active) values(auth.uid(),true); raise exception 'Self-entitlement allowed'; exception when insufficient_privilege then null; end;
end $$;
select set_config('request.jwt.claims','{"sub":"10000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ begin
 if not public.ipo_roll_has_access() then raise exception 'Entitled account blocked'; end if;
 if (select count(*) from app.watchlists)<>1 then raise exception 'Own watchlist unavailable'; end if;
 begin insert into app.watchlists(user_id,name) values('10000000-0000-4000-8000-000000000002','Wrong owner'); raise exception 'Cross-user write allowed'; exception when insufficient_privilege then null; end;
 begin update app.watchlists set user_id='10000000-0000-4000-8000-000000000002'; raise exception 'Ownership reassignment allowed'; exception when insufficient_privilege then null; end;
 perform public.ipo_roll_overview();
 perform public.ipo_roll_people_search('University of Michigan');
 perform public.ipo_roll_saved();
end $$;
reset role;
do $$ begin
 if exists(
  select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  cross join lateral aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
  where n.nspname in ('research','evidence','app','ops')
  and a.grantee=0 and a.privilege_type='EXECUTE'
 ) then raise exception 'PUBLIC can execute an internal-schema function'; end if;
 if not exists(
  select 1 from pg_db_role_setting s join pg_roles r on r.oid=s.setrole
  cross join lateral unnest(s.setconfig) setting
  where r.rolname='authenticated' and setting='statement_timeout=15s'
 ) then raise exception 'Authenticated statement timeout is not configured'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform app.lock_liquidity_report_account(); raise exception 'Anonymous quota mutex admitted' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
reset role;
select 'PASS: quota helper authorization, entitlement, cross-user read/write, ownership reassignment, API functions, internal function ACLs and authenticated timeout' as result;
rollback;
