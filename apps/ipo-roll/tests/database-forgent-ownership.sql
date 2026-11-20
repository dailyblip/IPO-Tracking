-- Complete reviewed Forgent management biographies and two-class beneficial-ownership grid.
-- Filing dashes remain explicit unknowns; alternative full-option columns and the overlapping
-- aggregate are held. Disposable private reports and test identities roll back.
begin;
create temporary table forgent_test_state as
 select count(*) reports,md5(coalesce(string_agg(to_jsonb(r)::text,'|' order by r.id),'')) checksum
 from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89800000-0000-4000-8000-000000000001','forgent-a@example.invalid'),
 ('89800000-0000-4000-8000-000000000002','forgent-b@example.invalid'),
 ('89800000-0000-4000-8000-000000000003','forgent-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89800000-%';
insert into app.reviewers(user_id) values
 ('89800000-0000-4000-8000-000000000001'),('89800000-0000-4000-8000-000000000002');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89800000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; holder jsonb; r jsonb; begin
 d:=public.ipo_roll_detail('cbdf385c-db79-53e5-8398-9fb375460b3f');
 if jsonb_array_length(d->'people')<>12 then raise exception 'Forgent subject roster incomplete: %',jsonb_array_length(d->'people'); end if;
 if (select count(*) from research.ownerships where offering_id='cbdf385c-db79-53e5-8398-9fb375460b3f')<>48
  then raise exception 'Forgent source positions incomplete'; end if;
 if (select count(*) from research.biographies b join research.roles rr on rr.person_id=b.person_id where rr.offering_id='cbdf385c-db79-53e5-8398-9fb375460b3f' and b.approved)<>11
  then raise exception 'Forgent management biographies incomplete'; end if;
 if exists(select 1 from research.ownerships where offering_id='cbdf385c-db79-53e5-8398-9fb375460b3f' and holdings_as_of<>'2026-01-23')
  or (select count(distinct (share_class,position_basis)) from research.ownerships where offering_id='cbdf385c-db79-53e5-8398-9fb375460b3f')<>4
  then raise exception 'Forgent holdings date, class or basis mismatch'; end if;

 select x into strict holder from jsonb_array_elements(d->'people')x
  where x->>'name'='Investment vehicles controlled by Neos, including the Selling Stockholders';
 if holder->>'kind'<>'group' or jsonb_array_length(holder->'ownershipGrid')<>4
  or not exists(select 1 from jsonb_array_elements(holder->'ownershipGrid') x where x->>'shareClass'='Class A Common Stock' and x->>'positionBasis'='pre' and x->>'reportedTotal'='214261254')
  or not exists(select 1 from jsonb_array_elements(holder->'ownershipGrid') x where x->>'shareClass'='Class A Common Stock' and x->>'positionBasis'='post' and x->>'reportedTotal'='174847681')
  or not exists(select 1 from jsonb_array_elements(holder->'ownershipGrid') x where x->>'shareClass'='Class B Common Stock' and x->>'positionBasis'='pre' and x->>'reportedTotal'='90167635')
  or not exists(select 1 from jsonb_array_elements(holder->'ownershipGrid') x where x->>'shareClass'='Class B Common Stock' and x->>'positionBasis'='post' and x->>'reportedTotal'='73581208')
  then raise exception 'Forgent Neos group grid failed or was duplicated'; end if;
 if exists(select 1 from research.ownerships where offering_id='cbdf385c-db79-53e5-8398-9fb375460b3f' and shares in (168935645,71093244))
  then raise exception 'Alternative full-option scenario was imported'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Gary J. Niederpruem';
 if jsonb_array_length(subject->'ownershipGrid')<>4
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x->>'reportedTotal' is not null)
  or subject->>'biography' not like '%make him well qualified to serve as a director.'
  then raise exception 'Gary source dashes or complete biography failed'; end if;

 select x into strict subject from jsonb_array_elements(d->'people')x where x->>'name'='Peter Jonna';
 if jsonb_array_length(subject->'ownershipGrid')<>8
  or (select count(*) from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}'='control_authority')<>4
  or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') x where x#>>'{attribution,kind}'='control_authority' and x#>>'{reportedHolder,name}'<>'Investment vehicles controlled by Neos, including the Selling Stockholders')
  then raise exception 'Peter Jonna direct unknowns or Neos control attribution failed'; end if;

 r:=public.ipo_roll_request_liquidity('cbdf385c-db79-53e5-8398-9fb375460b3f',(subject->>'id')::uuid,'89900000-0000-4000-8000-000000000001');
 if r->>'version'<>'liquidity/1.6' or jsonb_array_length(r->'positions')<>8
  or exists(select 1 from jsonb_array_elements(r->'positions') x where x->>'category'<>'unknown' or x->>'marketValue' is not null)
  or (select count(*) from jsonb_array_elements(r->'positions') x where x#>>'{attribution,kind}'='control_authority')<>4
  then raise exception 'Forgent private report promoted unknown/control holdings'; end if;
 perform set_config('forgent.report',r->>'id',true);
end $$;

select set_config('request.jwt.claims','{"sub":"89800000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports)
 or exists(select 1 from app.liquidity_reports where id=current_setting('forgent.report')::uuid)
 then raise exception 'Cross-account Forgent report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89800000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('cbdf385c-db79-53e5-8398-9fb375460b3f') is not null then raise exception 'Internal Forgent research exposed'; end if;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_liquidity_report(current_setting('forgent.report')::uuid,gen_random_uuid());
  raise exception 'Anonymous guessed Forgent report access allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ declare baseline forgent_test_state; begin
 select * into baseline from forgent_test_state;
 if (select count(*) from app.liquidity_reports)<>baseline.reports+1 then raise exception 'Unexpected Forgent QA report count'; end if;
end $$;
select 'PASS: full Forgent roster, two-class unknown/grid semantics, controller distinction and private-report denial' result;
rollback;
