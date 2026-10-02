-- Disposable identities and all source mutations are rolled back.
begin;
insert into auth.users(id,email) values('90000000-0000-4000-8000-000000000001','lockup-a@example.invalid'),('90000000-0000-4000-8000-000000000002','lockup-b@example.invalid'),('90000000-0000-4000-8000-000000000003','lockup-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '90000000-%';
insert into app.reviewers(user_id) values('90000000-0000-4000-8000-000000000001'),('90000000-0000-4000-8000-000000000002');
create temporary table lockup_subject as select h.id,h.offering_id,h.party_id from research.ownerships h join research.parties p on p.id=h.party_id where p.name='Christoph Birchler' and h.offering_id='4f9a9c1f-fcd6-541f-9e4a-d60caea7e7b9';
grant select on lockup_subject to authenticated;
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"90000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare s record; r jsonb; p jsonb; t jsonb; n int:=0; begin
 for s in select h.* from research.ownerships h join research.lockup_terms t on t.ownership_id=h.id where h.offering_id='4f9a9c1f-fcd6-541f-9e4a-d60caea7e7b9' loop
  r:=public.ipo_roll_request_liquidity(s.offering_id,s.party_id,gen_random_uuid());p:=r#>'{positions,0}';t:=p#>'{restrictionTimeline,0}';n:=n+1;
  if t is null or t->>'triggerDate' is distinct from '2026-09-17' or t->>'boundaryDate' is distinct from '2027-03-16' or t->>'dayCount' is distinct from '180' then raise exception 'Trigger/date arithmetic mismatch'; end if;
  if p->>'filingDate' is distinct from '2026-09-21' or p->>'holdingsAsOf' is distinct from '2026-09-03' or p->>'category' is distinct from 'unknown' or p->>'lockupEnd' is not null or p->>'marketValue' is not null then raise exception 'Conditional date promoted or conflated'; end if;
  if jsonb_array_length(t->'evidence')<>4 or t->>'method'<>'calendar-days-after/1' then raise exception 'Missing date/term provenance'; end if;
  if public.ipo_roll_request_liquidity(s.offering_id,s.party_id,gen_random_uuid())<>r then raise exception 'Reopen regenerated'; end if;
  if s.id in(select id from lockup_subject) then perform set_config('lockup.report',r->>'id',true); end if;
 end loop;
 if n<>2 then raise exception 'Expected two source-reviewed timelines'; end if;
 begin update research.lockup_terms set day_count=1; raise exception 'Source write allowed' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
select set_config('request.jwt.claims','{"sub":"90000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ declare s record; begin select * into strict s from lockup_subject;
 if exists(select 1 from app.liquidity_reports where id=current_setting('lockup.report')::uuid) or public.ipo_roll_liquidity_report(s.offering_id,s.party_id) is not null then raise exception 'Cross-account report/existence leak'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"90000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ declare s record; begin select * into strict s from lockup_subject;
 if exists(select 1 from research.lockup_terms) or research.lockup_timeline_json(s.id)<>'[]'::jsonb then raise exception 'Internal facts leaked'; end if;
end $$;
reset role;
-- Exact date arithmetic handles leap days with no trading-calendar inference.
update research.lockup_terms set trigger_date='2024-02-28',day_count=1 where ownership_id in(select id from lockup_subject);
do $$ begin if not exists(select 1 from research.lockup_terms where ownership_id in(select id from lockup_subject) and boundary_date='2024-02-29') then raise exception 'Leap-day arithmetic failed'; end if; end $$;
-- Cross-document evidence must suppress the whole new timeline, not just one citation.
update research.lockup_terms set evidence_ids[1]=(select o.evidence_id from research.ownerships o where o.offering_id<>'4f9a9c1f-fcd6-541f-9e4a-d60caea7e7b9' limit 1) where ownership_id in(select id from lockup_subject);
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"90000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare s record; old jsonb; fresh jsonb; begin select * into strict s from lockup_subject;
 old:=public.ipo_roll_liquidity_report(s.offering_id,s.party_id);
 if old#>>'{positions,0,restrictionTimeline,0,boundaryDate}' is distinct from '2027-03-16' then raise exception 'Static timeline rewritten'; end if;
 fresh:=public.ipo_roll_request_liquidity(s.offering_id,s.party_id,gen_random_uuid(),(old->>'id')::uuid);
 if fresh#>'{positions,0,restrictionTimeline}' is distinct from '[]'::jsonb or fresh#>>'{positions,0,category}' is distinct from 'unknown' then raise exception 'Unapproved evidence accepted or saleability inferred'; end if;
end $$;
set local role anon;
do $$ begin begin perform research.lockup_timeline_json(gen_random_uuid()); raise exception 'Anonymous timeline allowed' using errcode='ZX001'; exception when insufficient_privilege then null; end; end $$;
reset role;
select 'PASS: exact date-only arithmetic, sourced trigger distinct from filing/holdings dates, conditional-not-liquid, private/static reports, source isolation and explicit refresh' result;
rollback;
