-- Retained September staging cohort. No test users or watchlist changes persist.
begin;
insert into auth.users(id,email) values
 ('60000000-0000-4000-8000-000000000001','month-reviewer@example.invalid'),
 ('60000000-0000-4000-8000-000000000002','month-customer@example.invalid');
insert into app.entitlements(user_id,active) values
 ('60000000-0000-4000-8000-000000000001',true),
 ('60000000-0000-4000-8000-000000000002',true);
insert into app.reviewers(user_id) values('60000000-0000-4000-8000-000000000001');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"60000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if (public.ipo_roll_offerings()->>'total')::int<>0 then raise exception 'Internal filings leaked to customer'; end if;
 if (select count(*) from research.biographies)<>0 then raise exception 'Internal biographies leaked'; end if;
 if (public.ipo_roll_people_search('Harvard')->>'total')::int<>0 then raise exception 'Internal search leaked'; end if;
 begin insert into app.reviewers values(auth.uid()); raise exception 'Self promotion accepted' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
select set_config('request.jwt.claims','{"sub":"60000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; oid uuid; item record; begin
 if (public.ipo_roll_offerings()->>'total')::int<>22 then raise exception 'Month count mismatch'; end if;
 if (select count(*) from research.biographies)<>44 then raise exception 'Biography count mismatch'; end if;
 if (public.ipo_roll_people_search('University of Michigan')->>'total')::int<>2 then raise exception 'Michigan evidence missing'; end if;
 if (public.ipo_roll_people_search('Invented University')->>'total')::int<>0 then raise exception 'Unsupported match'; end if;
 if (public.ipo_roll_people_search('University of Michigan','Beneficial owner')->>'total')::int<>0 then raise exception 'Executive inferred to own shares'; end if;
 d:=public.ipo_roll_offerings(p_query=>'Orion180');
 if d#>>'{items,0,filingPrice}' <> '$15.00–$17.00' or (d#>>'{items,0,finalPrice}')::numeric<>12 or d#>>'{items,0,pricingDate}'<>'2026-09-17' then raise exception 'Orion pricing history lost'; end if;
 if d#>>'{items,0,filed}'<>'2026-09-21' or d#>>'{items,0,initialFiled}'<>'2026-08-20' then raise exception 'Filing dates conflated'; end if;
 oid:=(d#>>'{items,0,id}')::uuid;
 perform public.ipo_roll_set_saved(oid,true);
 if (public.ipo_roll_offerings(p_saved=>true)->>'total')::int<>1 then raise exception 'Saved filter failed'; end if;
 perform public.ipo_roll_set_saved(oid,false);
 if (public.ipo_roll_offerings(p_saved=>true)->>'total')::int<>0 then raise exception 'Unsave failed'; end if;
 d:=public.ipo_roll_offerings(p_query=>'Electra');
 if d#>>'{items,0,filingPrice}' <> '$14.00–$16.00' or (d#>>'{items,0,finalPrice}')::numeric<>15 or (d#>>'{items,0,value}')::numeric<>350000010 then raise exception 'Electra pricing history lost'; end if;
 if (public.ipo_roll_offerings(p_min=>250000000)->>'total')::int<>1 then raise exception 'Size filter failed'; end if;
 for item in select id from research.offerings loop
  d:=public.ipo_roll_detail(item.id);
  if d is null or d->>'currentPrice' is not null then raise exception 'Detail missing or unsupported quote'; end if;
  if d::text ~* 'stanford|#8c1515' then raise exception 'Legacy terminology leaked'; end if;
 end loop;
end $$;
reset role;
select 'PASS: month counts, dates/prices, evidence search, no inferred owners, saves, source filtering and customer isolation' as result;
rollback;
