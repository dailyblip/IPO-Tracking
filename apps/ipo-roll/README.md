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

A real legacy snapshot has been imported into private review tables. The current internal review corpus has 22 companies/offerings and 44 sourced biographies; it is available only to entitled reviewers. Ordinary customers still have no commercially published corpus. The application does not silently substitute sample data on a database or authentication error.

For production: `npm run build`, then `npm start`, with server-side environment variables and HTTPS at the hosting boundary. Internal staging is hosted at https://ipo-roll-staging.onrender.com/ with a confirmed reviewer login. Before commercial launch, complete source-content publication filtering, licensing, production auth configuration and operational recovery checks. Earlier milestone sections below describe their state at the time; see the latest milestone for current status.

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

Canonical records live in private schemas. RPC functions in `public` are SECURITY INVOKER, with EXECUTE revoked from PUBLIC/anon and granted to authenticated. Entitlements and RLS restrict what they can read. Customer writes are limited to their own profile/watchlist/saves. Every application table has RLS enabled (29 tables after SEC review storage). Ingestion/release/quality tables and market prices intentionally have no customer policies or grants: they default to denial. The security advisor reports eleven informational notices after SEC review storage, all for deliberately inaccessible tables: https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy.

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

At this intake milestone all 91 candidates awaited root-lineage verification, operating-company review, exact source-document capture and commercial rights review. One internal pilot has since advanced through source review (milestone 5); commercial publication remains blocked. This is a commercial migration gate, **not** a finding that all legacy records are incorrect. Sixteen lack even a reported registration file number in the feed; the other 75 still need the exact root filing and current filing linked independently. No historical backfill has been run.

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

This milestone was validated with eight synthetic capture tests plus the nine intake tests. **This initial tooling-only milestone has now been followed by live capture; see milestone 4 below.** Existing GitHub Actions secrets were not retrieved, changed or reused.

Remaining limitations: UTF-8 HTML only; conservative paragraph discovery can miss biographies split across paragraphs or using abbreviated names. Explicit passage review and a verified person/company relationship remain required. A successful capture never publishes records, approves rights, or grants customer access. SEC API reference: https://www.sec.gov/search-filings/edgar-application-programming-interfaces.


## Milestone 4: live source evidence and account boundary

Live SEC capture succeeded using the business contact supplied by the owner. The source company is Accelevation Holdings Corp. (CIK 0002141406). Its exact registration number is 333-298715, root accession 0001628280-26-060083 (S-1, 2026-09-02) and current accession 0001628280-26-062945 (S-1/A, 2026-09-22). This was source capture for an already staged offering, not a historical backfill.

`prepare_sec_review.py` supports explicitly selected multi-block biographies and relationship passages. It requires exact full names, literal titles and literal search terms; school names split over visual lines remain exact source text with newlines. It never infers education/employment predicates or automatically approves identity, source rights, eligibility or publication. The automatic holder filter also now recognizes the legacy `Individual` capitalization.

Migration `20260923214234_sec_review_packets.sql` creates three private append-only tables. One review packet (`28f6e32e-1374-58df-ac0f-313342d599c8`) and five content-addressed objects are retained in staging: SEC submissions metadata, two raw filings, and two normalized text snapshots. Original bytes are gzip-compressed internally and retain their raw hashes/lengths. Stored compressed hashes were compared with the locally validated objects. This is a small pilot archive; move larger-scale objects to private object storage while preserving these hashes and packet references before expanding broadly.

Four source-selected executive biographies are retained: Michael Rubiera, Charles Hillman, Brent Jewell and Ericka Harrison. A private PostgreSQL phrase-search check for `University of Michigan` returns Brent Jewell, whose source biography explicitly supports the term and his Chief Operating Officer role. These are private review results; the customer People Search corpus remains unpublished. No beneficial-ownership claim is inferred from an executive biography.

Example preparation after reviewing exact block numbers in a captured document:

```sh
python3 scripts/prepare_sec_review.py \
  --packet import-output/sec-artifacts/review-RECORD_ID.json \
  --selections import-output/sec-artifacts/selections.json \
  --archive-dir import-output/sec-artifacts \
  --output-dir import-output/sec-review
```

Each selection specifies `name`, literal `title`, `relationship`, `first_block`, `last_block`, `relationship_first_block`, `relationship_last_block`, and `search_terms`. Output JSON and SQL are private review artifacts; apply the SQL only administratively to staging. Do not put captured documents or biography payloads in this public repository. `tests/database-sec-review.sql` checks the loaded pilot's immutability and customer denial, and rolls back its attempted writes.

GET /api/account now separates verified identity from research entitlement. Signed-in accounts without access receive a clear account state rather than a generic workspace failure. Research APIs/RLS remain gated. Monthly billing is explicitly `not_configured`; no subscription service, pricing or charges were activated. See [the subscription access contract](docs/subscription-access.md).

Validation: 21 Python import/capture/passage tests, seven API tests, four browser tests, the production build, the private SEC storage/access checks and the real internal phrase-search check passed. Browser/API identity tests use simulated Auth responses; production Auth and payment integration remain unconfigured. No merge, domain deployment or production ingestion change occurred.

