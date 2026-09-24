-- A staging reviewer is an explicit server-managed permission, never a JWT user claim.
create table app.reviewers(user_id uuid primary key references auth.users(id) on delete cascade);
alter table app.reviewers enable row level security;
revoke all on app.reviewers from public,anon,authenticated;
grant select on app.reviewers to authenticated;
create policy reviewer_self on app.reviewers for select to authenticated using(user_id=(select auth.uid()));
create function app.is_reviewer() returns boolean language sql stable security invoker set search_path='' as $$
select app.has_access() and exists(select 1 from app.reviewers where user_id=(select auth.uid())) $$;
revoke all on function app.is_reviewer() from public,anon;
grant execute on function app.is_reviewer() to authenticated;
alter table research.companies add column audience text not null default 'commercial' check(audience in ('commercial','internal_review'));
alter table research.offerings add column audience text not null default 'commercial' check(audience in ('commercial','internal_review'));
alter table evidence.sources drop constraint sources_rights_status_check;
alter table evidence.sources add constraint sources_rights_status_check check(rights_status in ('unreviewed','approved','restricted','internal_review'));
-- Internal source use is not a commercial-rights approval.
drop policy companies_read on research.companies;
create policy companies_read on research.companies for select to authenticated using((select app.has_access()) and eligible and classification='operating_company' and (audience='commercial' or (select app.is_reviewer())));
drop policy offerings_read on research.offerings;
create policy offerings_read on research.offerings for select to authenticated using((select app.has_access()) and release_id is not null and exists(select 1 from research.companies c where c.id=company_id) and ((audience='commercial' and published) or (audience='internal_review' and not published and (select app.is_reviewer()))));
drop policy sources_read on evidence.sources;
create policy sources_read on evidence.sources for select to authenticated using((select app.has_access()) and (rights_status='approved' or (rights_status='internal_review' and (select app.is_reviewer()))));
-- Scope supporting records to visible relationships, rather than broad entitlement.
drop policy parties_read on research.parties;
create policy parties_read on research.parties for select to authenticated using((select app.has_access()) and (exists(select 1 from research.roles r where r.person_id=research.parties.id) or exists(select 1 from research.ownerships o where o.party_id=research.parties.id)));
drop policy claims_read on research.claims;
create policy claims_read on research.claims for select to authenticated using((select app.has_access()) and verified and exists(select 1 from research.biographies b where b.id=biography_id));
drop policy listings_read on research.listings;
create policy listings_read on research.listings for select to authenticated using((select app.has_access()) and identity_verified and exists(select 1 from research.companies c where c.id=company_id));
create table ops.pilot_manifests(
  release_id uuid primary key references ops.releases,
  review_packet_id uuid not null references ops.sec_review_packets,
  manifest jsonb not null,
  created_at timestamptz not null default now()
);
create index pilot_manifest_packet on ops.pilot_manifests(review_packet_id);
alter table ops.pilot_manifests enable row level security;
revoke all on ops.pilot_manifests from public,anon,authenticated;
create trigger immutable_pilot_manifest before update or delete on ops.pilot_manifests for each row execute function ops.reject_intake_mutation();
