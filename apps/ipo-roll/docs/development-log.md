# IPO Roll development handoff

## September 28 UTC: site-wide holdings gap; first multi-company quantities batch

Owner clarified that blank holdings affect the full site, not only Neutron.
Fresh staging audit found only **5 of 94 offerings** with any ownership records.
Held the shared development lock; branch/PR started at `6245f6b3` with no other
pending changes. Legacy engine/feed/schedules and source access are unchanged.

**Applied and verified:** 38 source-reported table positions across 19 people:
Buda Juice 18 (nine people, January filing), Green Circle two (one person,
January filing), Neutron 18 (nine people, July filing). Before-IPO and projected
after-IPO positions are alternative snapshots, never summed. Ten Neutron records
retain undisclosed dashes as null; explicit Buda zeros remain zero. These are not
38 issued common-share positions. Totals now **94 offerings / 323 people / 320
biographies / 52 positions / 16 components / zero quotes**; **8 offerings have
positions and 86 have none**. No new offerings/biographies or complete month/census.
The nine existing private reports were checksum-identical through every applied
transaction and replay (one more real report than the preceding handoff existed
before this batch). No test users/reports persist.

`build_disclosed_holdings.py` removes the old dependency on completing liquidity
interpretation before displaying reviewed table quantities. Explicit review still
requires exact source hashes/current registration, full HTML row/cell boundaries,
ordered headers, identity/alias, security class, holdings date, basis and notes.
This addresses normalized text gluing adjacent numeric cells without guessing
how to split them. Rejects repeated scenarios, duplicate people/rows, wrong source
and existing-holding overlaps. Exact replay adds nothing. All new positions are
reported beneficial totals with incomplete components and unknown liquidity.
No values, quotes, cash proceeds, personal attribution or lock-up dates inferred.

Reviewed nuances: Buda's source percentages conflict with its stated post-offering
denominator; percentages remain unimported/unresolved while literal quantities
and the conflict are retained. Director grants and redemption assumptions remain
projected. Buda holdings date is January 7 (prospectus), not January 8 filing.
Green Circle uses November 28, 2025 current table, not its older incorporation
schedule; Chan is imported once despite repeating in the same table, with his
company attribution retained. Its full-overallotment alternative is not added.
Neutron uses May 31 basis; option/RSU/trust mixed totals retain complete linked
notes, not a claim that all are issued personal common shares. Proposed selling
columns do not become completed-sale proceeds. Entity/group rows still require
separate attribution review. All nine Neutron management rows are now represented.

**QA performed:** rollback rehearsal, apply and exact replay for each company;
reviewer RPC compared every imported total/null, basis, date, source and evidence.
Tested ordinary-customer/anonymous denial, guessed report IDs, cross-account
read/write denial, reopen idempotency, explicit refresh/new version and unchanged
prior reports. All 98 Python tests and 18 Node/API tests pass; production build
passes with existing bundle-size/lucide warnings. Captured real reviewer RPC and
new report rendered in desktop and 390px browser tests, including footnotes,
reopen/refresh, mobile overflow and focus. Screenshots inspected. Authentication
is simulated for browser tests; live reviewer login is still unverified.

Read-only structural audit ran across all 94: no identity/source/lifecycle failures;
eight holdings-source checks pass, 86 are unverified. Whole-table completeness,
financial interpretation, independent census and live source-link checks are not
promoted to pass. A private ordered company/source-hash coverage queue preserves
all 94 records, with the first no-position cursor at BitGo. Presence of records
is not completeness, including the existing eight offerings.

**Publication:** data is applied and served by existing authenticated APIs. Generic
importer/tests and concise truthful grid labels are prepared for the commercial
branch; confirm commit and Render asset before calling these code changes deployed.
No migrations or new dependencies. No owner action needed; no paid quotes/AI.

Private recovery bundle in `ops.sec_artifacts`:
`843fe36988e19c151af412b91375c5cb0b61ae671f01f2da8eb0e6cc1b56ae30`,
1,423,672 raw bytes; gzip SHA-256
`62f207fa1880c2a44acd2b94fb12996c336ae5d6f1056eface805de0937ef5ad`.
Verified storage hashes. Contains 27 review/manifests/SQL/QA/queue/fixture files from
`import-output/holdings-cohort/`; raw SEC documents remain in their prior archives.
No private payload is committed or bundled in the frontend.

**Next work:** use the new review contract for BitGo (`0001628280-26-003180`),
EquipmentShare (`0001628280-26-003334`), PicPay, Ethos, York in oldest-first batches;
reconcile all table rows and named controllers, not just people with biographies.
Continue instrument/attribution decomposition and holder-specific restrictions
for imported totals; only then populate compatible historical value/liquidity.
Maintain independent SEC census/new-discovery-to-import and full-biography QA
work alongside holdings. The automatic end-to-end ingestion/QA pipeline and
site-wide backfill remain incomplete. Do not replay applied batches blindly.

## September 27 night: Neutron missing people corrected; controller search and cohort QA

Publication verified: commercial commit `de6f061945a4a337c10c9467bd1d44e9c687dddd`.
All five ownership-history guard status lists were clear before commit. Render
serves `index-BwX4kXBy.js` with SHA-256
`a0f25dbfbc344a31aa5ae734ac3f0545e9a032f5166ba2a402ad661f4abce5b0`,
identical to the tested build. Staging health is 200/ok; real anonymous search and
Neutron detail endpoints return 401. Test Research Monitor run `36373335487` passed.
Controller import replay passed all reviewer/access/report checks and left counts
323 people / 320 biographies / 14 positions / eight reports unchanged. No live
signed-in browser check or full financial-coverage claim. No owner action needed.

Owner reported missing Neutron Holdings people. Started from clean published
`f2eacfca0a8028b7b610b7976361aa86ec03f7e4` under the shared development lock.
Restored and hash-verified its exact current 424B4, accession
`0001628280-26-046635`, CIK `0001699963`, source SHA-256
`5db0f3af0446d7c0875124e02f032611ebad446b1de8e9bd2634a873f50ae44a`.
The earlier import contained only two people despite nine management-table rows.
Their existing biographies were complete; the other seven had not been imported.

**Applied:** seven full July-filing biographies (Joseph Kraus, Zhoujia Brad Bao,
Elizabeth Hamren, Andrew Macdonald, Brandon Pedersen, James Rowan and Sarah Smith).
Kraus retains the filing's retired-President qualifier. Whole management-table
blocks 2181–2217 and biography blocks 2218–2241 reconcile to **nine complete
biographies**, including page continuations. Inventoried every ownership-table
row (16) and all 10 footnotes. These inventories are not quantity completeness.

Also applied three separately labeled **Footnote controller** records: Marc
Andreessen, Benjamin Horowitz and Abigail P. Johnson. Reviewed full footnotes 7/8
and searched the whole retained filing for their names; no full biography is
present for these three. AH shared voting/dispositive authority and upstream FMR
control remain distinct from personal economic ownership. FMR's 49% voting-power
statement is not a Neutron holding. No fund quantity is assigned to a person.
Neutron detail now returns **12 people / nine full biographies**.

**Implemented/applied:** migration `20260928030724_footnote_controller_name_search`
adds the separate relationship without changing RLS/access grants. Name search
now includes reviewed people without biographies; shared footnotes cannot match
biography-text searches. Importer requires explicit control-attribution review.
Roster reconciliation now flags missing named controllers inside reviewed notes.
**Tested/deployed app:** relationship filter, accurate people-results label and
concise controller/missing-biography notices. See publication verification above;
data and RPC changes are also applied.

Verified staging: **94 offerings / 323 people / 320 biographies / 14 positions /
16 components / zero quotes / eight unchanged private reports**. No new offering,
ownership quantity, valuation, quote, private-report version or commercial access.
Both imports passed rollback rehearsals and transactional applications with exact
biography/source/name checks, controller-only filtering, null personal quantities,
no invented biographies, ordinary-customer/anonymous denial and full-row private
report fingerprints. No temporary QA users remain. **94 Python tests, 17 Node/API
tests and production build pass**. Captured reviewer RPC browser journey passes
at desktop/390px, including controller evidence, 12-person count, private report
reopen/explicit refresh and overflow. Screenshots inspected. Authentication/report
creation were simulated in this browser test; live owner-login remains unverified.

**Repeatable QA run:** new read-only `scripts/audit_staging_data.sql` returns a
source-versioned per-offering check matrix. All 94 pass filing identity, offering
source-version and lifecycle consistency. Role-source checks: 82 pass, 12
unverified; holding-source checks: five pass, 89 unverified. Financial interpretation,
full rosters, census completeness, link liveness and live browser checks remain
unverified in this structural audit and need their separate evidence receipts.
The existing source-start audit scanned 54/94 retained sources available locally,
with 40 requiring restoration, and found 440 unmatched paragraph-start leads
across 46 offerings. These include aliases/false positives, not 440 verified people.
No source/accuracy/completeness pass is inferred from missing data or a parser test.
The full automatic discovery-to-import/rotating-content-audit pipeline is still
unfinished; a prompt or this read-only audit is not that completed pipeline.

Recovery: ignored `import-output/neutron-review/` contains exact reviews, both
manifests, import/rollback/QA SQL, full section reconciliation, current snapshot,
reviewer RPC fixture, cohort inventory and both audit results. Applied manifests
are in `ops.pilot_manifests`. Private recovery bundle in `ops.sec_artifacts`:
`fe779649558dcfe0f78f4eb932edc7e09d87bb615bd6878cd47d6d305f7cc92e`
(1,057,420 raw bytes; gzip SHA-256
`453062864d83f8c3dbfecb21cd073ea4c3f702e8fe3943a76322a77df32c94f0`, verified).

Next: represent the seven remaining Neutron entity/group table rows and review
its instrument/conversion/attribution components before loading quantities. Restore
40 missing local artifacts; continue oldest-first whole-roster review, resolve
aliases from the audit and advance the January 14 independent census batch.
Connect discovery, explicit review/import and the per-offering QA receipts into
the durable staging pipeline; do not mark it implemented merely from instructions.
No owner action is needed for these steps. Paid quotes remain deferred. All
production/Research Monitor, source-rights, report-privacy and commit guards remain.

## September 27 evening: continuing development restored; 31 more biographies applied

Owner asked why development stopped and explicitly requested a continuing process.
Verified that IPO Roll Development was disabled while the separate nightly review
was enabled. Re-enabled the existing hourly development task, replaced its stale
September 26 handoff, and specified resumable batches, shared-lock coordination,
unblocked-task progression and durable checkpoints. Kept the 6 PM digest separate.
No duplicate automation or always-running-worker claim. The existing instruction
to return to 8 AM/noon/4 PM after independently verified historical completion
remains; that completion gate has not been met.

Started from clean `888ae35e2a06f6320f0b576abb8a4c4f49dc0eff`, fetched the branch,
checked PR #581 and live counts, and acquired the shared development lock.
Restored Buda Juice and Green Circle final source objects from private staging
artifacts and verified their raw and normalized hashes. Applied four reviewed
biography supplements to existing offerings:

| Filing month | Company | Added biographies | Complete selected management roster |
| --- | --- | ---: | ---: |
| January | Buda Juice | 9 | 9 |
| January | Green Circle | 6 | 6 |
| January | Ethos | 10 | 13 |
| February | Agomab | 6 | 11 |

All 39 management biographies now match complete reviewed section partitions
and a fresh canonical database snapshot. Buda's CEO appears twice in its source
table but remains one person. Clint Bowers retains the biography's CFO Nominee
label (the table says CFO); Green Circle nominees retain nominee titles. Retained
cross-page continuations including Christopher Capozzi, Roelof Botha, Mark Mullin,
David Epstein, Colin Bond, Marie Quintana and Lai Tai Yan. These are source-dated
roles, not inferred current appointments. Ownership quantities remain separate.

Added explicit `relationship_name` alias review to `build_people_supplement.py`
for reviewed differences between a table and biography, with a required reason,
literal source-name/title validation and unchanged canonical biography identity.
Used for Buda's Don/Donald Short and Mo/Mohammad Hayat variants. No automatic
identity merging, inferred affiliation or holdings was introduced.

Verified staging: **94 offerings / 313 people / 313 biographies / 14 positions /
16 components / zero quotes / eight private reports**. Each batch passed rollback
rehearsal and transactional application with exact full-biography/source/name
search checks, ordinary-customer denial and anonymous denial. Full-row saved-report
fingerprints stayed unchanged in all transactions. **92 Python tests pass**,
including alias-review rejection cases; `git diff --check` passes. No new IPO,
position, valuation, schema or frontend/backend application change. The data is
served by existing authenticated APIs; real signed-in browser QA was not performed.
The offline tooling is being checkpointed on the commercial branch. No application
deployment is needed for the data/tooling; no claim of a newly deployed UI.

Recovery: ignored `import-output/roster-pivot/{ethos,agomab,buda,green-circle}/`
contains reviews, manifests, import/QA SQL, whole-section reviews, snapshots and
coverage receipts. `prepare_followup.py`, `prepare_restored.py` and
`reconcile_followup.py` reproduce this review work. Applied manifests are durable
in `ops.pilot_manifests`. Roster checkpoint in `ops.sec_artifacts`:
`0a0e39cc31140c38a85e08ec80b39fea3514dbc5dbdfe0da9c4b2e95d2633661`
(159,640 raw bytes; compressed SHA-256
`78d139f8c3c481d91ed8ad194734dcbde56b5670f18fd1ea312d4ef1d8997579`, verified).
Source packets for the restored pair can be recovered from their original applied
manifest's `capture`; raw objects remain private in `ops.sec_artifacts`.

