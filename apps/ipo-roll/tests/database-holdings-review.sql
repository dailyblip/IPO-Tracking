begin;
insert into auth.users(id,email) values('70000000-0000-4000-8000-000000000001','holdings-review@example.invalid'),('70000000-0000-4000-8000-000000000002','holdings-customer@example.invalid');
insert into app.entitlements(user_id,active) values('70000000-0000-4000-8000-000000000001',true),('70000000-0000-4000-8000-000000000002',true);
insert into app.reviewers(user_id) values('70000000-0000-4000-8000-000000000001');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"70000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare s record; result jsonb; positions jsonb; checked int:=0; begin
 for s in select o.offering_id,o.party_id,o.shares,p.name from research.ownerships o join research.parties p on p.id=o.party_id join research.offerings i on i.id=o.offering_id join research.companies c on c.id=i.company_id where c.cik='0002141406' loop
  result:=public.ipo_roll_request_liquidity(s.offering_id,s.party_id,gen_random_uuid());
  positions:=result->'positions'; checked:=checked+1;
  if jsonb_array_length(positions)<>1 then raise exception 'Position split or duplication'; end if;
  if positions#>>'{0,category}'<>'unknown' or positions#>>'{0,positionBasis}'<>'post' then raise exception 'Projected holding promoted'; end if;
  if positions#>>'{0,lockupStart}' is not null or positions#>>'{0,lockupEnd}' is not null or positions#>>'{0,marketValue}' is not null then raise exception 'Unsupported date or value'; end if;
  if jsonb_array_length(positions#>'{0,evidence}')<>4 then raise exception 'Footnote/header/basis/lockup evidence missing'; end if;
  if positions#>>'{0,filingAccession}'<>'0001628280-26-062945' or length(positions#>>'{0,documentHash}')<>64 then raise exception 'Version provenance missing'; end if;
  if s.name='Michael Rubiera' and s.shares<>1375666 then raise exception 'Michael position changed'; end if;
  if s.name='Charles Hillman' and s.shares<>226178 then raise exception 'Charles position changed'; end if;
  if s.name='Ericka Harrison' and s.shares<>65695 then raise exception 'Ericka position changed'; end if;
  if public.ipo_roll_request_liquidity(s.offering_id,s.party_id,gen_random_uuid())<>result then raise exception 'Reopen changed report'; end if;
 end loop;
 if checked<>3 then raise exception 'Expected three reviewed positions'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"70000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from research.ownerships) or exists(select 1 from research.liquidity_assessments) or exists(select 1 from app.liquidity_reports) then raise exception 'Internal/private evidence leaked to customer'; end if;
end $$;
reset role;
select 'PASS: three source-backed projected positions, footnotes, version provenance, no invented liquidity/price/date, static reopen and customer denial' result;
rollback;
