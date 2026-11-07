-- Read-only staging consistency audit. Run after each batch under an authorized
-- database connection; retain these private per-offering results with the source
-- review receipts. A pass here never proves financial interpretation or coverage.
select o.id offering_id, c.cik, f.accession, now() observed_at,
 d.content_sha256 source_sha256,
 jsonb_build_object(
  'filing_identity',case when f.company_id=o.company_id and root.company_id=o.company_id
    and f.file_number=o.registration_file_number and root.file_number=o.registration_file_number
    then 'pass' else 'fail' end,
  'offering_source_version',case when s.filing_id=o.current_filing_id and d.id is not null
    and (select count(*) from evidence.documents dd where dd.source_id=o.source_id)=1
    then 'pass' else 'fail' end,
  'lifecycle_consistency',case
    when o.stage='Priced' and o.final_price>0 and o.pricing_date is not null
      and o.pricing_date<=current_date then 'pass'
    when o.stage='Pre-pricing' and o.final_price is null and o.pricing_date is null then 'pass'
    else 'fail' end,
  'role_source_alignment',case when not exists(select 1 from research.roles r where r.offering_id=o.id)
    then 'unverified' when exists(
     select 1 from research.roles r join evidence.spans e on e.id=r.evidence_id
      join evidence.documents rd on rd.id=e.document_id
     where r.offering_id=o.id and (not r.verified or not e.approved or rd.id<>d.id))
    then 'unverified' else 'pass' end,
  'holding_source_alignment',case when not exists(select 1 from research.ownerships h where h.offering_id=o.id)
    then 'unverified' when exists(
     select 1 from research.ownerships h join evidence.spans e on e.id=h.evidence_id
      join evidence.documents hd on hd.id=e.document_id
     where h.offering_id=o.id and (not h.approved or not e.approved or hd.id<>d.id or h.filing_id<>o.current_filing_id))
    then 'unverified' else 'pass' end,
  'independent_census_completeness','unverified',
  'full_management_biographies','unverified',
  'all_ownership_rows_and_controllers','unverified',
  'financial_interpretation_and_arithmetic','unverified',
  'lockup_saleability','unverified',
  'live_source_links','unverified',
  'authenticated_browser_journey','unverified'
 ) checks,
 (select count(distinct r.person_id) from research.roles r where r.offering_id=o.id) people,
 (select count(*) from research.ownerships h where h.offering_id=o.id) positions,
 'Structural checks only. Join separately reviewed whole-section receipts by exact offering and source hash. Missing checks never pass.' scope
from research.offerings o join research.companies c on c.id=o.company_id
left join research.filings f on f.id=o.current_filing_id
left join research.filings root on root.id=o.root_filing_id
left join evidence.sources s on s.id=o.source_id
left join evidence.documents d on d.source_id=o.source_id
where o.audience='internal_review' and not o.published
order by f.filed_on,o.id;