Next: implement evidence-backed ownership-only/entity/group/controller roster
representation and name search without fabricating quantities, then ingest the
reviewed table components/footnotes. Continue January 14 independent IPO census
classification from the prior checkpoint. No month or full holder coverage is
complete. Paid quote providers remain deferred; no owner action is needed for
these next tasks. Preserve all source-rights, report-privacy and commit guards.

## September 27 Pacific: comprehensive research pivot; 31 biographies and two option positions applied

Owner approved the full researcher pivot and said to continue. Started at clean
`fde7309044a84dbb11685d3c4c0c52ba8e7b74fc`, fetched the commercial branch, checked
draft/open PR #581 and live staging counts, and acquired the shared development
lock. Added `comprehensive-research.md` with independent completion criteria for
IPO census, management, biographies, ownership rows, footnotes, quantities,
historical value and private liquidity. An imported company is never a completed
company by itself.

Corrected another structural omission: commercial capture and passage selection
rejected whole SEC biographies mentioning Stanford. The owner's subsequent
**every available biography** requirement supersedes that blanket evidence
filter. Source education/employment is now institution-neutral; no Stanford
branding, counters, semantic highlighting, special search or legacy enrichment
was restored. Legacy intake field restrictions remain. Also fixed discovery
mistaking a seeded name and its credential-bearing source prefix for two
different people. Discovery remains unapproved and never merges identities.

Applied **31 missing complete biographies** from retained January final
prospectuses, without reimporting offerings:

| Company | Added | Management biographies now reconciled |
| --- | ---: | ---: |
| Aktis Oncology | 11 | 14 |
| BitGo | 7 | 10 |
| EquipmentShare | 6 | 9 |
| York Space Systems | 7 | 10 |

Reviewed management-table identities, source spelling/credential differences and
full biography boundaries. Preserved Michael Sherman's, Brian Murray's, John
Weinstein's, Kirk Konert's and Andrew Boyd's cross-page continuations. Confirmed
Chen Fang's already-imported biography was complete; did not duplicate it. York
nominees remain labeled nominees. Andrew Levin's source-disclosed forthcoming
resignation is in his role text and full biography. No unsupported current-role
or personal-wealth claim was inferred.

Added `reconcile_people_roster.py`: a private offline comparison of reviewed
whole-section partitions against an exact-source, timestamped canonical
snapshot. It rejects unaccounted/overlapping blocks, source/issuer mismatch,
unreviewed aliases and duplicate canonical names, and compares complete biography
text. All **43 named management biographies** across these four reviewed filings
match staging. It does not certify exhaustive source discovery or company/holder
completeness. Aktis's entire selected ownership table is accounted for: 11
individual rows, four affiliated-entity aggregates and one overlapping group
row. All 11 footnotes are inventoried. Entity representation, named footnote
controllers, attribution and remaining quantity review are explicitly pending.

Separately reviewed/applied two option-only positions now that their people exist:
Akos Czibere, 124,805 underlying voting-common option interests; Ken Herrmann,
75,103. Both are source-dated October 31, 2025 and described as exercisable within
60 days of that date. Full source notes, table conversion assumptions and
conditional lock-up/exercise restrictions are retained. These are not issued
shares, confirmed current holdings, personal cash, intrinsic option values or
proof of present saleability. No historical/current price estimate was added.

Current verified staging: **94 offerings / 282 people / 282 biographies / 14
positions / 16 components**. Each biography and holdings batch passed rollback
rehearsal then transactional application with reviewer RPC/source/search tests,
customer/anonymous denial and unchanged full-row private-report fingerprints.
Exact replay of all five releases left counts unchanged. **91 Python tests pass**;
`git diff --check` passes. A private option-QA assertion initially treated the
component envelope as an array; corrected it to `components.items` and reran
successfully before application. A revised legacy-key SQL assertion initially
included non-object JSON nodes; corrected and verified that factual biography
text passes while legacy affiliation keys fail. The old month fixture's fixed
counts were not rerun against the expanded live dataset.

No frontend/backend application or schema changes were needed. Applied data is
available through the existing authorized APIs; signed-in visual/browser QA was
not performed in this pass. Source rights remain internal_review/unpublished,
ordinary customers denied. Saved private reports were not generated or refreshed.
No purchases, new AI/quote provider, main/Monitor/production feed/schedule changes.

Recovery: ignored `import-output/roster-pivot/` contains the four explicit people
reviews, generated manifests/SQL, per-batch QA, canonical snapshot and complete
section reviews/results; `aktis-options/` contains the two position reviews and
QA. All five applied manifests are immutable in `ops.pilot_manifests`. Roster
checkpoint SHA-256 `58cf2cd8b378a2bad78b3a050e5ce07b5c56e6bb4616f018fda80be8a0e28e39`
is durable in `ops.sec_artifacts` (183,469 raw bytes, compressed SHA-256
`c640ea30cd17c0470a8417efa2a2f01a6f843385eaaaf95cefb6556fa8e361a1`, verified).
Do not rerun the pre-holdings biography QA assertion requiring empty grids after
these two positions have been added; use the current holdings/coverage checks.

Next: finish January management reconciliation (including Ethos and independent
additions), restore missing retained sources, and add ownership-only people /
organization / group / footnote-controller representation with proper name
search and attribution. Aktis controllers pending include the MPM, Vida and
Blue Owl named control parties; do not treat their fund totals as personal
wealth. Continue the independent SEC IPO census separately; no new IPO was added
in this pass and no month is complete. No owner decision or paid service needed
for these next tasks. This commercial-branch checkpoint contains the validated
tooling/docs; the data above is already applied. All five active/pending workflow
status queries were clear before publication. No application deployment is
required for this offline tooling change.

## September 27: missing people and biographies confirmed; first supplements applied

Owner clarified the requirement: **every person with a biography in the filing must have that biography attached and searchable**, regardless of whether they have a reviewed ownership position. Ownership-table-only people must not disappear for lack of a biography. A complete people roster, biography coverage and quantified holdings coverage are separate review tasks. Preserve the compact expandable biography UI; this is a data-completeness correction.

Confirmed the structural gap in live staging: initially 94 offerings, 235 people/biographies (188 Executive and 47 Director relationships), only 12 reviewed ownership positions across five offerings, and no separately imported Beneficial owner relationships. The company RPC reads `research.roles`, not every source-table row. Commercial capture looked for biographies using previously supplied owner names; its narrative filter also missed some nominee wording/short wrapped starts. Neither importing an IPO nor importing a few executive biographies establishes complete people/ownership coverage.

Added `discover_people.py` and integrated its unapproved independent name discovery into commercial `capture_sec_evidence.py`. It covers director nominees and expected board service, including short wrapped paragraph starts; it never confirms identity, complete biography or ownership. Added `build_people_supplement.py` to append explicit source-reviewed biographies/relationships to an already imported offering without reimporting the offering, guessing quantities or rewriting evidence. It verifies raw/normalized hashes, issuer/registration/current source, complete reviewed biography selection, role evidence, deterministic identities, conflicts and exact replay. Missing biographies require an explicit review disposition rather than silently excluding the person.

Applied **16 additional people and complete biographies** from retained SEC sources: Orion180 +7 (now all nine named management biographies; source accession `0001628280-26-062794`) and Accelevation +9 (now all 13 named management biographies; `0001628280-26-062945`). Orion's additions include the Chief Legal Officer, who is not listed in its principal-shareholder table. Ryan Jesenik, Robert Deutsch and Paul Donahue retain biography continuations across page breaks, including their education. Director nominees remain labeled as nominees/expected board members. All eight distinct individuals named in Orion's ownership table now have person records, but Darling Strategic Investments LLC and Craig Darling's separately attributed control footnote still require appropriate entity/authority handling; no claim that the entire beneficial-ownership table or its quantities is complete.

Both batches were rehearsed/rolled back, applied with reviewer RPC/search and customer/anonymous denial checks, then replayed with no duplicates. Current staging: **94 offerings / 251 people / 251 biographies / 12 ownership positions**. Private-report full-row fingerprints stayed unchanged inside each import transaction; no report generation, holdings or pricing changes. Checks include all newly added biographies/source links, no invented holdings, search for biography terms beyond page breaks, and named research for a person absent from the ownership table. These are database role/RPC tests, not live-login or visual QA. Data is served through the existing authenticated app without a frontend deployment.

Added `audit_people_coverage.py`. The first cross-company checkpoint scans 51 locally retained current filing sources from the 94-offering inventory; 43 source objects must be restored from the private archive. It records **462 unmatched candidate paragraph starts across 46 offerings**, NOT 462 confirmed missing people: aliases/credentials, duplicates and false positives require review. Discovery is not a completeness denominator and does not reconcile all table rows/footnotes. Private audit checkpoint SHA-256 `0996a753424ddc602ee90d1fda724827a27ab7ebf6fa49ee3017b827e78f43cf` (219,825 bytes) is archived in `ops.sec_artifacts`. Local files: `import-output/people-coverage-{inventory,audit}.json`; exact supplemental reviews/SQL/QA/manifests in `import-output/month/orion-people-supplement/` and `import-output/pilot/people-supplement/`. The two applied review manifests are also durable in `ops.pilot_manifests`.

Validation: **84 Python tests pass**, including independent discovery without seeded names, full biography selection, nominee/wrapped-start cases, identity/evidence rejection, missing-bio dispositions, corruption rejection and unavailable-source accounting. `git diff --check` passes. Tooling prepared for commercial-branch publication under the ownership-history guard; the 16-person data correction is already applied/verified. Next: restore remaining source objects, reconcile management and beneficial-owner tables company by company, attach every available full biography, review aliases explicitly, retain entities/groups as such, and then import reconciled holdings/footnotes. No need for owner-supplied missing names or a paid provider. Main, Research Monitor, legacy Pages/JSON, production schedules and access policies are unchanged.

## September 27: compact researcher drill-down and approved value comparison

Owner approved retained stake value and documented IPO sale proceeds side by side, with a sourced default Liquidity Analysis and optional hypothetical price/date exploration. Acquired the shared development lock and started from clean `6cdbb032c8d668200242098d0a3941d26d303c9c`; PR #581 remains open/draft. This requested UI work does not replace the ongoing oldest-first backfill.

Implemented paired value cards above the stock/award grid, with equal emphasis on mobile and desktop. Collapsed biography/relationship passages, duplicate ownership context and long assessment/source metadata; kept class, quantity, pre/post basis, holdings/filing dates, attribution and conditional lock-up boundaries visible. Private reports reuse the compact grid with saved category labels and an explicit as-of/staleness strip. Counts are clearly position records, not shares or dollars. All source passages, exact calculation terms, filing accession/hash and review validity remain accessible. The dialog now uses the available desktop width. Existing report requests, reopening, explicit refresh and authorization paths are unchanged; no stored report was rewritten.

The two value amounts remain **Not established**: the current reviewed position contract has no validated compatible historical IPO-price basis or actual holder sale-proceeds record. Removed the stale claim that a paid quote is required for the historical filing-based estimate. Do not fill these cards from aggregate beneficial totals, issuer offering proceeds or unmatched share classes. Next valuation work is the reviewed historical-price/sale-evidence contract and ingestion, not a paid provider.

Added collapsed, local-only hypothetical share/price inputs and a date comparison against the saved report's reviewed conditional boundaries. Exact integer-cent arithmetic avoids floating-point/large-integer rounding; malformed and out-of-bounds inputs fail closed. Hypothetical outputs do not classify liquidity, fetch prices, create requests or modify saved reports. No quantity is prefilled from an ambiguous position. Inputs reset on dialog close or report refresh. Date comparisons never label a boundary as permission to sell.

Validation performed: TypeScript/production build, **17 Node/API/render/calculation tests**, and `git diff --check` passed. New tests cover exact cents, large values, invalid inputs, leap/invalid dates, retained evidence, separate award components, old saved-report quantity compatibility and unchanged input snapshots. Updated the existing fixture browser journey for the compact layout, scenario isolation/reset and paired mobile cards, but **did not run it**: the supported cloud browser rejected the local preview with `net::ERR_BLOCKED_BY_CLIENT`. Desktop/mobile screenshots and live authenticated interaction remain unverified. The public staging HTTP request also timed out after 20 seconds; this is not a confirmed outage. Build succeeds with lucide directive and bundle-size warnings.

Published commercial implementation commit `41fd1f2be6e94bea66dafbb1591467f2bbec1bdc` after all five ownership-history active/pending status queries were clear. Local branch is reconciled cleanly with the remote commit. Research Monitor run `36358997136` was still in progress at the last check. The cloud browser successfully opened the staging login page (so the earlier shell timeout did not establish an outage), but its DOM still referenced the preceding `index-CHP2uPZn.js` bundle. The new expected assets are `index-D_y1qZbu.js` and `index-D9gnMbrz.css`; **deployment of this UI is not yet verified**. No signed-in reviewer session was present, so authenticated visual QA remains pending. No schema, source import, private report, paid provider, Research Monitor, production feed/schedule or main-branch change. Next: verify the new asset and deployed researcher journey in an authorized session, then continue source-reviewed January census/holdings work. No new owner decision is needed for this layout.

