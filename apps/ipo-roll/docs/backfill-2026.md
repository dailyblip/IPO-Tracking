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

## Next actions

1. Continue the remaining February–September SEC Monitor queue, starting with nine February candidates. Reconcile current staging identities before each release, preserve preliminary pricing and final terms, and independently check omitted SEC candidates before marking a month complete.
2. Review January ownership tables and footnotes independently before populating class/series, quantities, attribution, holdings dates or lock-up evidence. Unknown cash realizability stays unknown; do not infer personal proceeds from offering size or position differences.
3. Apply only small reviewed releases with immutable evidence, rollback QA and exact replay. Keep rights as internal review and customer access denied until approved.
4. Never generate or modify saved account-private Liquidity Analysis reports through backfill. Users request their own static report or explicit refresh.
5. No new setup, spending or paid AI provider is needed for this SEC review. Quote licensing continues to gate market-value estimates.
