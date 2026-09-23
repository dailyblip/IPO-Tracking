-- IPO Roll staging foundation. Independent of the legacy research writer.
create schema if not exists research;
create schema if not exists evidence;
create schema if not exists app;
create schema if not exists ops;
revoke all on schema research,evidence,app,ops from public,anon;
grant usage on schema research,evidence,app to authenticated;
alter default privileges in schema research,evidence,app,ops revoke all on tables from anon,authenticated;
alter default privileges in schema research,evidence,app,ops revoke execute on functions from public;

create table app.entitlements (user_id uuid primary key references auth.users(id) on delete cascade, active boolean not null default false, expires_at timestamptz, created_at timestamptz not null default now());
alter table app.entitlements enable row level security;
create policy entitlement_self on app.entitlements for select to authenticated using (user_id=(select auth.uid()));
grant select on app.entitlements to authenticated;
create function app.has_access() returns boolean language sql stable security invoker set search_path='' as $$ select exists(select 1 from app.entitlements where user_id=(select auth.uid()) and active and (expires_at is null or expires_at>now())) and not coalesce((auth.jwt()->>'is_anonymous')::boolean,false) $$;
grant execute on function app.has_access() to authenticated;
create function public.ipo_roll_has_access() returns boolean language sql stable security invoker set search_path='' as $$ select app.has_access() $$;
revoke all on function public.ipo_roll_has_access() from public,anon;
grant execute on function public.ipo_roll_has_access() to authenticated;