## September 27 Pacific: integrate exact-filing review dispositions

Verified clean branch checkpoint `b0aae024`, acquired the shared development lock, and confirmed staging remains 94 offerings / 235 biographies / five private reports. Added hash-pinned disposition inputs to `reconcile_sec_census.py`. It verifies retained original source bytes, normalized text, selected passage offsets/text and SEC URL CIK/accession, then requires exact index form/date identity. Duplicate/overlapping reviews, staged-offering conflicts, missing index rows, altered evidence and issuer-wide exclusions fail closed. This consumes human-reviewed classification; it does not infer exclusion from company names or prose heuristics.

Applied the four previously archived January dispositions to the private census: **94 exact snapshots / 240 issuer-lineage rows / 4 reviewed excluded filings / 10,723 unreviewed rows**, preserving all 11,061 scoped index rows. Other filings for those issuers remain unresolved. Recovery: `import-output/year-2026/census-reviewed-94/inventory.json`; source checkpoint and evidence paths remain in the prior entry. Seven targeted census tests and all **78 Python tests** passed. No canonical offering, biography, holding, quote, saved report, database schema or application UI changed in this step.

Published as `d6c868b55ae8b1dcae9b324b19dab3ccd53409be` after the ownership-history guard cleared. Research Monitor run `36328125948` and isolated capture run `36328121647` passed. All 48 captured files passed authenticated decryption and manifest hash/length checks. Encrypted source backup `github-actions-artifact-10934214265.zip` is durable as `libfile_2c10814fae1c819198ead1580378c855`; local recovery is `import-output/actions-capture-36328121647/`.

Reviewed January 8–12 finals: Soren `0001213900-26-002346` (blocks 7–8) and Bleichroeder II `0001213900-26-002472` (8–9) explicitly describe blank-check companies; Rubico `0001171843-26-000207` is a follow-on unit offering, with a prior November 2025 public offering documented at block 2186 (current cover 11–15). Those exact filings are excluded. Atlas Critical Minerals `0001493152-26-001253` is **held**, not excluded or imported: cover blocks 6–9 and block 368 describe an OTCQB-to-Nasdaq uplisting and public offering, requiring further scope/lineage review. No guess that the national-exchange listing was an initial IPO. The reconciler now preserves an explicit held status separately from excluded filings, with regression coverage.

Second evidence-linked disposition checkpoint `ab7a9b122b8985766ff65c3f0daa25b0f6348bda09baf591148f9c38a7b465e5` is archived in staging `ops.sec_artifacts` (12,671 bytes; compressed checksum verified). Reconciliation with both checkpoints gives **94 exact snapshots / 240 issuer-lineage rows / 7 reviewed exclusions / 1 held filing / 10,719 unreviewed rows**. Private output `import-output/year-2026/census-reviewed-eight/inventory.json` retains all 11,061 rows. All 78 Python tests pass after held-status support. Canonical staging remains 94 offerings / 235 biographies; no holdings, quotes or private reports were changed. Public health request timed out with no response in 15 seconds; website availability and live browser/login QA are unverified in this pass, not a confirmed service outage.

Next: continue January 14 source classification (Plus Therapeutics, BriaCell, Signing Day Sports, OneIM), retain Atlas for explicit uplisting scope/lineage review, and reconcile pending registration activity as well as final prospectuses. No owner action or paid service is needed for the next source batch. Full independent census and holdings coverage remain incomplete.

## September 27 UTC: PicPay and AGI reviewed, applied and verified

Applied two independently indexed IPOs from encrypted capture run `36295785408`: January PicPay (9 biographies) and February AGI Inc (14 biographies). Staging is now **94 offerings / 235 biographies / 12 positions / 14 components / zero quotes**. These are additions beyond the original SEC Monitor inventory, not a completeness claim. Both remain `internal_review`, unpublished and inaccessible to ordinary customers.

PicPay: CIK `0001841644`, root `0001213900-26-001029`, final `0001213900-26-009315`, PICS, preliminary $16–$19, final $19, pricing date January 28, 2026, gross base offering $434,285,717. AGI: CIK `0002081206`, root `0001753926-26-000110`, final `0001753926-26-000308`, AGBK, preliminary $15–$18, final $12, pricing date February 10, 2026, gross base offering $240,000,000. Prospectus dates are distinct from next-day SEC filing dates. Both issuers' initial registrations leave the range blank; reviewed amendments supply it. Gross issuer offering amounts are not holder proceeds. No holdings, saleability, personal wealth or current-price claims were inferred from biographies.

Fixed the offline review importer's rejection of explicit `US$` preliminary ranges while preserving the exact source passage. Regression coverage rejects reais, inconsistent currency notation and mismatched precision. **75 Python tests passed.** All 530 archived objects were verified against expected raw byte counts and compressed checksums; three large PicPay source files remain losslessly chunked with full logical hashes. Sources, normalized text, reviewed spans, manifests and chunk reconstruction metadata are durable in staging `ops`; no private source payload is in Git/frontend.

The database import rehearsal rolled back to 92 offerings; application then raised counts to 94/235. Exact replay produced no duplicates. Reviewer-role QA passed final/preliminary prices, pricing/filing/root dates, all 23 biography/source displays, named search and save/unsave. Customer and anonymous denial, including guessed offering ID, passed. Search counts: Michigan 4, Harvard 31, Goldman Sachs 6, investment banking 13. All five private Liquidity Analysis reports remained unchanged (same full-row fingerprint). These are database role/API checks, **not live reviewer login or desktop/mobile browser QA**; no authorized live session was used. Data is served by the existing authenticated app; no application deployment or schema change is required by this batch.

Recovery: ignored `import-output/actions-capture-36295785408/reviewed/` contains bound intake, review selections, generated release and QA. PicPay release `5127330b-7ed3-52a4-90fe-4134ddd92a84`; AGI release `3cdcd431-5955-5a87-84e3-7a1a42ddb3c4`. Do not reimport blindly. Discovery IDs were rebound to exact retained Q1 SEC index rows before import.

Published as `e6b3a0770303e87a73cff4b02a624096284e6070` after all five ownership-workflow active/pending status checks were clear. Research Monitor tests `36296615955` and private capture `36296613333` both passed. Public staging `/api/health` returned HTTP 200 with `ok` / `staging`. No frontend application change was made or visually verified in this pass.

The next four January candidate filings were captured and source-classified: Brazil Potash `0001193125-26-000752` is a resale registration (blocks 8–10, 13); STAK `0001493152-26-000242` is a follow-on unit offering after its February 2025 IPO (9, 15); Art Technology Acquisition `0001213900-26-001875` is an explicit blank-check company (8–9); Jefferson Capital `0001104659-26-002168` is a secondary offering after its June 2025 IPO (9–11, 178). These dispositions apply to those exact filings, **not issuer-wide exclusions**. No offering/biography was imported from this second capture. Its ten source documents and metadata (42 files) passed authenticated decryption plus manifest hash/length checks. Durable encrypted backup `github-actions-artifact-10924286195.zip` is `libfile_3f3a76d7c9ec8191823132d32c68ed04`, ciphertext SHA-256 `44c0bc356791bc9ec0ec0d9dcc5d88e3803ad8a28b38a1596610b25afbe8642c`. Local recovery: ignored `import-output/actions-capture-36296613333/`. Source-linked disposition checkpoint is archived in staging `ops.sec_artifacts` at SHA-256 `19885b338331d03cda4ac268d1c2ca984163dc404397d5a4446d0ff194ccd88f` (10,134 raw bytes).

Fresh 94-offering comparison is `import-output/year-2026/census-staged-94.json`; regenerated `census-94/inventory.json` accounts for 94 exact snapshots, 240 known-issuer lineage rows, and 10,727 unmatched filing rows. The inventory's three-way classifier does not yet consume the four separate reviewed dispositions above: subtracting them or excluding other filings of the same issuer automatically would be incorrect. Next, integrate exact-filing dispositions into census tracking, then continue oldest-first captured source review. Independent census classification, cutoff freshness and holder/footnote coverage remain incomplete. No new owner decision, quote subscription or AI service is needed; paid quotes remain deferred. Research Monitor, production schedules, main and commercial UI remain unchanged.

## September 27 UTC: reuse the existing SEC contact in isolated Actions capture

Owner authorized using the Research Monitor's existing `SEC_EDGAR_USER_AGENT` secret. Added a separate commercial-branch-only capture job with read-only repository permissions, bounded serial SEC retrieval, and encrypted-only artifact upload. It uses the secret in place, never exports it, and requires no staging database secret. First request selects the two public 424B1 CIK/accession identities already recorded in the census (PicPay and AGI); it does not approve or import either offering. See `sec-capture-actions.md` for recovery and subsequent bounded batches.

Four targeted tests pass for request bounds/identity validation, missing-contact rejection, authenticated encryption/decryption and tamper rejection, and workflow branch/secret/upload boundaries. Published as `a4460208ca7b36917971b91c5a7a4567199c6dd4`; live capture run `36295785408` and Research Monitor test run `36295787365` both passed. The job successfully used the existing SEC contact without revealing/copying it.

Downloaded/decrypted the encrypted artifact and verified all **24 captured files** against the manifest's hashes and lengths. **Six SEC documents** are captured: PicPay root F-1 `0001213900-26-001029` (21,943,698 bytes), F-1/A `0001213900-26-005383` (22,115,089), final 424B1 `0001213900-26-009315` (21,852,289); AGI root F-1 `0001753926-26-000110` (5,920,829), F-1/A `0001753926-26-000217` (6,338,000), final 424B1 `0001753926-26-000308` (6,255,491). These actual captured byte counts/hashes supersede earlier index-listed size estimates; no document was truncated. Both candidates remain unreviewed/unimported, with no new biography, holding, quote, or private report produced.

Recovery: private plaintext is under ignored `import-output/actions-capture-36295785408/evidence/`; archive objects are in its `archive/` child. Ciphertext SHA-256 is `bd3ce13e78717fc53c1ee9aea92681037ab08aa31771be4730dab14d7445c49e`. A durable encrypted backup is `github-actions-artifact-10923971317.zip` (`libfile_31366d29cb608191b030a69ddad7fec4`), recoverable with the separately retained owner-private key described in `sec-capture-actions.md`. The local-shell missing-contact condition no longer blocks capture: use this isolated Actions path for subsequent source batches. Next, bind these discovery packets to independently validated SEC-index intakes, review January PicPay first, and apply only after evidence and staging QA. No database mutation or application deployment was performed by this setup.

## September 27 UTC: oversized SEC evidence archive support

Implemented the remaining large-document tooling gap in this checkpoint. Live capture stays bounded at 64 MB, while any logical source above the existing 20 MB immutable-object ceiling is archived as ordered 128 KB content-addressed chunks plus a canonical reconstruction manifest. The original full-file SHA-256 and byte count remain authoritative. Review packets and pilot manifests bind the logical file to the exact manifest/chunk hashes; all stored rows still satisfy the unchanged `ops.sec_artifacts` 20 MB constraint. No database limit, schema, grant or customer-facing source surface was expanded.

Seventy Python tests pass. A separate 21.85 MB incompressible simulation produced 171 chunks plus one manifest, reconstructed byte-for-byte, revalidated the full hash and kept the largest encoded SQL payload below 171 KB. Staging's SEC immutability/customer/anonymous-denial rollback suite passed. Fresh staging counts remain **92 offerings / 212 biographies / 12 positions / 14 components / zero quotes / five unchanged private reports**. This checkpoint changes capture/review tooling only; it did not capture PicPay, import an offering, deploy application code, refresh a private report or claim census completion.

The current execution service still lacks its configured `SEC_EDGAR_USER_AGENT`, so live SEC capture was not attempted and no contact was fabricated. Once that already-approved operational setting is restored through the service, the confirmed 21.85 MB PicPay source can use this path instead of truncation or a blob-limit increase. Continue oldest-first 424B1 and registration-group review from the comprehensive census. Paid quote feeds remain deferred; historical IPO-price estimates remain separate future filing-based work under the owner's evidence rules.

## September 26 Pacific / September 27 UTC: systematic census omissions fixed

Owner requested comprehensive reconciliation rather than a list of user-supplied missing companies. Acquired `/tmp/ipo-roll-development.lock`; started from clean `f67dfb8741e3b135b0a95bfae11399a3bb8f112a`. Restored and hash-verified all three full SEC indexes from eleven retained private chunks. The new offline census checks CIK/accession identities, expands beyond the prior five forms, and records known-issuer unmatched filings separately rather than assuming that issuer coverage means registration coverage. See `backfill-2026.md` for all monthly filing-row counts and exact provenance. Inventory: 11,061 scoped filing rows / 2,192 CIKs, not an IPO count; 92 exact current staged matches, 236 lineage reviews, 10,733 unreviewed candidates.

Fixed commercial intake, capture and reviewed import to accept 424B1 final prospectuses with the existing explicit eligibility/pricing safeguards. PicPay and AGI are independently discovered examples of this systematic missing-form issue, not a user-selected scope. Fixed legitimate co-registrant accession handling in index parsing, while ambiguous selected issuers still fail closed. All 68 Python tests pass; no raw source payloads or candidate records added to Git/frontend. No production ingestion/legacy feed/schedule, UI, authorization, private report or quote changes.

