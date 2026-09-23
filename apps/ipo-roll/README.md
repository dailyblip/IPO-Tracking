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

No real research records have been imported. Once connected, the workspace intentionally displays an empty approved corpus. It does not silently substitute sample data on a database or authentication error.

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

Canonical records live in private schemas. RPC functions in `public` are SECURITY INVOKER, with EXECUTE revoked from PUBLIC/anon and granted to authenticated. Entitlements and RLS restrict what they can read. Customer writes are limited to their own profile/watchlist/saves. Every one of the 22 application tables has RLS enabled. Ingestion/release/quality tables and market prices intentionally have no customer policies or grants: they default to denial. The security advisor reported only four informational notices about these deliberately inaccessible tables: https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy.

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

1. Build an idempotent staging importer that resolves exact root registration lineage, maps field-specific provenance and quarantines conflicts.
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
