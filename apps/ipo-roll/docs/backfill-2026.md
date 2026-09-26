# Commercial 2026 backfill checkpoint

Owner authorization, September 25, 2026: extend IPO Roll's commercial staging backfill to **January 1, 2026 through the present**, including April/May and qualifying smaller operating-company IPOs. The previous historical hold is superseded for this commercial work. Do not change legacy ingestion, production schedules, Pages, or the ownership-history commit guard.

Include IPOs priced during the interval even if their initial registration predates January 1, as well as qualifying filing activity during the interval. Resolve issuer and registration identity before updating an existing offering. Do not equate a later amendment with a new IPO. Pre-/post-offering snapshots must remain distinct.

## Baseline audited September 25

Source: legacy `docs/data/filings.json` at `f4bdf65261fc583a406da3fd0b653b111143a2f6`, generated `2026-09-25T16:42:05.707069+00:00`. Private intake batch `e1554778-d4c5-54a7-87dd-1505e4e06f48`; payload SHA-256 `5fe74d887c35772eab6d61b7b69a08d295c7453f85900c5483abac2265741142`. Intake has 93 source records; 90 have qualifying interval dates. The three remaining records are outside the interval. The intake contains **unverified observations**, never publication approval.

This is an inventory of the existing feed, **not a complete census of 2026 IPOs**. Independently reconcile SEC coverage for each month before marking that month complete. Count biographies, verified ownership, footnotes and liquidity evidence separately from company coverage.

| Cohort month | Candidates | Exact staged snapshots | Existing issuer needing reconciliation | New source review |
| --- | ---: | ---: | ---: | ---: |
| January | 5 | 0 | 0 | 5 |
| February | 9 | 0 | 0 | 9 |
| March | 2 | 0 | 0 | 2 |
| April | 11 | 0 | 0 | 11 |
| May | 8 | 0 | 0 | 8 |
| June | 13 | 0 | 0 | 13 |
| July | 6 | 0 | 0 | 6 |
| August | 13 | 3 | 0 | 10 |
| September through 25th | 23 | 18 | 1 | 4 |
| Total | 90 | 21 | 1 | 68 |

Cohort uses pricing date when within the interval; otherwise the earliest qualifying filing date. These counts are not monthly completed-IPO totals. An exact staged snapshot does not establish complete holder/footnote coverage or current lifecycle status.

## Initial capture checkpoint (superseded by release below)

January capture completed for all five candidates: 15 filing documents and 34 automatically located biography candidates. These are **unreviewed candidate passages**, not verified people/affiliations. Capture packets and content-addressed bytes are retained privately under `import-output/year-2026/archive/`; no historical offering, biography or holding was imported in this step.

`scripts/build_backfill_queue.py` validates the intake checksum, uses inclusive boundaries, detects duplicate filing identities, skips exact staged snapshots, and holds different accessions for an existing issuer for reconciliation. It records a hash of the staging comparison. Two tests cover pre-year registrations priced in-year, interval boundaries, empty months, exact deduplication, issuer reconciliation, duplicate identities and tampered intake rejection.

Private inputs/queue/capture artifacts are under ignored `import-output/year-2026/`. Recreate the intake from the exact source commit if the workspace expires; fetch a new read-only staging snapshot before applying any reviewed release. Captured evidence alone is not reviewed or imported. All generated source payloads stay out of Git and frontend assets.

## January staging release — September 26, 2026

Applied the previously prepared 93-record SEC Monitor intake to private staging quarantine (90 interval candidates); reviewed and released **five January offerings and 15 executive biographies**. Staging now contains **27 offerings, 59 biographies and 10 ownership positions**. This release adds no ownership positions or market quotes. All five offerings remain unpublished with `internal_review` access; ordinary customers cannot retrieve them.

| Reviewed issuer | Ticker | Pricing date | Preliminary range | Final IPO price | Base offering value |
| --- | --- | --- | --- | ---: | ---: |
| Aktis Oncology | AKTS | 2026-01-08 | $16.00–$18.00 | $18.00 | $317,700,000 |
| BitGo Holdings | BTGO | 2026-01-21 | $15.00–$17.00 | $18.00 | $212,788,710 |
| EquipmentShare | EQPT | 2026-01-22 | $23.50–$25.50 | $24.50 | $747,250,000 |
| Ethos Technologies | LIFE | 2026-01-28 | $18.00–$20.00 | $19.00 | $199,999,985 |
| York Space Systems | YSS | 2026-01-28 | $30.00–$34.00 | $34.00 | $629,000,000 |

