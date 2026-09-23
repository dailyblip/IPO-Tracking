# IPO Roll — initial commercial build

An independent React/TypeScript application and Node API in the existing research repository. The legacy Python engine, data, workflows and Pages application are unchanged. This first build implements the approved graphite/teal/blue visual direction.

## Run the visual review

Requires Node 24 and npm.

```sh
cd apps/ipo-roll
npm ci
npm run demo
```

Open http://127.0.0.1:4100. Sample mode serves fictional fixtures from the Node process, clearly labels the interface, and keeps sample saves in the current browser. It never reads or writes the staging database. Sample mode is explicitly refused when NODE_ENV=production.

## Run against staging

Copy `.env.example` to `.env`, set the project's publishable key, and keep IPO_ROLL_DEMO=0. Do not use a secret/service-role key. Run `npm run dev`. The URL is configured for `ipo-roll-staging` only.

Authentication uses Supabase Auth. The Node API verifies the bearer token with `getUser` and checks a server-managed entitlement on every research request. An administrator must provision an account and grant an entitlement before it can use the workspace. This build does not automatically invite users, enable self-signup or send email.

A real legacy snapshot has been imported into private review tables. No canonical research records have been published. Once connected, the workspace intentionally displays an empty approved corpus. It does not silently substitute sample data on a database or authentication error.

For production: `npm run build`, then `npm start`, with server-side environment variables and HTTPS at the hosting boundary. A hosting deployment has not been made. Before launch, complete source import, biography capture/review, field provenance, source-content publication filtering, licensing, production auth configuration and operational recovery checks.

## Included

- Overview with derived metrics, monthly filing/pricing chart and Recent Activity.
- IPO Activity with company/ticker search, stage/size filters, 25-row server pagination and persisted column reordering with keyboard controls.
- Company detail drawer and a single-open person accordion.
- People Search with quoted evidence, relationship filters and an evidence trail.
- User-isolated watchlists with filtering before pagination.
- Methodology, responsive layouts, local fonts and reduced-motion behavior.
- A Node API with validated query bounds, rate limits, security headers and no-store responses.
- A normalized staging foundation: companies, filings, offerings, preliminary price history, people/parties, ownership, roles, biographies, claims, evidence sources/documents/spans, listings/prices, entitlements, profiles, watchlists, saves and ingestion/release records.
- Six application/API tests, browser interaction tests, and transactional database security/evidence tests.

## Staging schema

Migration `20260923042120_ipo_roll_foundation.sql` is applied to project `mpinbkaifvilxmixkzzv`. The file version matches the version recorded by the remote migration tool. The first attempted application failed transactionally on a SQL alias and created no partial schema; the corrected migration succeeded.

Canonical records live in private schemas. RPC functions in `public` are SECURITY INVOKER, with EXECUTE revoked from PUBLIC/anon and granted to authenticated. Entitlements and RLS restrict what they can read. Customer writes are limited to their own profile/watchlist/saves. Every application table has RLS enabled (26 tables after the staging-intake milestone). Ingestion/release/quality tables and market prices intentionally have no customer policies or grants: they default to denial. The security advisor reports eight informational notices after the intake milestone, all for deliberately inaccessible tables: https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy.

No service-role credential is used in customer requests. `app.entitlements` has SELECT-only grants for the current user; customers cannot grant themselves access. Research is read-only. Source functions respect approved rights/evidence and person identity. Quotes are not published in this first build; the UI preserves the column but leaves it blank.

## Evidence search contract

The staging query uses PostgreSQL phrase full-text search on an approved person-specific biography, plus a verified claim from the same document for non-name searches. It requires a verified person and a verified relationship to a published offering. A match always includes both biography and relationship evidence. Results are labeled biography text matches, not automatically education or employment assertions. There is no embedding inference, whole-filing fallback or fund-to-manager wealth attribution.

The initial UI returns one card per matching person/relationship. Consolidating multiple matches under a single company header and deduplicating multiple biographies are follow-up improvements before a large corpus is published. A person with no approved biography is not a biography-search result.

## Migration boundary and remaining work

The engine has NOT been rewritten or redirected. `scripts/inspect-legacy.py` is a read-only assessment, not an importer:

```sh
python scripts/inspect-legacy.py ../../docs/data/filings.json
```

