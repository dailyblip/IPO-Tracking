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

## Work prepared

January capture completed for all five candidates: 15 filing documents and 34 automatically located biography candidates. These are **unreviewed candidate passages**, not verified people/affiliations. Capture packets and content-addressed bytes are retained privately under `import-output/year-2026/archive/`; no historical offering, biography or holding was imported in this step.

`scripts/build_backfill_queue.py` validates the intake checksum, uses inclusive boundaries, detects duplicate filing identities, skips exact staged snapshots, and holds different accessions for an existing issuer for reconciliation. It records a hash of the staging comparison. Two tests cover pre-year registrations priced in-year, interval boundaries, empty months, exact deduplication, issuer reconciliation, duplicate identities and tampered intake rejection.

Private inputs/queue/capture artifacts are under ignored `import-output/year-2026/`. Recreate the intake from the exact source commit if the workspace expires; fetch a new read-only staging snapshot before applying any reviewed release. Captured evidence alone is not reviewed or imported. All generated source payloads stay out of Git and frontend assets.

## Next actions

1. Review the completed January captures for Aktis Oncology, BitGo, EquipmentShare, Ethos Technologies and Yellowstone Midco. Check authoritative current final terms, preceding preliminary pricing and operating-company eligibility. Review human biographies and holder identities independently.
2. Apply small reviewed staging releases with immutable evidence, transaction rollback tests and exact replay checks. Preserve source rights as internal review; ordinary customer access remains denied. No duplicate re-import of existing offerings.
3. Populate the approved beneficial ownership grid with class/series, shares versus awards, ownership attribution, holdings date, footnotes and lock-up evidence. Unknown cash realizability stays unknown. Do not infer sale proceeds from pre-/post-offering differences or issuer capital raised.
4. Work forward through February–September gaps and reconcile missing SEC candidates. Account-private Liquidity Analysis is generated only on user request; this backfill must not generate, update or expose anyone's saved report.
5. Report reviewed/imported progress by month in the existing nightly digest. No new owner setup or spending is needed for SEC review. Quote licensing continues to gate market-value estimates; do not add a paid AI provider.

No month is yet marked complete. No historical research offering was published by this initial inventory/capture step.
