-- Synthetic internal-review facts and disposable accounts; everything rolls back.
-- Run administratively after the visible_ownership_subjects migration.
begin;
create temporary table ownership_subject_original_reports as select id,report from app.liquidity_reports;
insert into auth.users(id,email) values
 ('98000000-0000-4000-8000-000000000001','subjects-reviewer-a@example.invalid'),
 ('98000000-0000-4000-8000-000000000002','subjects-reviewer-b@example.invalid'),
 ('98000000-0000-4000-8000-000000000003','subjects-customer@example.invalid'),
 ('98000000-0000-4000-8000-000000000004','subjects-no-access@example.invalid');
insert into app.entitlements(user_id,active) values
 ('98000000-0000-4000-8000-000000000001',true),
 ('98000000-0000-4000-8000-000000000002',true),
 ('98000000-0000-4000-8000-000000000003',true);
insert into app.reviewers(user_id) values
 ('98000000-0000-4000-8000-000000000001'),('98000000-0000-4000-8000-000000000002');
do $$ declare company uuid; filing uuid; prior_filing uuid; src uuid; prior_src uuid;
 doc uuid; prior_doc uuid; run uuid; release uuid; offering uuid; person uuid; span uuid;
 named_person uuid; hidden_span uuid; i integer;
 names text[]:=array['Roleless Owner Fixture','Neutral Named Fixture','Unapproved Owner Fixture',
  'Wrong Source Fixture','Unverified Identity Fixture','Prior Filing Fixture'];
begin
 insert into research.companies(cik,name,classification,eligible,audience)
 values('0000098001','Ownership subject transactional fixture','operating_company',true,'internal_review') returning id into company;
 insert into research.filings(company_id,accession,form,filed_on,index_url)
 values(company,'0000098001-26-000001','S-1','2026-01-03','https://www.sec.gov/Archives/edgar/data/98001/000009800126000001/0000098001-26-000001-index.html') returning id into filing;
 insert into research.filings(company_id,accession,form,filed_on,index_url)
 values(company,'0000098001-26-000002','S-1','2026-01-02','https://www.sec.gov/Archives/edgar/data/98001/000009800126000002/0000098001-26-000002-index.html') returning id into prior_filing;
 insert into evidence.sources(filing_id,title,url,published_on,rights_status)
 values(filing,'Synthetic current source','https://www.sec.gov/Archives/edgar/data/98001/000009800126000001/synthetic.htm','2026-01-03','internal_review') returning id into src;
 insert into evidence.sources(filing_id,title,url,published_on,rights_status)
 values(prior_filing,'Synthetic prior source','https://www.sec.gov/Archives/edgar/data/98001/000009800126000002/synthetic.htm','2026-01-02','internal_review') returning id into prior_src;
 insert into evidence.documents(source_id,content_sha256,parser_version) values(src,repeat('8',64),'synthetic-test') returning id into doc;
 insert into evidence.documents(source_id,content_sha256,parser_version) values(prior_src,repeat('9',64),'synthetic-test') returning id into prior_doc;
 insert into ops.ingestion_runs(source_commit,input_sha256,engine_version,status)
 values('ownership-subject-test','ownership-subject-test','synthetic-test','published') returning id into run;
 insert into ops.releases(run_id) values(run) returning id into release;
 insert into research.offerings(company_id,root_filing_id,current_filing_id,stage,filed_on,source_id,published,release_id,audience)
 values(company,filing,filing,'Pre-pricing','2026-01-03',src,false,release,'internal_review') returning id into offering;
 for i in 1..array_length(names,1) loop
  insert into research.parties(name,kind) values(names[i],'person') returning id into person;
  insert into research.people(id,identity_verified) values(person,i<>5);
  insert into evidence.spans(document_id,excerpt,locator,approved)
  values(case when i in(4,6) then prior_doc else doc end,
   case when i=2 then 'Neutral Named Fixture is named as an upstream partner. Example University is mentioned for another person. Individual issuer ownership and control are not established.'
    else names[i]||' is a disclosed shareholder with 10 Class A common shares.' end,
   'Synthetic ownership/footnote row',true) returning id into span;
  if i=2 then
   named_person:=person;
   insert into research.roles(person_id,offering_id,title,relationship,evidence_id,verified)
   values(person,offering,'named as an upstream partner','Footnote-named person',span,true);
  else
   insert into research.ownerships(offering_id,party_id,filing_id,share_class,position_basis,shares,source_row_key,evidence_id,approved,quantity_kind)
   values(offering,person,case when i=6 then prior_filing else filing end,'Class A common shares','pre',10,
    'synthetic-subject-'||i,span,i<>3,'beneficial_total');
  end if;
  if i=1 then
   perform set_config('subject_test.owner',person::text,true);
   perform set_config('subject_test.owner_span',span::text,true);
   -- A source-invisible role must not suppress a visible ownership fallback.
   insert into evidence.spans(document_id,excerpt,locator,approved)
   values(doc,'Roleless Owner Fixture is a synthetic officer.','Unapproved synthetic role',false) returning id into hidden_span;
   insert into research.roles(person_id,offering_id,title,relationship,evidence_id,verified)
   values(person,offering,'synthetic officer','Executive',hidden_span,true);
  end if;
 end loop;
 perform set_config('subject_test.offering',offering::text,true);
 perform set_config('subject_test.named',named_person::text,true);
 perform set_config('subject_test.doc',doc::text,true);
