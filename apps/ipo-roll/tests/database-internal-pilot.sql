-- Tests the retained pilot through the same RPCs used by the Node application.
begin;
insert into auth.users(id,email) values('40000000-0000-4000-8000-000000000001','reviewer@example.invalid'),('40000000-0000-4000-8000-000000000002','customer@example.invalid');
insert into app.entitlements(user_id,active) values('40000000-0000-4000-8000-000000000001',true),('40000000-0000-4000-8000-000000000002',true);
insert into app.reviewers(user_id) values('40000000-0000-4000-8000-000000000001');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"40000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if (public.ipo_roll_offerings()->>'total')::int<>0 then raise exception 'Pilot leaked to customer'; end if;
 if (select count(*) from research.parties)<>0 then raise exception 'Pilot identities leaked'; end if;
 if (select count(*) from research.claims)<>0 then raise exception 'Pilot claims leaked'; end if;
 if (public.ipo_roll_people_search('University of Michigan')->>'total')::int<>0 then raise exception 'Pilot search leaked'; end if;
 begin insert into app.reviewers values(auth.uid()); raise exception 'Customer self-elevated' using errcode='ZX001'; exception when insufficient_privilege then null; end;
end $$;
select set_config('request.jwt.claims','{"sub":"40000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; oid uuid; begin
 d:=public.ipo_roll_offerings(p_query=>'Accelevation');
 if (d->>'total')::int<>1 then raise exception 'Reviewer pilot missing'; end if;
 oid:=(d#>>'{items,0,id}')::uuid;
 if d#>>'{items,0,filed}' <> '2026-09-22' or d#>>'{items,0,initialFiled}' <> '2026-09-02' then raise exception 'Filing dates conflated'; end if;
 if d#>>'{items,0,filingPrice}' <> '$20.00–$24.00' then raise exception 'Preliminary range wrong'; end if;
 if d#>>'{items,0,finalPrice}' is not null or d#>>'{items,0,currentPrice}' is not null then raise exception 'Unsupported price leaked'; end if;
 select x into d from jsonb_array_elements(public.ipo_roll_people_search('University of Michigan')->'items') x where x#>>'{person,name}'='Brent Jewell';
 if d is null then raise exception 'Source search mismatch'; end if;
 if d#>>'{person,relationship}' <> 'Executive' then raise exception 'Relationship misrepresented'; end if;
 if (public.ipo_roll_people_search('University of Michigan','Beneficial owner')->>'total')::int<>0 then raise exception 'Executive inferred to own shares'; end if;
 if (public.ipo_roll_people_search('Invented University')->>'total')::int<>0 then raise exception 'Unsupported match'; end if;
 d:=public.ipo_roll_detail(oid);
 if jsonb_array_length(d->'people')<>4 then raise exception 'Accordion people missing'; end if;
 perform public.ipo_roll_set_saved(oid,true);
 if (public.ipo_roll_offerings(p_saved=>true)->>'total')::int<>1 then raise exception 'Reviewer watchlist failed'; end if;
 perform public.ipo_roll_set_saved(oid,false);
end $$;
reset role;
select 'PASS: reviewer pilot list, evidence search, accordion, saves, and commercial isolation' result;
rollback;