Final prospectus accessions, respectively: `0001193125-26-009078`, `0001628280-26-003180`, `0001628280-26-003334`, `0001193125-26-029993`, `0001193125-26-030469`. Initial registrations predate 2026 and remain separate from pricing dates. The queued Yellowstone Midco identity was reconciled to York Space Systems from its prospectus, preserving issuer CIK and registration lineage. Base offering values are IPO offering amounts, not personal proceeds.

Reviewed complete, person-specific SEC biography passages for three executives per issuer. People Search now returns three University of Michigan matches and ten Harvard matches across staging (previously two and eight). The newly supported Michigan match is Devjyoti Rudra at York. Biography evidence does not establish beneficial ownership, stock quantities or saleability.

Retained 15 filing documents plus normalized text/metadata as 35 immutable private evidence artifacts in `ops.sec_artifacts`. The release uses existing import/review scripts; no pipeline rewrite or migration. Private inputs, reviewed selections, manifest and generated SQL remain under ignored `import-output/year-2026/january-release/` and `january-reviews.json`; source payloads are not Git/frontend assets.

Validation: full transaction rehearsal with rollback; apply; exact replay without duplication; post-apply rollback QA checking counts, authoritative pricing versus preliminary ranges, root dates, issuer identity, detail quote safeguards, evidence search, no inferred beneficial-owner match, ordinary-customer denial and anonymous RPC denial. Five pre-existing private liquidity reports retained their identical aggregate content fingerprint. These are database role/RPC tests, not a live authenticated browser journey. The old `tests/database-month-review.sql` records the earlier 22/44 baseline and must be scoped to that cohort before reuse; its global exact counts are now historical.

For the original 90-candidate inventory, January moves from zero to five reviewed staged candidates. Overall comparison is now 26 reviewed staged candidates, one existing issuer awaiting reconciliation and 63 requiring new source review. This is **not a complete January census or a completed year backfill**. Holder, footnote and liquidity coverage remains separately incomplete.

## Acceleration authorized September 25 (Pacific)

Owner requested faster completion. Development/backfill is now scheduled hourly, including overnight, while the historical backlog remains. Keep the separate 6 PM Pacific digest; skip overlapping work using the shared development lock. Prioritize source-reviewed imports and ownership/footnote coverage ahead of cosmetic changes. Reuse retained SEC artifacts and batch independent preparation within SEC access limits. Evidence, access and commit guards remain unchanged. Restore the previous 8 AM/noon/4 PM Pacific development cadence after independently verifying historical completion.

February capture is prepared for all nine candidates (27 filing documents, 42 automatically located unreviewed biography candidates). The first reviewed release below supersedes the capture-only status for four issuers. Automatic candidate counts are not verified-person counts. Reuse retained artifacts for the remaining review.

## First February release — September 26, 2026

Applied four reviewed offerings and 13 complete executive biographies, bringing staging to 31 offerings and 72 biographies; ownership positions remain 10. Archived 28 private evidence artifacts for 12 SEC filing documents. All data remains unpublished/internal_review. Rehearsal, apply, exact replay and post-apply database role/RPC QA passed; existing private reports remained unchanged. Live staging health passed, but the unauthenticated HTTP offerings check timed out and live authenticated browser QA was not performed.

| Issuer | Ticker | Pricing date | Preliminary range | Final IPO price | Base offering value | Final prospectus |
| --- | --- | --- | --- | ---: | ---: | --- |
| Veradermics, Incorporated | MANE | 2026-02-03 | $14.00–$16.00 | $17.00 | $256,319,999 | 0001628280-26-005505 |
| Eikon Therapeutics | EIKN | 2026-02-04 | $16.00–$18.00 | $18.00 | $381,196,800 | 0001193125-26-039375 |
| Forgent Power Solutions | FPS | 2026-02-04 | $25.00–$29.00 | $27.00 | $1,512,000,000 | 0001193125-26-040029 |
| Bob’s Discount Furniture | BOBS | 2026-02-04 | $17.00–$19.00 | $17.00 | $330,650,000 | 0001628280-26-005868 |

Biography search now supports the newly reviewed named executives and their literal education/employment passages, including Ryan S. Fiedler’s investment banking experience and Carl Lukach’s Georgetown education across a page boundary. A biography is not an ownership position. Veradermics holdings are held because table and footnote date bases conflict (September 30 versus December 31, 2025), quantities mix common shares/options, and Tim/Timothy Durso needs identity reconciliation. Lock-up expiry alone would not establish current saleability.