end $$;
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"98000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $$ declare d jsonb; p jsonb; r jsonb; neutral jsonb; begin
 d:=public.ipo_roll_detail(current_setting('subject_test.offering')::uuid);
 if jsonb_array_length(d->'people')<>2 then raise exception 'Fallback missed a source-proven subject or exposed an ineligible one: %',d->'people'; end if;
 select x into strict p from jsonb_array_elements(d->'people')x where x->>'id'=current_setting('subject_test.owner');
 if p->>'relationship'<>'Beneficial owner' or p->>'role'<>'Disclosed shareholder'
  or p->>'biography' is not null or jsonb_array_length(p->'roles')<>1
  or p#>>'{source,excerpt}' not like 'Roleless Owner Fixture%'
  or p#>>'{ownershipGrid,0,reportedTotal}'<>'10' then raise exception 'Ownership fallback source/quantity/role changed'; end if;
 select x into strict neutral from jsonb_array_elements(d->'people')x where x->>'id'=current_setting('subject_test.named');
 if neutral->>'relationship'<>'Footnote-named person' or neutral->>'biography' is not null
  or jsonb_array_length(neutral->'ownershipGrid')<>0 then raise exception 'Neutral footnote person promoted or lost'; end if;
 if (public.ipo_roll_people_search('Neutral Named Fixture','Footnote-named person')->>'total')::int<>1
  or (public.ipo_roll_people_search('Neutral Named Fixture','Beneficial owner')->>'total')::int<>0
  or (public.ipo_roll_people_search('Example University','Footnote-named person')->>'total')::int<>0
  then raise exception 'Neutral name/filter/biography search leaked attribution'; end if;
 r:=public.ipo_roll_request_liquidity(current_setting('subject_test.offering')::uuid,
  current_setting('subject_test.owner')::uuid,'98100000-0000-4000-8000-000000000001');
 if r#>>'{positions,0,category}'<>'unknown' or r#>>'{positions,0,marketValue}' is not null
  or r#>>'{positions,0,reportedTotal}'<>'10' then raise exception 'Roleless owner report promoted or incomplete'; end if;
 perform set_config('subject_test.saved',r::text,true);
 perform set_config('subject_test.report',r->>'id',true);
 r:=public.ipo_roll_request_liquidity(current_setting('subject_test.offering')::uuid,
  current_setting('subject_test.named')::uuid,'98100000-0000-4000-8000-000000000002');
 if jsonb_array_length(r->'positions')<>0 or r->>'relationship'<>'Footnote-named person'
  then raise exception 'Neutral footnote report invented holdings'; end if;
end $$;
reset role;
-- Later reviewed roles supersede the display fallback without duplicating people
-- or silently rewriting the already saved analysis.
do $$ declare span uuid; begin
 insert into evidence.spans(document_id,excerpt,locator,approved)
 values(current_setting('subject_test.doc')::uuid,'Roleless Owner Fixture is a director.','Synthetic role',true) returning id into span;
 insert into research.roles(person_id,offering_id,title,relationship,evidence_id,verified)
 values(current_setting('subject_test.owner')::uuid,current_setting('subject_test.offering')::uuid,'director','Director',span,true);
end $$;
set local role authenticated;
do $$ declare d jsonb; p jsonb; r jsonb; begin
 d:=public.ipo_roll_detail(current_setting('subject_test.offering')::uuid);
 if jsonb_array_length(d->'people')<>2 then raise exception 'New role duplicated ownership fallback'; end if;
 select x into strict p from jsonb_array_elements(d->'people')x where x->>'id'=current_setting('subject_test.owner');
 if p->>'relationship'<>'Director' or jsonb_array_length(p->'ownershipGrid')<>1 then raise exception 'Role/grids were not retained'; end if;
 r:=public.ipo_roll_request_liquidity(current_setting('subject_test.offering')::uuid,
  current_setting('subject_test.owner')::uuid,'98100000-0000-4000-8000-000000000003');
 if r<>current_setting('subject_test.saved')::jsonb then raise exception 'Saved snapshot changed after a new shared role'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"98000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from app.liquidity_reports where id=current_setting('subject_test.report')::uuid)
  or public.ipo_roll_liquidity_report(current_setting('subject_test.offering')::uuid,current_setting('subject_test.owner')::uuid) is not null
  then raise exception 'Cross-account report existence leaked'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"98000000-0000-4000-8000-000000000003","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail(current_setting('subject_test.offering')::uuid) is not null
  or (public.ipo_roll_people_search('Neutral Named Fixture')->>'total')::int<>0 then raise exception 'Customer saw internal subjects'; end if;
end $$;
select set_config('request.jwt.claims','{"sub":"98000000-0000-4000-8000-000000000004","role":"authenticated"}',true);
do $$ begin
 if public.ipo_roll_detail(current_setting('subject_test.offering')::uuid) is not null then raise exception 'Unentitled account saw subjects'; end if;
 begin
  perform public.ipo_roll_request_liquidity(current_setting('subject_test.offering')::uuid,current_setting('subject_test.owner')::uuid,'98100000-0000-4000-8000-000000000004');
  raise exception 'Unentitled report creation allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
set local role anon;
do $$ begin
 begin perform public.ipo_roll_detail(current_setting('subject_test.offering')::uuid);
  raise exception 'Anonymous detail allowed' using errcode='ZX001';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
do $$ begin
 if exists(select 1 from ownership_subject_original_reports original
  left join app.liquidity_reports current on current.id=original.id
  where current.id is null or current.report<>original.report) then raise exception 'Existing report changed'; end if;
end $$;
select 'PASS: current-source roleless owner fallback, neutral footnote names, no inferred holdings/biographies, exact subject identity, no duplicate roles, immutable reports and access denial' result;
rollback;
