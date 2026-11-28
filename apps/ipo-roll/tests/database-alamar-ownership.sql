-- Current-source Alamar roster/ownership QA. Requires the neutral-person migration
-- and all people/holdings/component imports. Every disposable account/report rolls back.
begin;
create temporary table alamar_prior_reports as select id,to_jsonb(r) body from app.liquidity_reports r;
insert into auth.users(id,email) values
 ('89000000-0000-4000-8000-000000000001','alamar-a@example.invalid'),
 ('89000000-0000-4000-8000-000000000002','alamar-b@example.invalid'),
 ('89000000-0000-4000-8000-000000000003','alamar-c@example.invalid');
insert into app.entitlements(user_id,active) select id,true from auth.users where id::text like '89000000-%';
insert into app.reviewers(user_id) values ('89000000-0000-4000-8000-000000000001'),('89000000-0000-4000-8000-000000000002');
do $$ begin
 if (select count(*) from research.ownerships where offering_id='1b8df451-1e69-5a30-a949-0e6dc5658339')<>22 then raise exception 'Alamar source row/basis count differs'; end if;
 if (select count(*) from research.ownership_attributions a join research.ownerships o on o.id=a.ownership_id where o.offering_id='1b8df451-1e69-5a30-a949-0e6dc5658339')<>6 then raise exception 'Alamar controller attribution differs'; end if;
 if (select count(*) from research.roles where offering_id='1b8df451-1e69-5a30-a949-0e6dc5658339' and relationship='Footnote-named person')<>4 then raise exception 'Neutral footnote names absent or misclassified'; end if;
 if exists(select 1 from research.ownerships o join research.parties p on p.id=o.party_id where o.offering_id='1b8df451-1e69-5a30-a949-0e6dc5658339' and p.name='Nicholas Naclerio, Ph.D.') then raise exception 'Duplicate personal Naclerio quantity added'; end if;
 if (select count(*) from research.ownership_components c join research.ownerships o on o.id=c.ownership_id where o.offering_id='1b8df451-1e69-5a30-a949-0e6dc5658339')<>8 then raise exception 'Alamar reviewed component count mismatch'; end if;
 if exists(select 1 from research.ownership_components c join research.ownerships o on o.id=c.ownership_id where o.offering_id='1b8df451-1e69-5a30-a949-0e6dc5658339' and o.position_basis<>'pre') then raise exception 'Projected component allocation inferred'; end if;