Within the original 90-candidate inventory: January 5/5 and February 4/9 candidates are now reviewed/imported. Overall comparison is 30 staged candidates, one existing issuer reconciliation and 59 requiring new source review. This is inventory progress, not a complete SEC census. Remaining February: Once Upon a Farm, SOLV Energy, ARKO Petroleum, Generate Biomedicines and SpyGlass Pharma. See `february-a-release/manifest.json` and private holdings notes for reproducible release evidence.

## Second February release — September 26, 2026

Applied the remaining five February feed candidates and 17 complete, person-specific SEC biographies. Staging now has **36 offerings / 89 biographies / 10 ownership positions**. January 5/5 and February 9/9 candidates from the original feed inventory are reviewed/imported; **neither month is an independently verified complete SEC census**. Across that inventory, 35 candidates are staged, one issuer requires reconciliation, and 54 need new source review.

| Issuer | Ticker | Pricing date | Preliminary range | Final IPO price | Base offering value | Final prospectus |
| --- | --- | --- | --- | ---: | ---: | --- |
| Once Upon a Farm, PBC | OFRM | 2026-02-05 | $17.00–$19.00 | $18.00 | $197,949,762 | 0001193125-26-041885 |
| SpyGlass Pharma | SGP | 2026-02-05 | $15.00–$17.00 | $16.00 | $150,000,000 | 0001628280-26-006068 |
| SOLV Energy | MWH | 2026-02-10 | $22.00–$25.00 | $25.00 | $512,500,000 | 0001193125-26-046879 |
| ARKO Petroleum | APC | 2026-02-11 | $18.00–$20.00 | $18.00 | $199,999,998 | 0001193125-26-049767 |
| Generate Biomedicines | GENB | 2026-02-26 | $15.00–$17.00 | $16.00 | $400,000,000 | 0001193125-26-083190 |

Source documents retain issuer CIK and registration lineage. ARKO Petroleum's APC ticker is sourced from its prospectus; ARKO is its separate parent. Once Upon a Farm's total includes issuer and selling-stockholder shares, not a person's cash proceeds. No inferred holdings or quotes were added. Selected biographies include complete cross-page evidence for Malik Y. Kahook and manually located ARKO executives. Search now returns four University of Michigan matches and 14 Harvard matches; each result preserves the literal person-specific passage and company relationship, without converting employment or visiting appointments into degrees.

Archived 35 immutable private evidence artifacts for 15 SEC documents. Rehearsal with rollback, atomic apply, exact replay and post-apply role/RPC QA passed: exact prices/dates/ranges/values, biography search and cross-page continuation, unsupported search rejection, no inferred beneficial-owner role, saved/unsaved IPOs, reviewer access, ordinary-customer denial and anonymous denial. Five pre-existing private liquidity reports retained the same aggregate fingerprint; no customer report was generated or refreshed. Zero temporary QA accounts remain. Data remains unpublished/internal_review. This is an applied data-only staging release, not a new application deployment.

Live health returned 200/ok/staging after an initial timeout; unauthenticated offerings returned 401. Live authenticated browser QA remains unperformed. No UI, schema, source access, legacy engine/feed/Pages, production schedule, billing or provider changes.

ARKO holdings triage is retained privately: the projected post-offering parent row lists Class A conversion interests overlapping its Class B position; never count these twice or attribute them to individual executives. Individual dashes are not confirmed present-day zero holdings, particularly because offering purchases are excluded. No January/February positions or lock-up dates are imported by this release.

Private reproducibility files: `february-b-reviews.json`, `select-february-b.py`, and `february-b-release/` (manifest, SQL, QA, holdings notes). March's two feed candidates, MiniMed and HMH, are now captured in six hash-verified documents but remain **unreviewed/unimported**. Automatic biography discovery found no candidates; manual review must preserve expected post-offering appointment wording. See private `march-capture-results.json` and `march-review-handoff.md`. These counts do not establish historical completeness.

## Next actions

1. Continue the remaining March–September SEC Monitor queue, starting with the two captured March candidates. Reconcile current staging identities before each release, preserve preliminary pricing and final terms, and independently check omitted SEC candidates before marking a month complete.
2. Review January ownership tables and footnotes independently before populating class/series, quantities, attribution, holdings dates or lock-up evidence. Unknown cash realizability stays unknown; do not infer personal proceeds from offering size or position differences.
3. Apply only small reviewed releases with immutable evidence, rollback QA and exact replay. Keep rights as internal review and customer access denied until approved.
4. Never generate or modify saved account-private Liquidity Analysis reports through backfill. Users request their own static report or explicit refresh.
5. No new setup, spending or paid AI provider is needed for this SEC review. Quote licensing continues to gate market-value estimates.