This is offline tooling work, **not a new canonical data import or live app deployment**. Staging remains 92/212/12 offerings/biographies/positions and zero quotes. Capture blockers are explicit: this execution shell lacks its configured authorized SEC contact, and PicPay's 21.85 MB filing exceeds the existing capture/object limit. Do not fabricate a contact or truncate a filing. Next: restore the existing capture configuration through the proper service, implement tested lossless bounded archival for large filings, then continue oldest-first source review/import across the complete candidate inventory. No need for the owner to name missing IPOs. Existing retained evidence can still be reviewed while live capture is unavailable.

Owner's filing-based valuation decision is now recorded in the backlog: paid quote feeds are deferred; historical price-based estimates and explicitly documented gross holder-sale proceeds must stay separate from current wealth, actual cash and saleability. Static per-account reports and explicit versioned refresh remain required. Paid quotes are not a standing owner action. Publication of this tooling checkpoint is subject to the unchanged ownership-history workflow guard; tests above are actual local Python checks, not live authenticated browser QA.

## 2026-09-27: recover exact Aktis voting-common review tooling

Recovered the missing deterministic `dated-voting-options` review path from the immutable applied Aktis manifest and its retained SEC source, without changing staging data. The strict parser accepts only the reviewed common-share-plus-option or option-only footnote shapes, requires the exact holdings date and source row name, and reconciles every component to the single reported beneficial-ownership total. Unsupported trust/fund/conversion/award clauses, source dates, instruments, malformed rows and arithmetic differences fail closed.

Ran the recovered builder against Aktis's retained final 424B4. It reproduced the already-applied release ID `ee9a8b51-add2-5859-bf5e-56987285d014` exactly: Matthew Roden's 1,280,943 total decomposes into 91,998 common shares plus 1,188,945 option-underlying interests; Paul L. Feldman's 328,650 total decomposes into 118,283 plus 210,367. Both remain historical October 31, 2025 beneficial totals with unknown attribution/current ownership/saleability, no lock-up expiry, quote, market value or cash proceeds. Akos Czibere's option-only row remains held because his identity/role was not included in the reviewed January commercial release; the parser does not create or infer that relationship.

All **60 Python tests** pass, including five new voting-option tests and the earlier AgomAb one-share mismatch regression. The Research Monitor workflow for the preceding reconciliation-guard commit `90468b07` passed. This is tooling recovery for reproducibility, not a new holding import or private-report refresh. Staging remains **92 offerings / 212 biographies / 12 positions / 14 components / zero quotes**, and the five account-private reports remain static.

## 2026-09-27: non-reconciling AgomAb holding held with regression guard

Reviewed Tim Knotnerus's ownership-table row and footnote in AgomAb's final 424B4 and preceding F-1/A. The table reports 668,855 shares as of December 31, 2025, while the four disclosed components (29,221 Series A conversion shares, 5,173 Series B conversion shares, 10,823 directly held common shares and 623,637 option-underlying shares) total 668,854. Both filings repeat the one-share difference. No quantity was rounded, repaired or imported; no liquidity classification, cash value, quote or private report was generated.

The strict component reconciler now emits the disclosed subtotal and reported total when it fails closed, and a regression test locks the 668,854 versus 668,855 case. All **55 Python tests** pass, including the focused five-test component suite. Publication is recorded below after the ownership-history workflow guard and branch checks complete. Staging remains **92 offerings / 212 biographies / 12 ownership positions / 14 components / zero quotes**, with five unchanged private reports.

The same source review found three director rows whose totals repeat entity/fund holdings while their footnotes deny voting/investment power or disclaim beneficial ownership. Those rows remain held rather than being presented as personal wealth. The contractual 180-day boundary is not evidence of current saleability. Next source priority remains independent SEC census classification plus reviewed holder/footnote coverage; this guard prevents an apparent one-share discrepancy from entering that accelerated path silently.

## 2026-09-27: independent AgomAb IPO applied and verified

Recovered the commercial worktree at checkpoint `4f88b543843d9589f0cb68e38d3e6ef1d0b63df2`, confirmed draft PR #581 remains open, and verified the Research Monitor test workflow for that checkpoint passed. The disconnected local review-tool changes were not present, so they were not represented as recovered or committed. Work proceeded from the remote checkpoint without reimporting any prior batch.

Independently identified and source-reviewed **AgomAb Therapeutics NV** from the exact 2026 Q1 SEC master-index row (CIK 2020932, registration 333-292790, final prospectus accession `0001104659-26-011523`). Applied one private quarantine intake and seven immutable evidence artifacts covering the January 16 F-1, January 29 F-1/A and February 6 424B4. The final prospectus supports ticker AGMB, a $15–$17 preliminary range, $16 final price, February 5 pricing date, 12.5 million ADS and $200 million base offering value. Offering size is not personal cash proceeds.

Applied the reviewed release atomically after rollback rehearsal, then replayed it exactly without duplication. Staging is now **92 offerings / 212 biographies / 12 ownership positions / 14 components / zero quotes**. Five complete executive biographies were added. The selected commercial biographies contain no Stanford reference; one unselected filing biography containing Stanford remains only inside private source evidence and is not returned by the application. No ownership position, lock-up expiry, saleability, wealth estimate or quote was inferred for an executive.

Role/RPC QA passed for ordinary-customer denial, reviewer list/detail access, exact pricing and dates, five-person accordion, named/Harvard/investment-bank evidence search, unsupported-search rejection, no inferred beneficial-owner relationship, empty ownership grids and save/unsave. The five existing account-private Liquidity Analysis reports remain unchanged with the same before/after fingerprint `f6b40d6398bb1feca59e42bde2ff4173`; no report was generated or refreshed. Live staging health returned HTTP 200 with `ok/staging`, and an unauthenticated offerings request returned HTTP 401. This is applied staging data served by the existing authenticated application, not a frontend/backend deployment. Live authenticated browser testing was not available.

Added a deterministic quarantine-only SEC-index intake builder and tests. Extended evidence capture with an explicit `--additional-accession` option that accepts only a verified filing in the same registration lineage; this preserves preliminary pricing evidence for independently discovered IPOs without broad capture or inference. **54 Python tests, 12 Node/API tests and the production TypeScript/Vite build pass.** The existing Vite dependency-directive and chunk-size warnings remain non-fatal.

Polaryx was reviewed as an explicit direct listing and was not imported. AgomAb raises reviewer People Search coverage to Michigan 4 and Harvard 25; Goldman Sachs remains 5 and the exact “investment banking” phrase remains 12. Supabase advisors show no new data-release error: the private ops tables and empty market-price table remain deny-by-default under RLS with no client policies. Existing launch work remains to enable leaked-password protection; one informational performance finding recommends a covering index for the composite saved-IPO foreign key. No schema change was made in this run.

The independent SEC census and beneficial-owner/footnote coverage are still incomplete, and MFB remains the original-feed eligibility hold. Next: commit the validated tooling/docs under the ownership-history guard, then continue oldest-first independent SEC classification and sourced holder/footnote review. No new paid AI/provider or owner spending is needed for that work; quote licensing still gates market-value estimates.

## 2026-09-26: accelerated backfill applied; workspace recovery needed for tooling commit

Verified at 23:45 UTC: **91 offerings, 207 biographies, 77 offerings with reviewed people, 12 ownership positions and 14 components**. Started this owner-authorized two-hour session at 22:07 UTC with 38 offerings, 95 biographies and 10 positions. All new research remains unpublished/internal_review, with ordinary customers denied. No production ingestion, legacy feed/Pages, schema, application UI/backend, billing or quote-provider change.

Applied 51 offerings from the original SEC Monitor inventory: April 11, May 8, June 13, July 6, August 10 and September 3. Reconciled Wella's September 23 amendment by CIK/registration root without duplicating the offering or deleting older biographies/documents. The original 90-record interval inventory now has 89 exact current snapshots and one eligibility hold: MFB's second-step conversion replaces previously OTC-quoted shares. The main feed was re-fetched and retains the September 25 generation timestamp.

Independently reviewed and imported Buda Juice and Green Circle from the SEC Q1 master index, adding two January IPOs missing from the Monitor. Their initial registrations predate 2026. Preliminary prices, final prices, prospectus/pricing dates and gross base offering values have distinct source evidence. New private sec-index-intake/1 batches preserve exact index rows, source URL/hash and an explicitly labeled capture-engine baseline commit; they do not pretend to be legacy-feed snapshots or automatically establish eligibility.

Added 112 biographies: first April release 12, then April supplement 21, May 22, June 25, July 12, August 15 and September/Lyntris 5. Complete multi-page passages and explicit issuer roles retained. Remaining person/holder coverage is incomplete; no affiliation or beneficial ownership inferred from executive biographies. Last pre-final-supplement search QA found Michigan 4, Harvard 22, investment banking 11 and Goldman Sachs 4; rerun counts before reporting newer coverage.

Added two Aktis historical voting-common beneficial totals with four common-share/option components. Source date and October 31, 2025 holdings date remain separate. Retained exact footnotes, voting/non-voting headers, conversion assumptions and full 180-day lock-up restrictions/exceptions. No Class A position, option exercise, personal economic interest, present saleability, expiry date, market value or cash proceeds inferred. Five existing private liquidity reports retain fingerprint 21e064dbab4b4fd773671e56bd03db11. Shared facts do not regenerate saved reports; explicit account-private refresh remains required.

Every applied company/biography/holdings batch passed rollback rehearsal, atomic application, exact replay and post-apply SQL QA. Checks cover canonical/API financial fields, biography/name/source/relationship identity, save/unsave, unsupported matches, ordinary-customer and anonymous denial, unchanged existing private reports and no fabricated quotes. Full-cohort pagination returned 91 unique offerings across four pages; all five size thresholds matched database truth; every company detail passed content/unknown-quote checks. Existing private-liquidity and ownership-grid SQL suites passed cross-account existence/guessed-ID denial, immutable reopen, explicit refresh, unauthorized mutation denial and shared-grid independence. Zero disposable test accounts remain.

62 Python tests and 12 Node/API tests passed. Production TypeScript/Vite build passed with existing dependency directive warnings. A subsequent small tightening of the voting-row percentage regex was prepared but not retested before disconnection. Live health returned 200/ok/staging; unauthenticated offerings returned 401. Inspected the live desktop login and verified Pause/Play. No authorized signed-in browser session was available: live authenticated and mobile journeys remain unverified. Database role tests are not a live-login test.

Important evidence cases: Hometown's primary bank IPO prospectus follows a separate 401(k) supplement; its proposed $600m midpoint is not a final offering value. Lyntris's pricing cover is an embedded JPEG: original image, separately hashed visually reviewed transcript, review timestamp and explicit image-transcript provenance are retained. No OCR/model guess, paid AI or new external provider used.

Independent SEC census is NOT complete. Q1/Q2/Q3 indexes contain 3,039 relevant-form rows across 1,144 CIKs. Initial comparison against 89 staged CIKs found 363 unmatched 424B4 rows across 324 issuers; these are unclassified candidates, not missing IPO counts. Reviewed first-sample exclusions include STAK (2025 IPO), Jefferson Capital (selling-stockholder follow-on), Atlas (pre-existing OTC market), Rubico (2025 spin-off/listing), Aptera (already-listed share/warrant offering), and Republic Power (2025 IPO). Virtuix's explicit resale direct listing and Public Policy Holding's existing AIM listing need policy reconciliation before inclusion; neither was force-imported. Agomab and Polaryx capture was started last; completion is unverified after the workspace disconnected.

Durable evidence checkpoint: ops.sec_artifacts contains manifest SHA-256 b91f8d3abff11629bba80676135770bbd4d63a4ab754e112fbb1cc1aaf1299b6. Its gzip JSON records full SEC index metadata, ordered <=10MB chunks and original hashes, candidate inventory and ten discovery packets. Original full indexes were chunked because they exceed the existing 20MB artifact limit; no limit/schema change. Reassemble and hash-check before reuse. All applied release evidence and manifests are also in staging. Raw documents for unimported candidates are not necessarily archived yet.

At approximately 23:43 UTC the execution workspace disconnected (environment_offline); database and GitHub connectors remained available. Applied data is verified and durable. Offline tooling changes are **prepared/tested locally, not committed or deployed**. Recover the worktree at /workspace/scratch/699a17a605a3/IPO-Tracking before editing: scripts/build_review_batch.py, scripts/build_holdings_review.py, new scripts/build_biography_supplement.py, scripts/build_sec_index_intake.py, scripts/review_voting_options.py and their test files. Existing local docs edits should be reconciled with this remote checkpoint. Private import-output/year-2026 has exact selections and import/verify SQL. Do not discard the worktree, reimport blindly or reconstruct a supposedly tested version without checking it.

Next: recover/commit the prepared tooling under the ownership-history guard; continue independent oldest-month SEC classification and missing holder/footnote evidence; verify remaining person gaps. Existing source-rights, licensed quotes, real-login QA and commercial auth/payment/launch gates remain. No new owner spending or AI-provider decision is needed for SEC backfill.

## 2026-09-26: March release verified; April source capture complete