create table ops.ingestion_runs(id uuid primary key default gen_random_uuid(),source_commit text not null,input_sha256 text not null,engine_version text not null,started_at timestamptz not null default now(),finished_at timestamptz,status text not null check(status in ('pending','validated','quarantined','published')),unique(source_commit,input_sha256));
create table ops.releases(id uuid primary key default gen_random_uuid(),run_id uuid not null references ops.ingestion_runs,created_at timestamptz not null default now(),published_at timestamptz);
create table research.companies(id uuid primary key default gen_random_uuid(),cik text unique not null check(cik~'^\d{10}$'),name text not null,sector text,classification text not null default 'unresolved',eligible boolean not null default false);
create table research.filings(id uuid primary key default gen_random_uuid(),company_id uuid not null references research.companies,accession text unique not null check(accession~'^\d{10}-\d{2}-\d{6}$'),form text not null,filed_on date not null,accepted_at timestamptz,file_number text,index_url text not null check(index_url like 'https://www.sec.gov/%'),unique(id,company_id));
create index filings_company_date on research.filings(company_id,filed_on);
create table evidence.sources(id uuid primary key default gen_random_uuid(),filing_id uuid references research.filings,title text not null,url text not null check(url~'^https://'),published_on date not null,rights_status text not null default 'unreviewed' check(rights_status in ('unreviewed','approved','restricted')),unique(url));
create index sources_filing on evidence.sources(filing_id);
create table evidence.documents(id uuid primary key default gen_random_uuid(),source_id uuid not null references evidence.sources,content_sha256 text not null,retrieved_at timestamptz not null default now(),parser_version text not null,unique(source_id,content_sha256));
create table evidence.spans(id uuid primary key default gen_random_uuid(),document_id uuid not null references evidence.documents,excerpt text not null,locator text not null,approved boolean not null default false);
create index spans_document on evidence.spans(document_id);
create table research.offerings(id uuid primary key default gen_random_uuid(),company_id uuid not null references research.companies,root_filing_id uuid not null,current_filing_id uuid not null,registration_file_number text,stage text not null check(stage in ('Pre-pricing','Priced')),filed_on date not null,pricing_date date,final_price numeric(20,6),currency text not null default 'USD' check(currency~'^[A-Z]{3}$'),offering_value numeric(24,2) check(offering_value>=0),value_basis text,filing_price text,ticker text not null default '',signals text[] not null default '{}',source_id uuid not null references evidence.sources,release_id uuid references ops.releases,published boolean not null default false,foreign key(root_filing_id,company_id) references research.filings(id,company_id),foreign key(current_filing_id,company_id) references research.filings(id,company_id),unique(root_filing_id),check((stage='Pre-pricing' and pricing_date is null and final_price is null) or (stage='Priced' and pricing_date is not null and final_price is not null and final_price>0)),check(pricing_date is null or pricing_date>=filed_on));
create index offerings_company on research.offerings(company_id);
create index offerings_current_filing on research.offerings(current_filing_id,company_id);
create index offerings_root_company on research.offerings(root_filing_id,company_id);
create index offerings_source on research.offerings(source_id);
create index offerings_release on research.offerings(release_id);
create index offerings_stage_value on research.offerings(stage,offering_value) where published;
create table research.preliminary_prices(id uuid primary key default gen_random_uuid(),offering_id uuid not null references research.offerings,filing_id uuid not null references research.filings,raw_text text not null,low numeric,high numeric,fixed_price numeric,evidence_id uuid not null references evidence.spans,check((low is not null and high is not null and low>0 and high>=low and fixed_price is null) or (fixed_price is not null and fixed_price>0 and low is null and high is null)));
create index preliminary_offering on research.preliminary_prices(offering_id);
create index preliminary_filing on research.preliminary_prices(filing_id);
create index preliminary_evidence on research.preliminary_prices(evidence_id);
create table research.parties(id uuid primary key default gen_random_uuid(),name text not null,kind text not null check(kind in ('person','organization','group','unresolved')));
create table research.people(id uuid primary key references research.parties(id),identity_verified boolean not null default false);
create table research.ownerships(id uuid primary key default gen_random_uuid(),offering_id uuid not null references research.offerings,party_id uuid not null references research.parties,filing_id uuid not null references research.filings,share_class text,position_basis text not null check(position_basis in ('pre','post','unspecified')),shares numeric check(shares>=0),ownership_percent numeric check(ownership_percent>=0 and ownership_percent<=100),percent_operator text check(percent_operator in ('=','<','>')),percent_raw text,source_row_key text not null,evidence_id uuid not null references evidence.spans,approved boolean not null default false,unique(filing_id,source_row_key));
create index ownership_offering on research.ownerships(offering_id);
create index ownership_party on research.ownerships(party_id);
create index ownership_evidence on research.ownerships(evidence_id);
create table research.roles(id uuid primary key default gen_random_uuid(),person_id uuid not null references research.people,offering_id uuid not null references research.offerings,title text not null,relationship text not null check(relationship in ('Beneficial owner','Director','Executive')),evidence_id uuid not null references evidence.spans,verified boolean not null default false,unique(person_id,offering_id,relationship));
create index roles_offering on research.roles(offering_id);
create index roles_evidence on research.roles(evidence_id);
create table research.biographies(id uuid primary key default gen_random_uuid(),person_id uuid not null references research.people,span_id uuid not null references evidence.spans,approved boolean not null default false,unique(person_id,span_id));
create index biographies_span on research.biographies(span_id);
create table research.claims(id uuid primary key default gen_random_uuid(),biography_id uuid not null references research.biographies,predicate text not null check(predicate in ('education','employment','experience')),object_text text not null,evidence_id uuid not null references evidence.spans,verified boolean not null default false);
create index claims_bio on research.claims(biography_id);
create index claims_evidence on research.claims(evidence_id);
create index span_text_search on evidence.spans using gin(to_tsvector('simple',excerpt));
create table research.listings(id uuid primary key default gen_random_uuid(),company_id uuid not null references research.companies,ticker text not null,exchange_mic text not null,share_class text not null,identity_verified boolean not null default false,valid_from date,valid_to date);
create index listings_company on research.listings(company_id);
create table research.market_prices(id uuid primary key default gen_random_uuid(),listing_id uuid not null references research.listings,provider text not null,provider_instrument_id text not null,quote_at timestamptz not null,retrieved_at timestamptz not null default now(),price numeric not null check(price>0),currency text not null,identity_verified boolean not null default false,licensed boolean not null default false,unique(provider,provider_instrument_id,quote_at));
create index prices_listing_time on research.market_prices(listing_id,quote_at desc);
create table app.user_profiles(user_id uuid primary key references auth.users on delete cascade,display_name text);
create table app.watchlists(id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users on delete cascade,name text not null default 'Watchlist',created_at timestamptz not null default now(),unique(user_id,name),unique(id,user_id));
create table app.saved_ipos(watchlist_id uuid not null,user_id uuid not null references auth.users on delete cascade,offering_id uuid not null references research.offerings,created_at timestamptz not null default now(),primary key(watchlist_id,offering_id),foreign key(watchlist_id,user_id) references app.watchlists(id,user_id) on delete cascade);
create index saved_user on app.saved_ipos(user_id);
create index saved_offering on app.saved_ipos(offering_id);
create table ops.quality_findings(id uuid primary key default gen_random_uuid(),run_id uuid not null references ops.ingestion_runs,record_key text not null,rule_code text not null,reason text not null,created_at timestamptz not null default now());
create index findings_run on ops.quality_findings(run_id);
create index releases_run on ops.releases(run_id);