## Milestone 5: canonical internal pilot and real-data rendering

The staging canonical schema now holds one unpublished internal-review offering, four executive biographies and six literal education claims. Source rights remain `internal_review`, not commercially approved. No beneficial ownership positions or market quotes were inferred. The preliminary range is $20–$24; final price, pricing date and offering value remain unknown. The offering card separates the current amendment date (2026-09-22) from the original registration date (2026-09-02).

`build_internal_pilot.py` validates explicitly selected field passages and biography packet hashes against the captured normalized source. It generates a single atomic SQL transaction and an immutable private pilot manifest. Reapplying that transaction fails on duplicate identities and rolls back. It neither grants access nor runs SQL automatically. All real source inputs and generated payloads remain in ignored `import-output`; none are committed or bundled into the frontend.

Migrations `20260923221859_internal_pilot_access.sql` and `20260923222128_offering_filing_dates.sql` were applied to staging. Internal access requires both an active entitlement and a server-assigned reviewer record. Ordinary entitled customers cannot read the pilot, its people or its search claims, or assign themselves reviewer status. No permanent reviewer account was created.

`tests/database-internal-pilot.sql` verifies the real reviewer search, four-person detail, save/unsave, date and price safeguards, ordinary-customer denial and no fabricated affiliation matches; temporary users and saves roll back. A University of Michigan phrase query returns Brent Jewell with the source biography and Chief Operating Officer relationship. Filtering for beneficial owners returns no match for that executive-only relationship. Existing evidence and security SQL tests also pass.

Validation: 23 Python tests, five browser tests (including the optional private pilot fixture), production build and the database checks pass. The private browser fixture contains actual reviewer RPC results, but browser login/network responses are simulated; this is rendering verification, not a live hosted Auth session. Run that browser case with `IPO_ROLL_PILOT_FIXTURE` pointing to the private captured RPC JSON. Search highlighting normalizes display whitespace while preserving original source text/offsets in storage.

Supabase advisors report no warning/error findings; private/default-denied tables produce informational no-policy notices. Public offerings remain zero. Hosting, permanent reviewer login, commercial source approval and monthly payment activation are still pending. The existing Research Monitor and production ingestion remain operational and unchanged.

## Holdings review preview

The person accordion accepts reviewed, separately identified share-class positions, source footnotes, restriction evidence and verified quote provenance. `shared/holdings.ts` refuses valuation for projected positions, unreviewed evidence, unconfirmed personal economic interest, options, mismatched securities, incompatible timestamps or unreconciled corporate actions. A successful result is a gross market estimate, never cash proceeds or confirmation of saleability. No aggregated wealth total is inferred from overlapping holdings.

The private downloadable preview now includes source-reviewed projected post-offering Class A positions for three pilot executives and their trust footnotes. The fourth person has no individually stated position in that table, which is not treated as zero ownership. All pilot valuations remain blank. This is preview data only: canonical ownership ingestion, quote-provider integration and population through the authenticated database API remain to be implemented. No live market feed, historical backfill or production deployment was enabled. Ten unit/API tests and the production build pass; the standalone preview was checked for holdings, footnotes and blank unsupported valuations.

### On-demand valuation popup

Each person's holdings section now has a Calculate estimated value button. The pure valuation function runs only on click for that person's positions; opening a company/person does not calculate values. The native modal shows position-specific results, evidence links, quote currency/timestamp when present, and explicit unavailable reasons. Positions are not summed into personal wealth. Escape and the close button restore focus without dismissing company research. The private preview has no live quote provider; server-side quote fetching and caching remain pending. Verified production build and real-preview browser interaction, including unavailable-state rendering and keyboard dismissal.

## Milestone 6: reviewed month cohort in authenticated staging

A manually reviewed cohort from the requested August 23–September 23, 2026 window has been imported into staging: 21 additional companies/offerings and 40 additional executive/director biographies, for totals of 22 and 44. This is a selected cohort, not a completeness claim for every IPO in the period. Two bank-conversion candidates remain held for eligibility review. The legacy engine, public feed and schedules are unchanged; no automatic Supabase synchronization is enabled.

`scripts/build_review_batch.py` consumes private intake, captured SEC packets and explicit review selections offline. It verifies content hashes, registration lineage, company identity, literal role/title passages and separately selected pricing evidence, then emits archive transactions, one atomic canonical import transaction and immutable manifests. Source artifacts must be archived before applying the canonical transaction. Exact replay is a no-op; a changed review cannot silently overwrite existing canonical identities. No account grants, publication flags, ownership positions or market quotes are inferred by this importer.

The applied batch archived 97 additional content-addressed objects; stored compressed hashes and original lengths matched the captured originals. All new records remain unpublished and internal-review-only, including source rights. Migration `20260924030228_reviewed_biography_text.sql` adds an explicitly literal `biography_text` claim predicate for reviewed full biographies. It supports text search without converting keywords into inferred education/employment assertions. Relationship evidence remains required and separate.