Started from clean commercial HEAD `242fb91c1e4e33437136bd9f4c1b615518df60fa`; draft PR #581 remained open and Test Research Monitor passed. Held the shared development lock. Applied MiniMed and HMH plus six complete person-specific biographies. Staging is now **38 offerings / 95 biographies / 10 ownership positions**. Original feed candidates reviewed/imported: January 5/5, February 9/9, March 2/2; **not an independently verified SEC census**. Remaining inventory: 52 new reviews and one issuer reconciliation.

MiniMed titles preserve the source's “Will serve as…” appointment timing, including in People Search. HMH director relationships are explicitly current as of the source; its March 31 pricing and April 1 filing dates stay distinct. MiniMed's $20 final price does not replace its $25–$28 preliminary range. Retained complete cross-page HMH biography evidence without converting an executive program into an MBA. Exact amounts/accessions are in `backfill-2026.md`.

Archived 14 immutable private artifacts, rehearsed with rollback, applied atomically, replayed exactly and passed post-apply role/RPC QA for pricing, dates, role wording, biography search, saved/unsaved IPOs, unsupported/inferred-owner search rejection, reviewer access and customer/anonymous denial. Search coverage is four Michigan matches and 15 Harvard matches. Five private Liquidity Analysis reports kept the identical aggregate fingerprint; no new reports, versions, holdings or quotes; zero temporary QA accounts remain. This is applied staging data through the existing reviewer API, with no new application code or deployment required. Rights remain internal_review/unpublished.

Public health requests timed out twice; the unauthenticated offerings request also timed out. Live HTTP availability/denial and authenticated browser journeys remain unverified for this run. These connection failures do not invalidate database QA or establish an application defect. No UI, schema, access, production pipeline/feed/Pages, schedule, billing or provider changes.

Prepared the next month: captured all 11 April candidates, 33 SEC documents and 44 automatically located unreviewed biography candidates; original/normalized hashes verified. Two bounded capture workers reused the existing SEC pacing. April remains unreviewed/unimported. Private `april-capture-results.json` and readable block dumps are ready; start with Arxis and Madison Air (April 15), then remaining April candidates. Do not recapture or treat candidate counts as verified-person counts.

Also prepared Aktis footnote decomposition for three executives: common shares versus option-underlying quantities reconcile to disclosed totals, but the as-if-conversion/table-basis and lock-up evidence require separate validated ingestion. See private `january-release/aktis-holdings-triage.md`; no unsupported holdings or personal cash claims inserted. Keep private reports static. Continue source-backed holdings and independent SEC coverage checks alongside the oldest-month queue. No new owner action, paid AI or spending needed; existing quote licensing/live-login/launch gates remain. Applied March reproducibility files are under ignored `march-reviews.json` and `march-release/`.

## 2026-09-26: remaining February feed candidates applied and verified

Applied five source-reviewed offerings and 17 biographies: Once Upon a Farm, SpyGlass Pharma, SOLV Energy, ARKO Petroleum and Generate Biomedicines. Current staging totals are **36 offerings / 89 biographies / 10 ownership positions**. January 5/5 and February 9/9 original feed candidates are now reviewed/imported; this is not independent SEC completeness. Remaining inventory: 54 new source reviews and one issuer reconciliation. Prices, ranges, dates, values and accession identifiers are recorded in `backfill-2026.md`.

Preserved 35 immutable private artifacts for 15 SEC documents. Full rollback rehearsal, atomic apply, exact replay and post-apply rollback QA passed. Checked literal pricing, complete biography search, no inferred beneficial-owner match, unsupported searches, saved/unsaved IPOs, ordinary-customer denial, reviewer access and anonymous RPC denial. Search coverage is now four University of Michigan matches and 14 Harvard matches. Five private Liquidity Analysis reports retain their identical aggregate fingerprint; zero temporary QA accounts remain. No holdings, quotes, lock-up dates or private report versions were added by this release. Static account-private reports remain unchanged.

Live staging health returned HTTP 200/ok/staging after an initial timeout; unauthenticated offerings returned 401. Live authenticated browser QA remains unverified. This is applied staging data available to existing reviewers through the current API; no new frontend/backend deployment was needed. Source rights remain internal_review/unpublished, with ordinary customers denied. No production ingestion, Pages, UI, schema, entitlement, billing or schedule changes. Commercial HEAD at start was `6fb25cb676c98bb1c1db3ba242aad8712461dc08`; PR #581 remains draft.

ARKO's projected parent holdings require careful conversion/overlap treatment: the Class A amount is issuable upon conversion of Class B, not an additional personal position. Individual executive dashes cannot establish current zero holdings because the table is projected and excludes offering purchases. Triage is retained in private `february-b-release/holdings-review-notes.md`; no unsupported quantities or cash claims were imported.

Next: manually review the two March candidates, MiniMed and HMH. Six SEC documents are captured and hash-verified; neither candidate is imported yet. Preserve expected appointment timing in their biographies. Reuse private `march-capture-results.json` / `march-review-handoff.md` and the archive rather than recapturing. Continue older-month ownership/footnote review and independent SEC coverage reconciliation. All private source payloads and generated SQL remain ignored, outside Git/frontend assets. No new owner action, paid AI provider or spending is needed for this SEC work; existing quote licensing, live login QA and launch gates remain.

## 2026-09-26: first February release applied and verified

Reviewed retained SEC Monitor/SEC evidence and applied four February offerings plus 13 executive biographies: Veradermics, Eikon Therapeutics, Forgent Power Solutions and Bob’s Discount Furniture. Staging now has **31 offerings / 72 biographies / 10 ownership positions**. Final prices, pricing dates, base offering values and preceding preliminary ranges are separately sourced. Veradermics uses its literal prospectus name, Veradermics, Incorporated. Eikon biography spans include separate full-name headings; Bob’s CFO biography includes the continuation across a page break. No ownership or quote was inferred from executive biographies. Forgent’s total offering includes both primary and selling-stockholder shares; it is not individual cash proceeds.

Applied 28 immutable private evidence artifacts for 12 filing documents, then rehearsed the complete release in a rollback transaction, applied it atomically, replayed it exactly, and reran rollback QA. Tests passed for counts, company/price/date/range/value, complete biography search, unsupported search rejection, no inferred beneficial-owner match, saved/unsaved IPOs, reviewer access, ordinary-customer denial and anonymous RPC denial. Five private liquidity reports retained their identical before/after content fingerprint. Existing source rights stay internal_review/unpublished; no entitlement changes or public enriched dataset. Data is applied to staging and readable through existing reviewer RPCs; no application deployment is required for this data-only release.

Live check: `/api/health` returned HTTP 200, status ok, mode staging after an initial timeout. A separate unauthenticated `/api/offerings` request timed out at connection level, so live HTTP denial and authenticated browser journeys remain unverified. No live login was simulated or claimed. PR #581 remains draft; Test Research Monitor was green on the inspected branch HEAD. No production pipeline, Pages, UI, migration, dependency, billing or schedule changes in this run.

Holdings review found a Veradermics source conflict: its table introduction says September 30, 2025, but the percentage/conversion basis and option footnotes use December 31, 2025. Positions remain held. Reid Waldman’s disclosed beneficial total mixes direct common shares with option-underlying interests; Dominic Carrano’s is option-underlying. Tim/Timothy Durso requires explicit identity reconciliation. Keep those distinctions and conditional lock-up terms; do not assign dates, cash value or saleability from the ambiguous table. This is internal review work, not an owner setup blocker.

Next: review/apply the remaining five February candidates (Once Upon a Farm, SOLV Energy, ARKO Petroleum, Generate Biomedicines and SpyGlass Pharma), then March; reconcile the Veradermics holdings-date conflict before adding its positions. All retained February captures have readable block files. Private applied manifest, SQL, QA and holdings notes are in ignored `import-output/year-2026/february-a-release/`; reviewed selections are `february-a-reviews.json`. No new owner action or spending needed for SEC backfill. No paid AI provider added; quote licensing still gates market-value estimates.

## 2026-09-26: accelerate historical backfill and capture February

Owner requested acceleration. Updated the existing development task to hourly including overnight, with the same exclusive-work lock, SEC access limits, evidence/access/commit guards and separate 6 PM Pacific digest. Prompt prioritizes source-reviewed imports and holder/footnote evidence ahead of cosmetic work and restores the previous 8 AM/noon/4 PM cadence after historical completion is independently verified.

Started the next batch immediately: captured all nine February SEC Monitor candidates, including 27 SEC documents and 42 automatically located biography candidates. Verified every retained source and normalized-text SHA-256 and packet publication hold. Captures cover Eikon Therapeutics, Forgent Power Solutions, Once Upon a Farm, SOLV Energy, ARKO Petroleum, Generate Biomedicines, Veradermics, Bob's Discount Furniture and SpyGlass Pharma. These are captured/unreviewed records, not new imported offerings or confirmed people. Zero February research rows were applied in this step; staging remains at the previously verified 27 offerings/59 biographies/10 positions.

Private packets/objects are under ignored `import-output/year-2026/archive/`; per-record results are in `february-capture-results.json`. Next run should reuse these artifacts for operating-company, current/root registration, preliminary/final pricing, complete biography and holder/footnote review. Missing automatic biography matches require manual passage review, never inferred identities. No schema, access, UI, production feed or private-report changes. No service purchases or new provider dependencies.

## 2026-09-26: apply first 2026 SEC Monitor backfill release

Owner requested backfill using existing SEC Monitor data, within the approved January 1 onward scope. Reused the existing private intake, SEC capture and reviewed-release builders. Applied the 93-record intake at source commit `f4bdf65261fc583a406da3fd0b653b111143a2f6` to quarantine (90 interval candidates), then released five January operating-company offerings and 15 source-backed executive biographies: Aktis Oncology, BitGo, EquipmentShare, Ethos Technologies and York Space Systems. Reconciled the queued Yellowstone Midco name to York from its final prospectus. Retained 35 immutable evidence artifacts covering 15 SEC filing documents.

Staging verified at 2026-09-26 06:20 UTC: **27 offerings / 59 biographies / 10 ownership positions**. Michigan search has three matches; Harvard has ten. Each new issuer retains its pre-year registration, January pricing date, sourced preliminary price range, authoritative final price and base offering value. No inferred holdings, cash proceeds, live quotes or beneficial-owner relationships were added. Data remains unpublished/internal_review and unavailable to ordinary customers. Existing reviewer APIs can read the applied data without an application deployment. This is five reviewed January feed candidates, not a complete annual or monthly census.

QA actually performed: full rollback rehearsal, atomic apply, exact replay, and post-apply database role/RPC checks for totals, duplicate prevention, pricing/lineage, search evidence, unsupported searches, no inferred owner matches, detail/current-price safeguards, customer isolation and anonymous denial. Five existing private Liquidity Analysis reports have the same before/after aggregate content fingerprint; no reports were generated or refreshed. Live authenticated browser QA was not performed. No application code, schema, production engine, Pages, schedules or access policy changes.

Checkpoint: detailed evidence identifiers, reviewed values and remaining queue are in `backfill-2026.md`. Private source payloads/generated SQL remain outside Git. Remaining inventory: 63 candidates needing new review and one issuer reconciliation; February has nine candidates. Next work is the remaining SEC Monitor queue and independently reviewed ownership/footnote evidence. No new owner setup, AI provider or spending is required for this batch; quote rights remain a launch/valuation prerequisite.

## 2026-09-26: icon-only motion control

Removed the visible illustrated-data-flow caption at the owner's request. Replaced the labeled motion control with one 44px circular Pause/Play icon button. Screen-reader action labels, keyboard focus and reduced-motion behavior remain. The decorative wrapper no longer uses figure/caption semantics. No animation geometry, form, authentication or data changes.

Production build and existing targeted login journey passed (13.6 seconds), covering click/focus, pause/resume/reduced-motion pixels, responsive coverage/overflow and no pre-login research calls/errors. Inspected the phone screenshot for caption removal and icon-only placement. No new tests, dependencies or database changes.

Staging verified 2026-09-26 05:04 UTC at commercial commit `99e5103e241298986a2ca0393557e3cc4af346c6`. Served JS `index-CHP2uPZn.js`, SHA-256 `455b7f388177e7f39dbcaf9f07f2031bcb97ef9c5c0493db6b4644c08b7d44bb`, and CSS `index-CiICTKzd.css`, SHA-256 `8a9da61fdd4d14ec1182cdac94ece9b1bc0bedd7581591b86e12f1f86170d5ee`, match the tested build. Health `ok` / `staging`; Test Research Monitor run `36219623529` passed. Ownership-history guard lists were clear immediately before committing.

## 2026-09-26: sharpen approved full-page particle composition

Owner approved the full-page direction and requested less blurry particles. Replaced diffuse sprite bloom with a defined bright center and short faint halo, reduced pulse expansion, and tightened the moving light capsules. Composition, flow geometry, typography, colors, form and motion controls are retained. No new dependency, data or auth changes.

Production build and existing targeted login browser journey passed (13.9 seconds), including full-container coverage, form click/focus, animation/pause/resume/reduced-motion pixels, overflow and no pre-login research calls/errors. Inspected desktop and phone screenshots for sharper distinct points. Live authenticated login was not tested.