-- All canonical data is read-only to customers. Only entitled users can read approved rows.
do $$ declare t text; begin
 foreach t in array array['companies','filings','offerings','preliminary_prices','parties','people','ownerships','roles','biographies','claims','listings','market_prices'] loop
 execute format('alter table research.%I enable row level security',t);
 end loop;
 foreach t in array array['sources','documents','spans'] loop execute format('alter table evidence.%I enable row level security',t); end loop;
 foreach t in array array['user_profiles','watchlists','saved_ipos'] loop
 execute format('alter table app.%I enable row level security',t);
 execute format('create policy own_rows on app.%I for all to authenticated using (user_id=(select auth.uid()) and (select app.has_access())) with check (user_id=(select auth.uid()) and (select app.has_access()))',t);
 end loop;
 foreach t in array array['ingestion_runs','releases','quality_findings'] loop execute format('alter table ops.%I enable row level security',t); end loop;
end $$;
create policy companies_read on research.companies for select to authenticated using ((select app.has_access()) and eligible and classification='operating_company');
create policy filings_read on research.filings for select to authenticated using ((select app.has_access()) and exists(select 1 from research.companies c where c.id=company_id));
create policy offerings_read on research.offerings for select to authenticated using ((select app.has_access()) and published and release_id is not null and exists(select 1 from research.companies c where c.id=company_id));
create policy preliminary_read on research.preliminary_prices for select to authenticated using ((select app.has_access()) and exists(select 1 from research.offerings o where o.id=offering_id));
create policy parties_read on research.parties for select to authenticated using ((select app.has_access()));
create policy people_read on research.people for select to authenticated using ((select app.has_access()) and identity_verified and exists(select 1 from research.parties p where p.id=research.people.id and p.kind='person'));
create policy roles_read on research.roles for select to authenticated using ((select app.has_access()) and verified and exists(select 1 from research.offerings o where o.id=offering_id));
create policy owners_read on research.ownerships for select to authenticated using ((select app.has_access()) and approved and exists(select 1 from research.offerings o where o.id=offering_id));
create policy bios_read on research.biographies for select to authenticated using ((select app.has_access()) and approved and exists(select 1 from research.people p where p.id=person_id));
create policy claims_read on research.claims for select to authenticated using ((select app.has_access()) and verified);
create policy listings_read on research.listings for select to authenticated using ((select app.has_access()) and identity_verified);
-- No market quote is published by this initial build; no customer grant/policy on market_prices.
create policy sources_read on evidence.sources for select to authenticated using ((select app.has_access()) and rights_status='approved');
create policy documents_read on evidence.documents for select to authenticated using ((select app.has_access()) and exists(select 1 from evidence.sources s where s.id=source_id));
create policy spans_read on evidence.spans for select to authenticated using ((select app.has_access()) and approved and exists(select 1 from evidence.documents d where d.id=document_id));
grant select on research.companies,research.filings,research.offerings,research.preliminary_prices,research.parties,research.people,research.ownerships,research.roles,research.biographies,research.claims,research.listings to authenticated;
grant select on all tables in schema evidence to authenticated;
grant select,insert,update,delete on app.user_profiles,app.watchlists,app.saved_ipos to authenticated;