The inspected snapshot had 91 offerings and 804 person/holder entries. Sixteen rows lacked registration file-number evidence in the available preliminary-price provenance. They require SEC lineage resolution before import. Passing basic identity checks is not release approval.

Do not write the public feed directly to the database as if it were fully sourced biographies. Next milestones:

1. Complete source verification on top of the private intake importer: resolve exact root registration lineage and capture field-specific SEC passages before promoting any candidate. The implemented intake records feed-reported observations; it does not claim to have independently verified them.
2. Collect and validate person-specific biographies for all eligible individuals. Preserve exact document versions and spans; never reuse whole-section text as an individual's biography.
3. Add immutable field observations and a complete atomic release manifest; this first schema's publication flag/release association is a foundation, not the complete release-version system proposed in the architecture review.
4. Implement the commercial source/content publication allowlist and rights gate before importing any legacy enrichment.
5. Resolve ownership share-class/time-basis display. The database-backed detail API currently suppresses share amounts rather than collapsing ambiguous positions; the sample workspace illustrates the intended presentation.
6. Add account/team membership and billing when needed. Initial entitlements are per-user, without a billing or team-sharing promise.
7. Configure and test production Auth, backup/restore, monitoring, consent/retention and commercial data rights. Do not publish provider quotes until the license is confirmed.

The commercial design approved in this conversation supersedes the older commercial mockup direction in the root invariants document; legacy-specific behavior remains confined to the legacy application.

## Validation

```sh
npm test
npm run build
npx playwright install chromium
npm run test:browser
```

For a preinstalled browser, set CHROMIUM_PATH. Playwright starts its own sample server and tests desktop/mobile navigation, search, source display, detail expansion, saves/unsaves, persistence, filters, column controls and empty results. Screenshot output defaults to `test-results/screenshots`; IPO_ROLL_SCREENSHOT_DIR can override it.

Run `tests/database-security.sql` and `tests/database-evidence.sql` against staging with an administrative test connection. Both use transactions and ROLLBACK: temporary accounts, entitlements, offerings and evidence are never retained. They verify non-entitled denial, cross-user reads/writes, owner reassignment denial, source-bearing matches, relationship filtering, unsupported-claim suppression, saves/unsaves and the final-price constraint.

No changes have been merged to main or deployed to the legacy Pages application.

## Standalone visual preview

After `npm run build`, run `node --import tsx scripts/build-preview.ts /absolute/path/IPO_Roll_Interactive_Preview.html`. This creates a self-contained, downloadable sample preview with bundled assets and a fictional-data adapter. It contains no credentials, real research records or database connection. It is not the production architecture and is not deployed by this change.

## Milestone 2: reproducible private staging intake

Migration `20260923044523_staging_intake.sql` is applied to staging. Four append-only tables in `ops` hold batches, IPO candidates, field observations and holder candidates. RLS is enabled and customer/anonymous grants are revoked. `ops.import_legacy_intake` is an administrative SECURITY INVOKER function; it is not exposed through the customer API and has no research/publication writes.

The importer reads the feed directly from an exact Git commit, so an uncommitted local feed cannot silently be assigned another commit's provenance. A strict field allowlist removes legacy affiliation enrichment, free-form signals, biographies, quote-provider values and unrelated fields. It preserves source JSON pointers, exact input hash, canonical row hashes, reported SEC index URLs and preliminary-price source metadata. An index link is only a reported source reference: it is **not** a retrieved document, source passage, rights approval or proof of registration lineage. `filed` (current document date) and `filing_date` (reported registration date) remain separate observations.

Holder entries remain candidates, including organizational/group holders; importing a name does not create a verified person or biography. Percentage operators and before/after positions remain separate. No person identities are merged by name. The broader verified biography collection is still required for People Search.

Generate a reviewable batch without contacting the network or database:

```sh
python3 scripts/import_legacy.py \
  --source-commit d453172852c7951dd6cf3e8f0c8a3c1e3a9ec252 \
  --output-dir import-output
npm run test:import
```

Outputs are `intake.json`, `intake.sql`, and `summary.json` in the ignored output directory. Use `intake.sql` only with an administrative connection to **ipo-roll-staging**. There is no automatic writer, scheduled workflow, production redirection or publish switch. Keep these private intake artifacts out of the static frontend and public repository.