Staging verified 2026-09-26 04:57 UTC at commercial commit `fcf22d94b331efc7c3f4fe783f7d06ab0ec4bf4a`. Served `index-CoNe2_z6.js` SHA-256 `8ff5674ef4989e9c6f23f8dbf7d1daba00489392aeaba555348b834e5b28cd61` matches the tested build. Health `ok` / `staging`; Test Research Monitor run `36219306024` passed. Ownership-history guard lists were clear immediately before committing.

## 2026-09-26: integrate particle flow across the login page

Owner requested that the animation occupy the full composition instead of appearing as a separate lower-page add-on. Moved LoginFlow out of the brand content into an absolute background layer spanning the login container. Conduits sweep from the viewport edges behind the actual sign-in panel; removed the separate processor/duplicate wordmark and figure header/divider. Enlarged and balanced the headline, preserved a dark quiet area behind text, and placed the caption/motion control along the page footer. Mobile keeps the background behind stacked content.

Canvas now measures both container dimensions, reflows curve coordinates to its aspect ratio, and uses uniform rendering scale so particles remain round. Render resolution caps at 2400px width and DPR two. Pause, reduced-motion, hidden-tab and offscreen behavior remain. No auth or application data flow changed.

Production build and targeted login browser journey passed (13.4 seconds). Added explicit desktop/laptop/mobile assertions that the canvas fills the login container and that an actual email-field click receives focus through the background layer. Existing pixel animation/pause/resume/reduced-motion, no pre-login research calls/errors and overflow checks pass. Inspected desktop, laptop, wide-screen and phone screenshots. Tests use simulated config, not live authenticated login; physical-device performance remains unmeasured. No database, legacy engine, source data, dependency or schedule changes.

Staging verified 2026-09-26 04:52 UTC at commercial commit `60449239128cba169d723dd4b3b4f9477b6507ec`. Served JS `index-3I_FVUy6.js`, SHA-256 `c9fa2ca887b8e1ac73583ea0f320410e74174a69fe135beacdb7ece71f22e934`, and CSS `index-ChHDnVwp.css`, SHA-256 `72d20d9fd0a386708845b33a13ef9f9202ba8dcbbd5b0567e27444c8b66aabd3`, match the tested build. Health `ok` / `staging`; Test Research Monitor run `36219024773` passed. All ownership-history guard lists were clear immediately before publication.

## 2026-09-26: restore directional conduits and processing core

Owner rejected the vortex metaphor and preferred the tendrils' meaning but wanted better execution. Restored three separated curved input conduits and three ordered output lanes around an original extruded glass-like processing core. Input swarms use irregular spacing and slight drift; outputs use aligned packets. Added lit tube surfaces, depth-weighted particles, traveling highlights and illuminated connection points. Paths are distance-resampled and all data travels left-to-right. Typography/form structure and the illustration label remain intact; the core wordmark was repositioned to its new geometry. No orbit/vortex, live dataset, external dependency or runtime graphics request.

Production build and targeted login browser test passed (9.8-second journey): moving/paused/resumed pixels, reduced-motion static state, no pre-login research calls or browser errors, desktop/laptop/wide-screen height and phone width. Inspected desktop and 390px phone screenshots, including the core's wordmark fit. Authentication is simulated config for visual QA; live sign-in and physical-device performance were not tested. Aesthetic acceptance remains with the owner. No database, source facts, private reports, production engine or schedules changed.

Staging verified 2026-09-26 04:43 UTC at commercial commit `fc97e51a058d3c62abf8df3a9e5ef67a0a8a43e3`. Served JS `index-t8v_ogZv.js`, SHA-256 `04bef404e0643afda162fed950df970de4e8930e4d37e2a92ef412ac9faecfd4`, and CSS `index-C0jSjaZa.css`, SHA-256 `b9082b244213e5399e45f1ccef2d97b08af3494c10b707ea242f317b5fcd885f`, match the tested build. Health `ok` / `staging`; Test Research Monitor run `36218598906` passed. Ownership-history guard lists were clear immediately before committing.

## 2026-09-26: luminous particle-lens direction

Owner rejected the sphere/tendrils as lacking visual impact. Replaced that composition with an original tilted particle lens, two broad spiral currents, a dense rotating light lattice, traveling highlights, a restrained rim flare and atmospheric depth. Increased focal scale and light density after inspecting the first render. Retained precise HTML text/form layout, local Canvas rendering, pause/reduced-motion/visibility controls and the illustrated-data-flow label. No external assets, video, dependencies, runtime data calls or auth changes.

Production build and targeted browser journey passed (9.3 seconds), including animation/pause/resume/reduced-motion pixels, desktop/laptop/wide-screen height checks, phone width, absence of browser errors and no research calls before sign-in. Inspected final desktop and 390px phone screenshots. These are simulated-config visual tests, not live authenticated login or a measured device-performance benchmark. Legacy engine, database, customer data and private reports remain untouched.

Staging verified 2026-09-26 04:22 UTC at commercial commit `cbcb5bcd7f7b040b10f5289d166bd66cd4619199`. Served assets match the tested build: `index-CqZVxztI.js`, SHA-256 `a0c1976af010066d190badfd067663182dd38d4fa7f573719686d0c44e46ca3b`; `index-BgRkCh2L.css`, SHA-256 `e13bfba8be74b33c6b9be45e38cc87495e9ad9a4c738d9445309612a438bdb72`. Health `ok` / `staging`; Test Research Monitor run `36217558079` passed. All ownership-history guard status lists were clear before committing. Owner aesthetic acceptance is pending.

## 2026-09-26: cleaner particle-stream geometry

Owner flagged the tendrils. Replaced the crossing paths with six separated, gently curved streams, keeping their depth coherent. Tube cross-sections now follow the local path direction instead of a fixed world plane, and narrow smoothly where they join the sphere. Distance-resampled paths and interpolated particle locations remove uneven speed and sample stepping. Reduced the braid twist; preserved the sphere, typography, authentication and existing motion controls.

Production build and targeted login browser test passed (8.4-second journey): changing/paused/resumed canvas pixels, reduced motion, no pre-login research requests/errors, desktop/laptop/wide-screen height and mobile width checks. Inspected desktop and mobile screenshots. Live authenticated login was not exercised. No source data, database, dependency, legacy pipeline or access changes.

Staging verified 2026-09-26 04:05 UTC at commercial commit `e4713a5a11bd38383c420474402b67d8294e8919`. Served `index-CrXnUxIT.js` SHA-256 `330472cf9f44669c073dc26dd6698d49c1291b234edc8ac76ac47f8cea35d3d4` matches the tested build. Health returns `ok` / `staging`; Test Research Monitor run `36216713528` passed. All ownership-history guard status lists were clear immediately before publication.

## 2026-09-25: cinematic character-stream scene

Owner supplied Riley Ralmuto's public video reference and explicitly requested its style/aesthetics and stronger visual impact, not a copy. Inspected sampled frames of the 33-second clip for depth, character streams, lighting and camera movement. No reference footage/assets were incorporated. Added original `particleScene.ts`: perspective projection, slow camera orbit, an independently rotating spherical character lattice, six braided streams with traveling light pulses, atmospheric dust, orbital arcs and cached glyph glow. The sign-in typography/layout stays crisp and unchanged from the reviewed responsive pass.

Preserved pause/reduced motion/hidden-tab/offscreen controls and fixed rendering budget (about 4,600 glyph draws/frame, throttled by the existing frame loop). No WebGL/library dependency, external runtime request, public research payload or AI provider was added. The illustration does not claim to show live data. Production TypeScript/build and the targeted browser journey passed, including moving/static/resumed pixel comparisons, no research requests before sign-in, no browser errors, desktop/laptop/wide-screen height checks and phone width. Inspected desktop, laptop and phone screenshots. No source data, authentication or private-report behavior changed.

Staging verified 2026-09-26 03:57 UTC at commit `7f1624a8470a5915a61ae32a4bcd7e526041e6d1`. Served assets match the tested build: `index-RaQusW-Y.js`, SHA-256 `3acdfd50c1b4039af5fe44f62a3e67c6b4c225b022ecd61de94da4c00d99db26`; `index-BJvDufcI.css`, SHA-256 `a1bb3245e6e6786ba2bdf780caad69d7a39f4c5f8a8908a8b776d41e3f906d39`. Health `ok` / `staging`; Test Research Monitor run `36216324912` passed. Ownership-history guard statuses were clear before the commit. Live owner login was not tested.

## 2026-09-25: particle-tube login revision and typesetting

Owner rejected the diagram's spacing and requested particle swarms flowing through illuminated tubes, with careful typography. Replaced the boxed SVG diagram with a locally rendered Canvas 2D particle field: eight curved conduits, clustered teal/blue particles, cached light sprites, a central branded collector and an orbiting swarm. Removed competing small diagram labels; capped desktop content width, tightened headline/brand spacing, and added a short-laptop-height layout. The form and existing authentication behavior are unchanged.

The renderer uses a fixed particle budget, caps device-pixel ratio at two, updates near 30 fps, and stops its frame loop when paused, reduced motion is enabled, the tab is hidden or the canvas is offscreen. No video, external animation service, dependency or research payload is used. The caption identifies an illustrated flow.

Production build passed. Targeted Playwright test checks actual canvas pixel changes while running, stable pixels while paused/reduced-motion, successful resume, no unauthenticated research requests, no browser errors, mobile width and no vertical overflow at 1366×768 / 2048×1184. An initial test caught 79px laptop overflow; tighter spacing and a shorter graphic corrected it before the passing rerun. Inspected screenshots at 1440×1100, 1366×768, 2048×1184 and 390px phone width. No data, source rights, private reports or row-navigation logic changed.

Staging verified 2026-09-26 03:36 UTC at commercial commit `de7ac7cb32b54e7fe75649cd06397a6be3cd893d`. Render serves `index-BpGUk0fh.js` (SHA-256 `360cfe3b1663ff4f0ac9e591f40a997ad78dbdee8675f87da27200ef962e19be`) and `index-BWiGWeVq.css` (SHA-256 `8ec576ecb0fe800b5b759a4b476964443e129f24868337928107175e37c40629`), matching the tested assets. Health returns `ok` / `staging`; Test Research Monitor run `36215250624` passed. All guarded workflow queues were clear before committing. Live owner sign-in was not tested.

## 2026-09-25: full-row navigation and animated login

Owner requested clicking the highlighted IPO row to open details and a code-rendered high-tech login visualization. Overview, IPO Activity and Saved/Watchlist rows now open details from non-control cells. Company buttons remain keyboard-accessible and receive focus for dialog return; bookmark buttons and selected/copied text do not trigger row navigation. Highlighting extends to keyboard focus. Column ordering behavior is preserved.

Added `LoginFlow.tsx` / `LoginFlow.css`: locally rendered SVG/CSS filing packets connect registration/prospectus/footnotes through IPO Roll to research areas. No video, remote graphics library, new dependency, actual company data or research API call is used on the unauthenticated login page. The illustration is explicitly labeled, includes Pause/Play, and honors system reduced-motion preferences. The existing sign-in handler is unchanged.

Production TypeScript/build passed. Both targeted Playwright journeys passed: non-company cell opens across all three views, bookmark independence, Enter/Escape/focus return, reordered column clicking; login desktop/390px mobile no overflow, pause/resume, reduced-motion static state, no pre-login research requests and no browser errors. Desktop and full-page phone screenshots were visually inspected. Login UI uses mocked config for this test; live authenticated owner sign-in remains unverified.

Deployed and verified at 2026-09-26 03:23 UTC: commercial commit `72883a646dfc59746b27f54af03668bcb02d166c`; Render serves `index-j9amFGVQ.js` (SHA-256 `da2d50e71cbf82214f674508d5e8187f9440b366df2e066af663936b60e279d3`) and `index-3gspJT6U.css` (SHA-256 `cca2d355a31388af579ddc7c92a6a79bdc37b84505f504791082444f01932b40`), both matching the tested build. Health is `ok` / `staging`. Test Research Monitor run `36214591493` passed. The January audit/capture checkpoint was committed separately in `f91b6d91cf22dc0a8ad53e1e6473b2349563343d`. All five guarded workflow-status queries were clear before each commit. No main merge, production schedule or source-data publication changed.

## 2026-09-25: January 1 backfill authorized and started

Owner expanded commercial staging coverage to January 1, 2026–present, superseding the prior commercial historical hold, including April/May and smaller qualifying operating-company IPOs. See `backfill-2026.md` for the durable monthly inventory and next review batch. Production/legacy scope and the ownership-history commit guard are unchanged.

Read current main feed at `f4bdf65261fc583a406da3fd0b653b111143a2f6` and compared an exact private intake to staging: 90 interval candidates, 21 matching staged filing snapshots, one existing issuer requiring accession reconciliation, 68 requiring new source review. Staging still has 22 offerings; no reviewed historical offering has been added by this step. Generated private intake/queue and completed January capture: five candidates, 15 filing documents, 34 unreviewed biography candidates. Added checksum-validated `build_backfill_queue.py`; both targeted tests passed. Existing development and nightly-review task prompts now include this expanded scope and monthly coverage reporting. No new task, schema, access grant, cost or private liquidity report was created.

## 2026-09-25 evening: beneficial ownership quick-reference grid