The entitled reviewer can retrieve 22 offerings and 44 biographies. Verified searches return two University of Michigan matches and eight Harvard matches. Beneficial-owner filtering does not return the executive-only Michigan relationships. Orion's preliminary $15–$17 range is retained alongside its authoritative $12 final price; Electra's preliminary $14–$16 range is retained alongside its $15 final price. Both have sourced September 17 pricing dates. Current market prices remain unknown.

Validation includes four importer tests, a successful rolled-back import rehearsal, successful atomic import and exact replay, archived-byte verification, and passing month-cohort, original-pilot, evidence and security SQL checks. Database checks exercise reviewer detail/search/size filters, saves/unsaves and ordinary-customer denial and roll back their fixtures. The new search input starts empty; targeted browser cases explicitly enter their queries. Browser fixture tests simulate authentication; the owner separately confirmed a successful hosted login.

Canonical holdings ingestion, licensed quote retrieval and monthly billing remain unfinished. Holdings in the downloadable preview are not yet supplied by the database-backed API. The latest security advisor also flags disabled leaked-password protection; resolve the production Auth configuration before commercial launch. Default-denied private tables intentionally have no customer RLS policies.

## Private Liquidity Analysis foundation

The stock holder accordion now offers **Liquidity Analysis**. Each signed-in account requests its own static, timestamped snapshot; reopening returns that saved snapshot and explicit refresh creates another version. Reports and request identifiers are isolated per account by database policies. The API accepts only subject identifiers and a request key; report contents are generated from authorized evidence in the database, never supplied by the client. No secret/service-role key is required.

Migration `20260924164646_private_liquidity_reports.sql` adds reviewed source-linked liquidity assessments and private report storage/RPCs. Categories distinguish current liquidity, conditional future liquidity, illiquid holdings and insufficient evidence. Stale or unsupported assessments cannot establish current liquidity. Subsequent reviewed backfills are tracked below and in the development ledger; absent evidence means unknown, not zero holdings. Quote integration, contractual date extraction and optional AI-assisted interpretation remain follow-up work. The prior valuation demonstration remains available in sample mode only.

Run `tests/database-liquidity.sql` administratively against staging; its fixtures roll back. The test verifies private-account isolation, unknown/stale classification safeguards, immutable customer snapshots, reopen/retry behavior, versioned refresh and revoked access. See `docs/development-log.md` for the next tasks and owner decisions.

### First holdings backfill

Three source-reviewed projected post-offering positions and their trust footnotes are now loaded for the initial company. Liquidity remains unknown; no current ownership, executed lock-up expiry or cash value is inferred. The report preserves table assumptions and the planned-lock-up passage, and the UI explicitly labels projected positions and exposes the source accession/hash. Existing account reports remain static until explicitly refreshed.

`scripts/build_holdings_review.py` prepares this narrow, explicitly reviewed import from captured artifacts without network or database access. Its generated transaction retains a private immutable manifest and is a no-op on exact replay. Run `tests/test_holdings_review.py` for input safeguards and `tests/database-holdings-review.sql` for the retained cohort's evidence and isolation checks. Both sources and generated import payloads stay private. For source-rich browser verification, supply `IPO_ROLL_LIQUIDITY_FIXTURE` alongside `IPO_ROLL_PILOT_FIXTURE`; these fixtures contain real captured evidence but simulate authentication.

### Dated holdings review

The offline holdings reviewer also accepts the explicit `dated-pre-common` profile for reviewed 424B4 rows with simple Class A/B common-share footnotes. It preserves the source table's holdings as-of date separately from the filing date and rejects mixed instruments or trust/fund attribution requiring further review. Do not use it to import aggregate RSU/option totals as ordinary shares. The generated manifest and SQL stay in private ignored output directories; execute only after evidence review and a rollback rehearsal.

### Reviewed mixed-award components

Migration `20260925151220_reviewed_ownership_components.sql` adds shared, source-linked components with read-only, source/entitlement-scoped RLS. The narrow `reviewed-mixed-awards` profile accepts a complete enumerated common-share/RSU/option footnote only when its quantities reconcile exactly to one beneficial total and holder/date associations are explicit. Unknown grammar, instrument, identity, condition or total fails closed. Components are not additional positions; trust attribution does not establish personal economic ownership and award-underlying shares are not confirmed issued shares.

New `liquidity/1.2` snapshots display the reported total and reconciled components with exact evidence. Mixed totals remain insufficient-evidence classifications, with no market value; missing components are not silently omitted from an apparently complete breakdown. Existing saved reports remain unchanged until the user explicitly refreshes. Run `tests/test_review_components.py` and staging rollback `tests/database-components.sql` alongside the existing privacy/holdings suites. Reviewed internal staging coverage is eight parent positions, including three mixed totals with eight components; no licensed quotes or automated lock-up release dates are present.

Liquidity snapshot v1.1 includes `holdingsAsOf` and `filingDate`; `holdingsDate` is a deprecated filing-date alias for older clients. Missing holdings dates remain unknown. Existing private reports are immutable, including their original dates and source versions.
