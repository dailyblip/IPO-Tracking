-- A literal biography-text observation is distinct from an education/employment assertion.
-- Search still requires reviewed person-specific evidence, a verified issuer relationship,
-- and the existing audience/entitlement policies. No permissions are broadened.
alter table research.claims drop constraint claims_predicate_check;
alter table research.claims add constraint claims_predicate_check
  check (predicate in ('education','employment','experience','biography_text'));