Owner requested an easy-to-read individual-research grid showing stock classes/series, quantities, lock-up periods and a Liquidity Analysis action, with the goal of understanding IPO-related wealth. Implemented `OwnershipGrid` inside the existing single-open person accordion, ahead of the expandable biography. Widened the company drawer for desktop comparison; phones horizontally scroll the labeled grid. Footnotes expand across the full table width. Rows separate reconciled common-share/option/RSU/trust components without adding the parent total again. Unsupported series, dates and quantities remain unconfirmed. Two separate summary areas distinguish estimated holdings value from documented personal IPO sale proceeds; neither currently has verified dollar data.

Applied additive migration `20260926025136_ownership_reference_grid`: a stable invoker-security helper returns authorized shared filing facts in the existing authenticated company-detail response. It reads no private report table, creates no analysis, exposes no report status/history/IDs, and preserves all access gates. Liquidity Analysis remains a user-requested private static snapshot with explicit refresh. The existing public source/evidence and RLS helpers are reused; no service-role key, provider cost, quote computation or AI dependency was introduced. No production/legacy changes.

QA: 12 Node/API tests including aggregate/component no-double-counting and incomplete-breakdown cases; production TypeScript/build; staging rollback grid and existing private-liquidity suites. The new database test checks equal shared detail before/after an account requests a private report, cross-account equality with private reports hidden, class/timeline values, mismatched company/person denial and ordinary-customer/anonymous denial. Security advisor remains at the known leaked-password warning and twelve intentional default-deny notices. Real private-report count increased from one to two during this work; contents and the cause of that activity were not inspected. Zero disposable test accounts remained. The explicit rollback test verifies that reading the grid creates no report.

Publication verified at 2026-09-26 03:00 UTC: migration applied and commercial commit `b8611b5128ad75dd6af667c5295787192cd0fab8` deployed. Render serves `index-DALFL-iP.js`, SHA-256 `78b3acfacf61e09be56918f2ae837663426692788784c84a0b2d3fdb4e502697`, matching the tested local build. Health returns `ok` / `staging`; anonymous company-detail and liquidity requests return 401. GitHub Test Research Monitor run `36213400903` passed. PR #581 remains open/draft; all five active/queued/waiting/pending/requested workflow lists were empty immediately before the feature commit.

Orion and Oura desktop/mobile browser journeys passed using actual captured company-detail and report responses with simulated authentication, including footnotes, no report generation before clicking, reopen, refresh and keyboard focus. Initial mobile assertion needed vertical scrolling before testing the horizontal footnote column, and the mixed-position fixture needed selecting its named holder rather than assuming the first person. These test-harness corrections preserve the actual source output order. Screenshots were inspected for readability and table/phone overflow; a live owner-login journey remains unverified.

Next data work: source-supported personal secondary-sale proceeds (shares actually sold, sale price, gross/net distinction and seller identity), kept separate from retained holdings and issuer fundraising. Never derive personal proceeds by subtracting pre/post beneficial totals. Continue Nancy Stagliano's reviewed trust/options and remaining recent-month coverage. Resolve the nightly Michigan count discrepancy using the actual normalized search predicate; the digest's literal-substring audit was not an authenticated API result. Quote licensing still gates holdings-value estimates. No new owner setup is needed for this grid.

## 2026-09-25 late afternoon: option-only Electra backfill

Started from clean commercial HEAD `a974476cbfe9df3c7b9757c6182280573169881c`; PR #581 remained open/draft and the ledger had no intervening afternoon work. Acquired the exclusive development lock. Fresh staging counts matched the midday checkpoint (eight positions/eight components, two conditional timelines and one private report). No legacy engine, schedules, main, access gates or frontend design changed.

Reviewed captured Electra final 424B4 `0001193125-26-395670`, raw SHA-256 `a20f78bb4ecb1af6b2df957314603ec26137b264c529e08d6a86076246eb7539`. Applied two internal-only **pre-offering option-underlying disclosures as of August 1**: Quehuong (Kathy) Dong, 1,399,175, and Gary S. Koe, 380,837. The filing is dated September 18. Full footnotes reconcile their separate LLC distributions to the post column; those distributions are not added to these pre totals. Dong's post-distribution repurchase condition remains visible in the complete footnote, not misapplied to her pre-option total. Seven exact spans retain headers, all table assumptions, individual rows/footnotes and full underwriting restrictions/exceptions. Neither option exercise, vesting, exercise cost, current ownership, personal cash value nor liquidity is inferred.

Added the narrow `dated-pre-options` profile and strict `review_options.py` grammar. Initial rollback QA caught the existing reconciliation helper's two-component minimum: an option-only position must be able to reconcile to one option component. Reviewed/applied migration `20260926002217_reconciled_single_option_component` makes only that extension; exact totals, same-document source visibility, invoker security and RLS remain enforced. Ordinary-share singletons still fail closed. No grant, saved-report rewrite, new dependency, AI provider or quote service was added. The import rehearsal then passed; actual application plus exact replay left **10 positions, 10 components, 10 unknown assessments, two timelines, 22 offerings and 44 biographies**. Quotes remain zero. The one pre-existing report's ID/content fingerprint stayed unchanged; its private contents were not inspected. Temporary QA accounts/reports were rolled back.

QA completed: all 48 Python tests (five new option tests), 10 Node/API tests, production build, and staging rollback options/components/liquidity/lock-up suites. Tests cover pre/post reconciliation, identity/date/instrument mismatch rejection, no double counting, unknown attribution/saleability, anonymous/ordinary-customer denial, cross-account existence/guessed-ID denial, immutable reports, explicit refresh and incomplete evidence. Previous Orion and Oura manifests reproduce identically. The Oura regression test now explicitly scopes its own cohort rather than assuming no other component-backed positions exist. Browser QA with actual captured reviewer RPC output and **simulated authentication** passed the University of New Mexico → Dong → option evidence → reopen → explicit refresh journey, Escape/focus behavior and 390px mobile overflow checks. Desktop/mobile screenshots were inspected; no live owner-login test was performed. Security advisor is unchanged: twelve intentional default-deny notices and [leaked-password protection disabled](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection), an existing commercial-launch gate.

Publication: tooling, migration, tests and documentation are committed on the commercial branch as `239235cbf0d46903be7a475bb2f1ddb8becec972`. All five active/queued/waiting/pending/requested workflow lists were empty immediately before commit. GitHub **Test Research Monitor** run `36204907204` passed. The migration and two reviewed disclosures are applied and verified in staging. The already-deployed component UI renders the new RPC structure in browser QA; Render's unchanged `index-DQeg5AJ3.js` matches the local SHA-256 `24237b24708e263edbf1f62a7addf2e8e42116701bad82bc8444361a9f83ae68`. This identical frontend hash does **not** identify Render's exact backend commit; no new backend/frontend application code was required in this increment. Staging health was `ok/staging`; the actual Electra liquidity endpoint returned 401 without authentication. A final offline parser hardening rejects malformed post-column comma grouping, passes all five targeted option tests and reproduces the applied Electra manifest unchanged. No production launch, merge or customer-rights expansion occurred.

Next: review Nancy Stagliano's explicit option/trust components in Electra block 3183 against row 3160–3161 before extending the parser; keep Carl Gordon's cross-referenced fund/control position held rather than treating it as personal wealth. The same file's full underwriting restriction at blocks 3442–3472 specifies close-of-trading expiry, so do not reuse Orion's date-only profile as proof of a tradable date. Eight of twelve companies with verified people still lack reviewed holdings; continue the recent-month cohort before historical expansion. No new owner action blocks staging testing. Existing quote licensing, commercial data rights, production Auth/password protection, payments and launch decisions remain future gates; no AI-provider approval is needed for this deterministic path.

## 2026-09-25 midday: sourced conditional restriction dates

Started from clean commercial HEAD `ee6c7fc0c129c51c9e3d1e47212ce489858ccf5e`. PR #581 remained draft/open; Render served the morning component release; staging had eight positions/eight components and one pre-existing private report. An exclusive local development lock prevented overlap. No pending earlier app changes needed recovery. Legacy Research Monitor, production schedules/ingestion, main and commercial access gates remain unchanged.

Reviewed Orion final 424B4 accession `0001628280-26-062794`: the cover is dated **September 17, 2026**, distinct from the September 21 filing date and September 3 holdings date. The underwriting definition says 180 days after the prospectus date; the executive/director scope covers Class A and convertible securities, with exceptions and discretionary release. Four exact source spans retain the cover, duration, full scope and exceptions. Applied two internal-only terms for the existing Kenneth Gregg and Christoph Birchler positions. The deterministic calendar boundary is **March 16, 2027**, not a confirmed release/first tradable date. Intraday expiry, current ownership, resale eligibility and actual waivers remain unknown. No position was promoted to liquid/future-liquid and no market value was invented.

Applied additive migration `20260925191241_reviewed_lockup_timeline`. Shared `research.lockup_terms` rows are read-only/source-scoped under RLS; the database calculates a date-only boundary. The existing private snapshot trigger now emits `liquidity/1.3` with a conditional timeline and evidence, without rewriting saved reports. New offline `build_lockup_review.py` verifies the captured document and reproduces the original holdings manifest, enforces the narrow final-prospectus/calendar-day/executive-director path, and records replay-safe private review provenance. Mixed/graduated/trading-day/unresolved trigger wording remains held. No AI calls, added dependencies, services or costs.

The report popup labels the boundary, trigger, day count, method and review date explicitly; original holdings-assessment notes remain separately expandable and dated. This avoids presenting earlier pending-date notes as the current contractual review. UI retains static private reopening and explicit refresh. Existing report contents were not inspected; its ID/content fingerprint remains unchanged after migration, backfill and tests. Current totals remain 22 offerings, 44 biographies, eight positions and eight components, now with two conditional timelines. No new biography/search coverage, quotes or customer reports were generated; temporary QA accounts were rolled back.

QA: production build; 10 Node/API tests; all 43 Python tests including five new date/importer tests; staging rollback lock-up, liquidity isolation, component and holdings suites passed. Coverage includes leap/year boundaries, weekends without trading-calendar adjustment, wrong cover dates/duration/scope rejection, immutable source manifests, replay, cross-account guessed-ID/existence denial, ordinary-customer and anonymous denial, source-write denial, wrong-document suppression, unchanged saved dates and explicit refresh. Backfill rehearsal passed before application; exact replay added no rows. Security advisor is unchanged (known leaked-password warning and twelve intentional default-deny notices). Browser QA with captured reviewer RPC output covers search → person → timeline/evidence → reopen → refresh → keyboard/focus at desktop and 390px mobile; authentication is simulated, not a live user login test. Screenshots were inspected for wrapping and modal overflow.

Publication verified at **2026-09-25 19:20 UTC**: commercial commit `d2789e7e1631c9464d36378d4363e8d53f857d15` is deployed. Render's `index-DQeg5AJ3.js` SHA-256 matches the local build (`24237b24708e263edbf1f62a7addf2e8e42116701bad82bc8444361a9f83ae68`). Health returns `ok` / `staging`; the real Orion holder liquidity endpoint denies unauthenticated access with 401. GitHub **Test Research Monitor** run `36178844597` passed. All five active/queued/waiting/pending/requested lists were empty immediately before the commit. Post-deployment staging checks still show two timelines, one unchanged private report and zero leftover test accounts. No merge or production launch occurred.

Next: prioritize **Electra Therapeutics**, captured final 424B4 accession `0001193125-26-395670` (`import-output/month/10.json`, current raw SHA-256 `a20f78bb4ecb1af6b2df957314603ec26137b264c529e08d6a86076246eb7539`). It has four verified biography/relationship records but no reviewed holdings. Source preflight locates Principal Stockholders at normalized block 3103, with an August 1 holdings basis at 3104 adjusted for the offering; inspect individual rows and full footnotes before selecting any current/projected or award classification. Cohort audit finds nine of the twelve companies with verified people still have no reviewed holdings; absence is not zero ownership. Keep Oura's graduated release conditions and fund-attributed directors held until a matching rule and attribution model are justified. Report history selection remains a focused follow-up. No new owner action blocks testing; licensed quotes, commercial source rights, production Auth, payments and launch remain the existing future gates. No AI-provider approval is needed for this deterministic path.

## 2026-09-25 morning: reconciled award and trust components

Started from clean commercial HEAD `c18335babe3ecfb1a9e51c17b6c8d91df588e7ef`; PR #581 was still draft/open and Render matched the prior release. Held an exclusive local development lock. Staging already contained one real private report; its contents were not inspected or changed. Its ID/content fingerprint remains unchanged after migration, import and rollback QA. No production engine, feed, schedule, legacy styling, main branch or customer access changed.

Applied additive migration `20260925151220_reviewed_ownership_components` and a reviewed internal-only Oura backfill from captured SEC accession `0001193125-26-396051` (S-1/A, September 21). Thomas Hale, Sean Brecker and Michael A. Chapp now have **three parent beneficial totals with eight reconciled components** distinguishing common shares, RSU/option-underlying interests, direct disclosure and trust/family attribution. Source table date is September 15; its preferred/SAFE conversion and RSU net-settlement assumptions remain explicit. Each component retains its exact footnote clause and source passage. Aggregate totals are not labeled ordinary shares, components are not counted again, and all three remain **unknown liquidity**, not cash or confirmed current positions. Graduated lock-up wording/price conditions and award exercise/vesting conditions are retained; exact releases are not invented.

