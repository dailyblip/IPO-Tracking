-- Source-reviewed Kailera roster/ownership QA. Disposable data always rolls back.
begin;
create temporary table kailera_prior_reports as select id,to_jsonb(r) body from app.liquidity_reports r;
do $$ begin
 if (select count(distinct person_id) from research.roles where offering_id='454f6a5c-4024-511c-a096-54aa9d783cb2' and verified)<>24 then raise exception 'Kailera people incomplete'; end if;
 if (select count(*) from research.ownerships where offering_id='454f6a5c-4024-511c-a096-54aa9d783cb2' and approved)<>19 then raise exception 'Kailera reviewed source quantities missing or duplicated'; end if;
 if exists(select 1 from research.ownerships where offering_id='454f6a5c-4024-511c-a096-54aa9d783cb2' and (position_basis<>'pre' or holdings_as_of<>'2026-03-31'::date or quantity_kind<>'beneficial_total')) then raise exception 'Percentage-only post columns became invented quantities or basis changed'; end if;
 if (select count(*) from research.ownerships where offering_id='454f6a5c-4024-511c-a096-54aa9d783cb2' and shares is null)<>8 then raise exception 'Kailera undisclosed dashes changed'; end if;
 if (select count(*) from research.ownership_attributions a join research.ownerships o on o.id=a.ownership_id where o.offering_id='454f6a5c-4024-511c-a096-54aa9d783cb2')<>11 then raise exception 'Kailera fund/controller attribution incomplete'; end if;
 if (select count(*) from research.roles r join research.parties p on p.id=r.person_id where r.offering_id='454f6a5c-4024-511c-a096-54aa9d783cb2' and p.name in ('Michael Gladstone','Amir Zamani, M.D.') and r.title like 'resigned from our board of directors%')<>2 then raise exception 'Resigned directors presented as current'; end if;
 if exists(select 1 from research.ownerships o join research.parties p on p.id=o.party_id where o.offering_id='454f6a5c-4024-511c-a096-54aa9d783cb2' and p.name='Michael Gladstone') then raise exception 'Atlas overlapping personal row imported'; end if;
end $$;
insert into auth.users(id,email) values
 ('89000000-0000-4000-8000-000000000001','kailera-a@example.invalid'),
 ('89000000-0000-4000-8000-000000000002','kailera-b@example.invalid'),
 ('89000000-0000-4000-8000-000000000003','kailera-c@example.invalid');
insert into app.entitlements(user_id,active) values
 ('89000000-0000-4000-8000-000000000001',true),
 ('89000000-0000-4000-8000-000000000002',true),
 ('89000000-0000-4000-8000-000000000003',true);
insert into app.reviewers(user_id) values ('89000000-0000-4000-8000-000000000001'),('89000000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; entity jsonb; r jsonb; again jsonb; begin
 d:=public.ipo_roll_detail('454f6a5c-4024-511c-a096-54aa9d783cb2');
 if jsonb_array_length(d->'people')<>30 or (select count(*) from jsonb_array_elements(d->'people') x where x->>'biography' is not null)<>16 then raise exception 'Kailera complete person/bio/entity roster lost'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Jamie Coleman';
 if subject->>'biography' not like '%University of Chicago Booth School of Business%' then raise exception 'Biography page continuation lost'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Andrew Kaplan';
 if subject->>'biography' not like '%Harvard Business School%' or jsonb_array_length(subject->'ownershipGrid')<>2 then raise exception 'Kaplan biography continuation or separate fund attribution lost'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Laurie Stelzer';
 if subject->>'biography' is not null or jsonb_array_length(subject->'ownershipGrid')<>1 then raise exception 'Former executive dropped or biography fabricated'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Roderick Wong, M.D.';
 if subject->>'biography' is not null or jsonb_array_length(subject->'ownershipGrid')<>1 then raise exception 'Footnote-only controller dropped or biography fabricated'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Michael Gladstone';
 if jsonb_array_length(subject->'ownershipGrid')<>1 then raise exception 'Atlas overlapping total double counted'; end if;
 select x into strict entity from jsonb_array_elements(d->'people') x where x->>'name'='Entities affiliated with Atlas Venture Fund';
 if entity->>'kind'<>'group' or jsonb_array_length(entity->'ownershipGrid')<>1 then raise exception 'Atlas entity/group basis lost'; end if;
 if not exists(select 1 from jsonb_array_elements(entity->'ownershipGrid') p where p->>'reportedTotal'='4671282' and p->>'positionBasis'='pre') then raise exception 'Atlas single reported quantity mismatch'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Ronald C. Renaud, Jr.';
 if jsonb_array_length(subject->'ownershipGrid')<>1 or not exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') p where p->>'reportedTotal'='1609139' and p->>'holdingsAsOf'='2026-03-31') then raise exception 'Option-only source total changed or projected duplicate created'; end if;
 r:=public.ipo_roll_request_liquidity('454f6a5c-4024-511c-a096-54aa9d783cb2',(subject->>'id')::uuid,'89100000-0000-4000-8000-000000000001');
 if jsonb_array_length(r->'positions')<>1 or exists(select 1 from jsonb_array_elements(r->'positions') p where p->>'category'<>'unknown' or p->>'marketValue' is not null) then raise exception 'Option-only quantity converted into unsupported liquidity/value'; end if;
 again:=public.ipo_roll_request_liquidity('454f6a5c-4024-511c-a096-54aa9d783cb2',(subject->>'id')::uuid,'89100000-0000-4000-8000-000000000002');
 if r<>again then raise exception 'Repeated click changed static report'; end if;
 perform set_config('kailera.report',r->>'id',true);
end $$;
select set_config('request.jwt.claims','{"sub":"89000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports where id=current_setting('kailera.report')::uuid) or exists(select 1 from app.liquidity_reports) then raise exception 'Cross-account report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('454f6a5c-4024-511c-a096-54aa9d783cb2') is not null then raise exception 'Internal source facts exposed to ordinary customer'; end if;
end $$;
reset role;
do $$ begin
 if exists(select 1 from kailera_prior_reports p left join app.liquidity_reports r on r.id=p.id where r.id is null or p.body<>to_jsonb(r)) then raise exception 'Existing static private report changed'; end if;
end $$;
select 'PASS: Kailera management/bios, departed directors, option-only quantities, single temporal quantity, attribution/overlap, missing bios, unknown values, immutable reports and access denial' result;
rollback;