create function evidence.source_json(p_span uuid) returns jsonb language sql stable security invoker set search_path='' as $$ select jsonb_build_object('title',s.title,'url',s.url,'date',s.published_on,'excerpt',e.excerpt,'locator',e.locator) from evidence.spans e join evidence.documents d on d.id=e.document_id join evidence.sources s on s.id=d.source_id where e.id=p_span $$;
grant execute on function evidence.source_json(uuid) to authenticated;
create view research.offering_cards with (security_invoker=true) as select o.id,c.name company,o.ticker,coalesce(c.sector,'') sector,f.form,o.stage,o.filed_on as filed,o.pricing_date as "pricingDate",o.offering_value value,o.filing_price as "filingPrice",o.final_price as "finalPrice",null::numeric as "currentPrice",o.signals,(select count(distinct r.person_id) from research.roles r where r.offering_id=o.id)::int as "peopleCount" from research.offerings o join research.companies c on c.id=o.company_id join research.filings f on f.id=o.current_filing_id;
grant select on research.offering_cards to authenticated;
create function public.ipo_roll_offerings(p_query text default '',p_stage text default '',p_min numeric default 0,p_page int default 1,p_saved boolean default false) returns jsonb language sql stable security invoker set search_path='' as $$
 with filtered as (select c.* from research.offering_cards c where (p_query='' or position(lower(left(p_query,160)) in lower(c.company||' '||c.ticker))>0) and (p_stage='' or c.stage=p_stage) and (p_min<=0 or c.value>=p_min) and (not p_saved or exists(select 1 from app.saved_ipos s where s.offering_id=c.id))), paged as (select * from filtered order by filed desc,id limit 25 offset (greatest(1,least(p_page,1000))-1)*25)
 select jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(p)) from paged p),'[]'::jsonb),'total',(select count(*) from filtered),'page',p_page,'pageSize',25) $$;
create function public.ipo_roll_detail(p_id uuid) returns jsonb language sql stable security invoker set search_path='' as $$
 select to_jsonb(c)||jsonb_build_object('source',jsonb_build_object('title',s.title,'url',s.url,'date',s.published_on,'excerpt','','locator','Offering document'),'people',coalesce((select jsonb_agg(jsonb_build_object('id',p.id,'name',p.name,'role',r.title,'relationship',r.relationship,'shares',null,'percent',null,'source',evidence.source_json(r.evidence_id),'biography',(select e.excerpt from research.biographies b join evidence.spans e on e.id=b.span_id where b.person_id=p.id order by b.id limit 1))) from research.roles r join research.people pe on pe.id=r.person_id join research.parties p on p.id=pe.id where r.offering_id=c.id and evidence.source_json(r.evidence_id) is not null),'[]'::jsonb)) from research.offering_cards c join research.offerings o on o.id=c.id join evidence.sources s on s.id=o.source_id where c.id=p_id $$;
-- Search approved person-specific biographies only. Phrase search deliberately avoids inferred aliases.
create function public.ipo_roll_people_search(p_query text,p_relationship text default '',p_page int default 1) returns jsonb language sql stable security invoker set search_path='' as $$
 with matches as (select b.id::text||':'||r.id::text id,jsonb_build_object('id',p.id,'name',p.name,'role',r.title,'relationship',r.relationship,'shares',null,'percent',null,'source',evidence.source_json(r.evidence_id),'biography',e.excerpt) person,c.name company,o.id "offeringId",o.stage,case when position(lower(p_query) in lower(p.name))>0 then 'Name match' else 'Biography text match' end "matchType",evidence.source_json(e.id) evidence
 from research.biographies b join research.people pe on pe.id=b.person_id join research.parties p on p.id=pe.id join evidence.spans e on e.id=b.span_id join research.roles r on r.person_id=p.id join research.offerings o on o.id=r.offering_id join research.companies c on c.id=o.company_id
 where length(p_query) between 2 and 160 and (p_relationship='' or r.relationship=p_relationship) and evidence.source_json(r.evidence_id) is not null and evidence.source_json(e.id) is not null and (position(lower(p_query) in lower(p.name))>0 or (to_tsvector('simple',e.excerpt) @@ phraseto_tsquery('simple',p_query) and exists(select 1 from research.claims cl where cl.biography_id=b.id and exists(select 1 from evidence.spans ce where ce.id=cl.evidence_id and ce.document_id=e.document_id) and position(lower(p_query) in lower(cl.object_text))>0 and evidence.source_json(cl.evidence_id) is not null)))) , paged as(select * from matches order by company,id limit 25 offset(greatest(1,least(p_page,1000))-1)*25)
 select jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(p)) from paged p),'[]'::jsonb),'total',(select count(*) from matches),'page',p_page,'pageSize',25) $$;