The same batch is a transactional no-op on replay. A changed payload under an existing batch ID raises an immutable conflict. A changed source snapshot produces new identities. A future importer contract must use a new version and matching database migration. Updates/deletes of intake history are rejected; corrections append new snapshots. A failing record rolls back the entire function call. This protects administrative intake history; it is not the future immutable customer release manifest.

Verified staging baseline:

| Item | Result |
| --- | --- |
| Source commit | `d453172852c7951dd6cf3e8f0c8a3c1e3a9ec252` |
| Input SHA-256 | `ab3c76814faf293de1d41797a40f869420590bfb48956d239df20d140da99fe8` |
| Batch | `54521902-5f4b-55e7-b605-b07dd2f7fc4a` |
| IPO candidates | 91 |
| Field observations | 1,064 |
| Holder candidates | 804 |
| Missing reported registration number | 16 |
| Canonical offerings / biographies / quotes published | 0 / 0 / 0 |

All 91 candidates await root-lineage verification, operating-company review, exact source-document capture and commercial rights review. This is a commercial migration gate, **not** a finding that all legacy records are incorrect. Sixteen lack even a reported registration file number in the feed; the other 75 still need the exact root filing and current filing linked independently. No historical backfill has been run.

`tests/database-intake.sql` rolls back its fixtures and verifies replay, immutable conflicts, mutation denial, full rollback after a malformed observation, and anonymous/customer denial. Run it administratively against staging. The actual 91-record batch was also replayed: no duplicate batch, observations, holders or findings were added.

Next implementation work: retrieve versioned SEC documents through the existing source-access conventions, resolve the root registration for each candidate, extract exact field passages and person-specific biographies, then review a small complete corpus before adding an atomic publication path. The customer UI and approved design remain available in sample mode while this source work proceeds.

## Milestone 3: SEC artifact capture and biography review packets

`scripts/capture_sec_evidence.py` adds a separate, standard-library-only capture path. It follows the existing engine's `SEC_EDGAR_USER_AGENT` contact convention, keeps requests below four per second, bounds retries/response sizes, and rejects redirects and non-SEC artifact paths. It does not alter the existing ingestion engine or independently reimplement lifecycle/pricing eligibility rules.

For each selected intake record it reads SEC submissions metadata, including all listed archive files, verifies the issuer CIK and current accession/form/date, and resolves one unamended S-1/F-1 root under the exact registration file number. Parallel registrations are kept separate. Missing history, conflicting metadata, ambiguous roots or mismatched preliminary sources stop packet generation. This resolves metadata lineage only; it does not approve the offering's eligibility or pricing facts.

The root, current and reported preliminary primary documents are captured as exact bytes with SHA-256 hashes, retrieval times and URLs. Normalized document text is separately hashed. The packet binds every biography candidate to the current document and precise block/character positions in that normalized snapshot. Only full-name-led paragraphs with biographical language are proposed; surname guesses, whole-section fallbacks, hidden content and mixed named subjects are held back. Names can be supplied explicitly for supported directors/executives absent from the legacy holder list. No affiliation, identity or company relationship is automatically verified.

Run after configuring `SEC_EDGAR_USER_AGENT` with a descriptive application name and a real contact email:

```sh
python3 scripts/capture_sec_evidence.py \
  --intake import-output/intake.json \
  --record-index 0 \
  --archive-dir import-output/sec-artifacts \
  --fetch
```

Add `--person 'Exact Full Name'` to locate another supported individual. Omit `--fetch` to replay previously captured artifacts offline; cached bytes are rehashed and missing/corrupt artifacts fail. URL lookup metadata can advance on a fresh fetch; content-addressed document objects are retained. Review packets pin the specific versions used. Keep captures in the ignored private output directory, never the frontend/public feed.

This milestone was validated with eight synthetic capture tests plus the nine intake tests. **No live SEC artifacts or real biographies have been captured by this new tool yet:** this workspace has no configured SEC contact identity. Existing GitHub Actions secrets were not retrieved, changed or reused. Once a real contact is supplied, run a small live capture and inspect its source spans before importing any evidence into the canonical database.

Remaining limitations: UTF-8 HTML only; conservative paragraph discovery can miss biographies split across paragraphs or using abbreviated names. Explicit passage review and a verified person/company relationship remain required. A successful capture never publishes records, approves rights, or grants customer access. SEC API reference: https://www.sec.gov/search-filings/edgar-application-programming-interfaces.