Implementation: strict offline `reviewed-mixed-awards` importer/profile, normalized read-only/source-scoped component RLS, fail-closed reconciliation helper, immutable `liquidity/1.2` snapshot fields, and a component breakdown in the existing private Liquidity Analysis popup. Existing saved reports reopen unchanged; explicit refresh creates a dated version. Legacy client `shares` is null for mixed totals to avoid mislabeling while deployment catches up. No AI provider, paid calls, quote provider or dependency was added. Both older real import manifests reproduce unchanged; the new import was rehearsed with rollback, applied and replayed without duplicates.

QA passed: production build, 10 Node/API tests, 38 Python tests, staging rollback component/privacy/security/holdings suites. Checks cover component sums and missing/hidden evidence, same-document provenance, private/guessed-ID/ordinary-customer/anonymous denial, denied source writes, static reports after source changes and explicit refresh. Source-rich Oura browser QA covers person search, company/person, report generation, each component's evidence, reopen without regeneration, refresh, keyboard/focus and desktop/390px mobile rendering with no horizontal modal overflow. Screenshots were inspected. Authentication is simulated using captured reviewer RPC output, **not a live owner login**. An initial browser selector matched repeated copies of the same footnote; it was scoped to the correct expanded source panel and rerun successfully. An unrelated browser executable-path typo was corrected before the compatibility rerun.

Staging totals: **22 offerings, 44 biographies, eight positions, eight components, eight unknown assessments, zero quotes**; one pre-existing private report preserved and zero leftover test accounts. No biography/search backfill was performed this run. Security advisor remains unchanged: the known leaked-password protection warning and twelve intentional default-deny informational notices. No new warning from the component schema.

Publication verified at **2026-09-25 15:25 UTC**: commercial commit `e8418ff66151f9fb8931fa4bbf943e9ebe87227c` is deployed. Render serves `index-Bsq_ijp8.js`, SHA-256 `ec1ac19fa4f66a0e584de61f5f8c147f403db7c1b1dc0819ff6a2e509db53249`, matching the local build. Health returns `ok` / `staging`; the real Oura holder liquidity endpoint returns 401 without authentication. An initial request timed out during deployment/startup; subsequent checks succeeded. GitHub **Test Research Monitor** run `36153789217` passed; PR #581 remains draft/open. All five active/queued/waiting/pending/requested lists were empty immediately before committing. Orion's retained plain-share browser fixture also passed, confirming backward compatibility. The private report fingerprint is still unchanged after all tests.

Next source task: exact Orion prospectus-trigger/date review and deterministic conditional lock-up calculations, without treating expiry as saleability; then extend remaining recent-month holdings only after identity/instrument/overlap review. Keep Oura's other director/entity totals held rather than inferring fund economics. Live authenticated QA and licensed quote integration remain unverified/unavailable. No new owner decision blocks continued staging work; existing launch gates below remain.

## 2026-09-24 afternoon: dated common-share backfill

Started from clean commercial HEAD `227be96f`; draft PR #581 and staging migrations matched the preceding handoff. No other local development process or active ownership workflow was found; this run held an exclusive local development lock. Preserved the legacy engine, feed, schedules and main branch.

Applied two additional source-reviewed Orion180 positions from SEC accession `0001628280-26-062794`, captured September 23: Kenneth Gregg, 59,935,260 **Class B** common shares; Christoph Birchler, 104,337 **Class A** common shares. These are disclosed pre-offering positions **as of September 3**, not holdings confirmed today. Seven exact spans retain rows, individual footnotes, table basis/headers and the director/executive lock-up terms, exceptions and discretionary release. Gregg's repeated table row and Class B conversion rights are not counted as extra holdings. Ryan Jesenik remains held pending complete identity/relationship and trust review.

Added the deliberately narrow `dated-pre-common` profile to `scripts/build_holdings_review.py`. It requires a final 424B4, a literal table as-of date, matched named row and exact simple common-share footnote. Mixed options/RSUs or trust/fund attribution fail closed. The existing Accelevation manifest reproduces unchanged. Private generated SQL and source payloads remain ignored; no public fixture, access grant, quote or customer report was added. Dry-run and rollback tests passed before the real transaction; exact replay added nothing. Totals are now **22 offerings, 44 biographies, five positions and five unknown liquidity assessments**.

Applied additive migration `20260924230222_separate_holdings_and_filing_dates`: nullable `research.ownerships.holdings_as_of` and report snapshot version `liquidity/1.1` with distinct `holdingsAsOf` and `filingDate`. The deprecated `holdingsDate` filing-date alias remains for old deployed clients. Existing snapshots are never rewritten. UI displays the explicit holdings date or “Not established in this snapshot,” separately from filing date. No RLS/grants/entitlement changes; trigger remains invoker-security. Security advisor results are unchanged: the known leaked-password-protection warning and intentional default-deny table notices.

Validation: production build; 10 Node/API tests; all 34 Python tests (seven holdings-review tests); staging rollback liquidity isolation and real-holdings SQL suites. Tests cover date mismatch/class/count rejection, mixed instrument rejection, static dates after source changes, separate Class A/B positions, cross-account/guessed-ID denial, refresh/retry and ordinary-customer denial. Captured real Orion RPC output was exercised in desktop and 390px mobile browser journeys with simulated authentication: biography search → company/person → private report → source footnotes → reopen → refresh → Escape/focus. Screenshots were inspected. The retained Accelevation fixture also checks backward compatibility for older saved reports. These are not live-user login tests.

Data and migration are applied. Commercial commit `e9a918f25fbcdc11140b343cc81d9afb20c57aa9` was deployed and verified at 2026-09-24 23:10 UTC. Render serves `index-DrMV5tmQ.js`, SHA-256 `74fde1092bf6b794ca5f545dd16872f3ec4adb184c155f61802d94690a571808`, matching the local build. Health returns `ok` / `staging`; the Orion holder endpoint returns 401 without authentication. The first request timed out during deployment/startup; subsequent checks succeeded. All five workflow-active/queue statuses were empty immediately before the commit. There are two explicit holdings dates, three unknown dates, zero saved customer reports and zero leftover test accounts. PR #581 remains draft; no main merge, production launch or access expansion occurred.

Next highest-value source review: Oura accession `0001193125-26-396051`. Its beneficial-ownership totals mix directly held shares, family trust shares, RSUs and options (particularly Michael A. Chapp); do **not** import the aggregate as ordinary shares or personal wealth. Add a reviewed component/overlap model before importing those rows. Separately implement exact contractual trigger/date calculations for Orion's lock-up: the filing date is not the prospectus date, exceptions apply, and expiry alone never establishes saleability. Both Orion assessments intentionally remain unknown with no computed release date or market value. These tasks need no owner intervention. Live authenticated UI QA remains pending an authorized session; quote licensing/Auth/launch decisions remain below for the nightly digest.

## 2026-09-24 midday: first holdings/footnote backfill

Verified the preceding release at `48043a47` on Render and confirmed the commercial branch had not advanced. Imported three Accelevation projected post-offering Class A positions from captured SEC accession `0001628280-26-062945`: Michael Rubiera 1,375,666; Charles Hillman 226,178; Ericka Harrison 65,695. Nine exact source spans retain the selected rows, table headers, offering assumptions, individual trust footnotes and planned lock-up wording. An immutable private manifest binds the review to the original document SHA-256. No new biographies, owner roles, access grants, customer reports or quotes were created.

All three liquidity assessments are deliberately **unknown**: these are projected positions, not confirmed current holdings or personal cash value. The trust amounts are included in the totals, not added again or attributed as personal wealth. The preliminary filing says lock-ups will be signed for not less than 180 days from the prospectus date, subject to consent/exceptions. An executed start/release date is not established, so both dates remain null. The fourth executive has no imported position; absence is not zero ownership.

`scripts/build_holdings_review.py` is an offline, explicit-selection importer for this narrow preliminary projected-Class-A/trust/conditional-lockup pattern, reusing the existing normalizer and identity convention. It verifies raw/normalized hashes, exact name/row/share-cell/footnote association, source lineage against canonical data, and records a private manifest. A conflicting changed import fails; exact replay adds nothing. Raw inputs and generated SQL remain ignored/private, never in the static frontend.

The data transaction was rehearsed and rolled back, then applied and replayed successfully. Four new importer tests and `tests/database-holdings-review.sql` pass. The SQL test checks all three values, footnote/provenance retention, blank dates/market values, static report reopening and ordinary-customer denial; temporary accounts/reports roll back. The UI now labels post-offering positions explicitly as projected and exposes accession/hash details, instead of the ambiguous label “post offering basis.” A captured real RPC fixture is used for browser QA; authentication remains simulated, not a live-user login test.

Next: expand source review to the other recent-month issuers (particularly the already captured Oura/Orion footnotes), preserving instrument and trust/fund distinctions. The first three positions now produce substantive evidence in a newly requested or explicitly refreshed report; existing private snapshots are not rewritten. No owner action is needed for further evidence backfilling. Quote licensing, optional AI provider and launch/Auth decisions remain in the nightly list below.

Additional QA passed: existing liquidity isolation/security SQL suites, production build, and desktop/mobile browser checks with the captured source-rich report (simulated login). The report's source passages are expandable and machine-readable block locators render as readable block references. The accordion no longer incorrectly claims that no reviewed positions exist before the report is opened.

Publication verified at 2026-09-24 19:19 UTC: commercial commit `3f27108167ca37f4cf972b89707484ef68fb4d35` is deployed to Render staging. Its served `/assets/index-Chuugp4P.js` SHA-256 matches the local build: `73c9051b977bc189bbb0775a35b13ccebf5929d98d12f4ebf967c33090d3c109`. Health returns `ok` / `staging`; unauthenticated access to the real holder liquidity endpoint returns 401. Staging has 22 offerings, 44 biographies, three positions and three assessments, with zero private reports and zero leftover test accounts. The ownership workflow was absent from all active/queued/waiting/pending/requested lists immediately before committing. Authenticated live-user interaction remains unverified; database authorization and simulated browser tests are distinct evidence. PR #581 remains draft, with no production changes. Next run can proceed to the next recent-month source review rather than repeating this deployment check.

## 2026-09-24: private Liquidity Analysis foundation

Implemented the holder Liquidity Analysis button, authenticated GET/POST API, private static database snapshots, reopen without regeneration, explicit versioned refresh and retry idempotency. The UI uses four categories: currently liquid, potential future liquidity, illiquid, and insufficient evidence. Evidence includes ownership passages, separately reviewed footnotes/restrictions, filing accession and document hash in the stored snapshot. Shared reviewed facts and private account reports are separate. No service-role key or AI provider is used.

Applied staging migration `20260924164646_private_liquidity_reports.sql`. The database generates report contents itself, rejects client-authored reports, enforces ownership/entitlement/access controls and grants no customer updates/deletes. Expired assessments, uncertain current positions or personal economic interest cannot be reported as currently liquid. Lock-up expiry does not automatically make shares liquid. Source facts changing do not rewrite saved snapshots.

Validation: production build, 10 unit/API tests, targeted browser test for the holder popup/reopen/refresh/Escape/focus, and rollback SQL tests for classification, private access, request replay, refresh versions, tamper denial and revoked entitlement passed. Browser authentication is simulated using the private pilot fixture; database policies were exercised in staging with disposable accounts and rolled back. This is not a completed live user login test.

The 22-company/44-biography month import is already applied, with no duplicate rows from replay. No new real holdings or liquidity assessments have been imported in this iteration. Current live reports therefore accurately report insufficient holdings evidence. Quote valuation remains unavailable. Do not describe this foundation as a completed financial analysis or an AI-powered review.

Publication: prepared for the existing commercial branch and Render staging. Verify the deployed asset before claiming the button is live. Legacy production engine, feed, Pages and schedules are unchanged.

## Next executable work

1. Current release is verified; test actual authenticated UI when an authorized browser session is available. Do not repeat unchanged simulated journeys as a substitute for live login QA.
2. Review and backfill exact ownership-table rows and holder-specific footnotes for the existing cohort. Separate issuer securities, share classes, trust/fund attribution, projected vs current holdings and overlapping positions. Reuse the original engine where appropriate.
3. Populate reviewed liquidity assessments only with explicit source passages, conditions, dates and review validity. Add release-date calculation tests for exact contractual wording before automating lock-up calculations. No default 180-day assumptions.
4. Add report history selection in the UI; old snapshots are retained already and source-version details are now displayed.
5. Integrate security-matched licensed quotes and reconciled positions before exposing market estimates. Do not infer future prices, cash proceeds or saleability.
6. Evaluate a source-grounded AI extraction/explanation adapter after the deterministic evidence path is established. No paid calls or new external provider transmission yet.

## Owner decisions / launch gates for the 6 PM digest

- Quote provider: choose a provider with commercial display/storage rights before live or last-known pricing integration; research options before asking the owner to spend.
- AI provider: only request setup/cost approval if evidence review warrants adding it. Current foundation needs no AI key.
- Auth: existing leaked-password-protection warning remains. Review plan/support and configure before commercial launch: https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection . No new security advisor warning was introduced by the liquidity schema.
- Payments, commercial source rights, production Auth and iporoll.com launch remain future gates. Continue staging work without waiting for these.

Maintain this ledger on subsequent runs. Do not re-import the month batch or reapply migrations blindly. Check Refresh Prospect Ownership History before every commit and preserve unrelated changes. Continue the established three daily development sessions and 6 PM Pacific digest.