end $$;
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"89000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; subject jsonb; g jsonb; r jsonb; again jsonb; begin
 d:=public.ipo_roll_detail('1b8df451-1e69-5a30-a949-0e6dc5658339');
 if jsonb_array_length(d->'people')<>19 or (select count(*) from jsonb_array_elements(d->'people') x where x->>'biography' is not null)<>8 then raise exception 'Alamar roster/bios incomplete'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Timothy “Tod” White';
 if subject->>'biography' not like '%University of Michigan Law School%' or jsonb_array_length(subject->'ownershipGrid')<>0 then raise exception 'White continuation lost or group remainder assigned'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Nicholas Naclerio, Ph.D.';
 if subject->>'biography' not like '%University of Maryland College Park%' or jsonb_array_length(subject->'ownershipGrid')<>2 then raise exception 'Naclerio continuation/attribution missing or duplicated'; end if;
 if exists(select 1 from jsonb_array_elements(d->'people') x where x->>'name' in ('Duane Ziping Kuang','Gary Edward Rieschel','Suk Han Grace Lee','Ho Man Lam') and (jsonb_array_length(x->'ownershipGrid')<>0 or x->>'biography' is not null)) then raise exception 'Unestablished Qiming biography/position attribution asserted'; end if;
 if (select count(*) from jsonb_array_elements(d->'people') x where x->>'name' in ('Duane Ziping Kuang','Gary Edward Rieschel','Suk Han Grace Lee','Ho Man Lam'))<>4 then raise exception 'Unquantified footnote people disappeared'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Entities affiliated with Illumina Innovation Funds';
 if subject->>'kind'<>'group' or not exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') p where p->>'positionBasis'='pre' and p->>'reportedTotal'='6128318' and p->>'holdingsAsOf'='2026-03-01') then raise exception 'Fund aggregate/basis lost'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Justin McAnear';
 if jsonb_array_length(subject->'ownershipGrid')<>2 or exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') p where p->>'reportedTotal' is not null) then raise exception 'Filing dashes treated as zero or omitted'; end if;
 select x into strict subject from jsonb_array_elements(d->'people') x where x->>'name'='Yuling Luo, Ph.D.';
 if not exists(select 1 from jsonb_array_elements(subject->'ownershipGrid') p where p->>'positionBasis'='pre' and p->>'reportedTotal'='6207834') then raise exception 'Reviewed mixed total mismatch'; end if;
 select x into strict g from jsonb_array_elements(subject->'ownershipGrid') x where x->>'positionBasis'='pre';
 if g#>>'{components,status}'<>'reconciled' or jsonb_array_length(g#>'{components,items}')<>3 then raise exception 'Luo component breakdown missing'; end if;
 if (select sum((x->>'quantity')::numeric) from jsonb_array_elements(g#>'{components,items}') x) is distinct from (g->>'reportedTotal')::numeric then raise exception 'Luo component sum mismatch'; end if;
 if not exists(select 1 from jsonb_array_elements(g#>'{components,items}') x where x->>'instrument'='common_share' and x->>'attribution'='trust_or_family' and x->>'quantity'='1224152') then raise exception 'Spouse attribution collapsed into personal quantity'; end if;
 r:=public.ipo_roll_request_liquidity('1b8df451-1e69-5a30-a949-0e6dc5658339',(subject->>'id')::uuid,'89100000-0000-4000-8000-000000000001');
 if jsonb_array_length(r->'positions')<>2 or exists(select 1 from jsonb_array_elements(r->'positions') p where p->>'category'<>'unknown' or p->>'marketValue' is not null) then raise exception 'Unsupported mixed-total value/liquidity inferred'; end if;
 if not exists(select 1 from jsonb_array_elements(r->'positions') p where p->>'positionBasis'='pre' and p#>>'{components,status}'='reconciled') or not exists(select 1 from jsonb_array_elements(r->'positions') p where p->>'positionBasis'='post' and p#>>'{components,status}'='incomplete') then raise exception 'Private component snapshot lost basis distinction'; end if;
 again:=public.ipo_roll_request_liquidity('1b8df451-1e69-5a30-a949-0e6dc5658339',(subject->>'id')::uuid,'89100000-0000-4000-8000-000000000002');
 if r<>again then raise exception 'Repeated click regenerated static report'; end if;
 again:=public.ipo_roll_request_liquidity('1b8df451-1e69-5a30-a949-0e6dc5658339',(subject->>'id')::uuid,'89100000-0000-4000-8000-000000000003',(r->>'id')::uuid);
 if again->>'id'=r->>'id' or (select report from app.liquidity_reports where id=(r->>'id')::uuid) is distinct from r then raise exception 'Explicit refresh rewrote original version'; end if;
 perform set_config('alamar.report',r->>'id',true);
end $$;
select set_config('request.jwt.claims','{"sub":"89000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports where id=current_setting('alamar.report')::uuid) or exists(select 1 from app.liquidity_reports) then raise exception 'Cross-account report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"89000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail('1b8df451-1e69-5a30-a949-0e6dc5658339') is not null then raise exception 'Internal evidence exposed to ordinary customer'; end if;
end $$;
set local role anon;
do $$ begin begin
 perform public.ipo_roll_detail('1b8df451-1e69-5a30-a949-0e6dc5658339');
 raise exception 'Anonymous evidence access unexpectedly allowed' using errcode='ZX001';
 exception when insufficient_privilege then null;end;end $$;
reset role;
do $$ begin
 if exists(select 1 from alamar_prior_reports p left join app.liquidity_reports r on r.id=p.id where r.id is null or p.body<>to_jsonb(r)) then raise exception 'Saved private report changed'; end if;
end $$;
select 'PASS: Alamar complete management biographies, neutral footnote people, nonduplicated fund attribution, unknown quantities/value, static reports and account isolation' result;
rollback;