create function public.ipo_roll_overview() returns jsonb language sql stable security invoker set search_path='' as $$
 with cards as(select * from research.offering_cards), events as(select id::text||'-filed' id,id "offeringId",company,'Filed' type,filed date,'Initial registration filed' summary from cards union all select id::text||'-priced',id,company,'Priced',"pricingDate",'Final offering terms published' from cards where "pricingDate" is not null), months as(select to_char(d,'YYYY-MM') as month,(select count(*) from cards where to_char(filed,'YYYY-MM')=to_char(d,'YYYY-MM')) filed,(select count(*) from cards where to_char("pricingDate",'YYYY-MM')=to_char(d,'YYYY-MM')) priced from generate_series(date_trunc('month',greatest(date '2026-06-01',current_date-interval '11 months')),date_trunc('month',current_date),interval '1 month') d)
 select jsonb_build_object('tracked',(select count(*) from cards),'filed',(select count(*) from cards where stage='Pre-pricing'),'priced',(select count(*) from cards where stage='Priced'),'median',(select percentile_cont(0.5) within group(order by value) from cards where value is not null),'months',coalesce((select jsonb_agg(to_jsonb(m)) from months m),'[]'::jsonb),'events',coalesce((select jsonb_agg(to_jsonb(e)) from (select * from events order by date desc,id limit 6)e),'[]'::jsonb),'updatedAt',null) $$;
create function public.ipo_roll_saved() returns jsonb language sql stable security invoker set search_path='' as $$ select jsonb_build_object('ids',coalesce(jsonb_agg(distinct offering_id),'[]'::jsonb)) from app.saved_ipos $$;
create function public.ipo_roll_set_saved(p_id uuid,p_saved boolean) returns jsonb language plpgsql security invoker set search_path='' as $$ declare w uuid; begin
 if not app.has_access() then raise exception 'Access denied' using errcode='42501'; end if;
 if p_saved then
 if not exists(select 1 from research.offerings where id=p_id) then raise exception 'Offering unavailable'; end if;
 insert into app.watchlists(user_id,name) values(auth.uid(),'Watchlist') on conflict(user_id,name) do nothing;
 select id into w from app.watchlists where user_id=auth.uid() and name='Watchlist';
 insert into app.saved_ipos(watchlist_id,user_id,offering_id) values(w,auth.uid(),p_id) on conflict do nothing;
 else delete from app.saved_ipos where user_id=auth.uid() and offering_id=p_id; end if;
 return jsonb_build_object('saved',p_saved); end $$;
revoke all on function public.ipo_roll_offerings(text,text,numeric,int,boolean),public.ipo_roll_detail(uuid),public.ipo_roll_people_search(text,text,int),public.ipo_roll_overview(),public.ipo_roll_saved(),public.ipo_roll_set_saved(uuid,boolean) from public,anon;
grant execute on function public.ipo_roll_offerings(text,text,numeric,int,boolean),public.ipo_roll_detail(uuid),public.ipo_roll_people_search(text,text,int),public.ipo_roll_overview(),public.ipo_roll_saved(),public.ipo_roll_set_saved(uuid,boolean) to authenticated;
