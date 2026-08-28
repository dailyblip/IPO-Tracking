# Research Monitor Product Invariants

These are intentional product decisions, not suggestions. Future changes must preserve them unless the user explicitly asks to change them. New requirements are additive unless they explicitly supersede an older requirement.

## Priority order

1. Include qualifying operating-company IPOs regardless of offering size going forward while preserving size filters.
2. Preserve authoritative preliminary Filing Price/range across lifecycle reconciliation.
3. Lifecycle correctness for priced/trading IPOs.
4. In-company expandable beneficial-owner detail.
5. Reliable Recent Activity ticker motion.
6. Keep the preliminary UI stable; save the larger IPO Roll product redesign for a separate future product repository.
7. Pagination only when the qualifying feed reaches roughly 50–75 records; add a Year filter only around 150–200+ records.

Do not skip a higher-priority unresolved item for opportunistic polish, refactors, or feature expansion.

## Main filing queue

The main queue contains exactly these columns, in this default order:

1. Company Name
2. Ticker
3. Form
4. Stage
5. Filed
6. Pricing Date
7. IPO Size / Offering Value
8. Filing Price
9. Final IPO Price
10. Current Price
11. Public Signals

- Priority and Status are not main-table columns.
- Clear Filters and draggable-column behavior remain available.
- Public Signals remains visible in the main queue.
- All-uppercase SEC issuer names are normalized for display while preserving correct mixed-case names and known acronyms/brands.

## Qualifying feed and data integrity

- Public facts only.
- Going forward, qualifying operating-company IPOs are included regardless of offering size/value; the former $100 million publication floor is retired for new/current ingestion.
- Do not run a dedicated historical backfill solely to add small/minor IPOs omitted under the former size floor.
- Keep offering-size filtering in the UI with `Any size` as the default and optional thresholds such as $100M+, $250M+, $500M+, $1B+, and $5B+.
- If offering size cannot be established reliably from authoritative public evidence, leave the size blank rather than guessing. Unknown size alone is not a reason to exclude an otherwise confirmed operating-company IPO.
- Omit SPACs, reverse SPACs, ETFs, ETNs, closed-end funds, interval funds, mutual funds, trusts, BDCs, commodity pools, unit investment trusts, grantor trusts, pooled investment vehicles, and other non-operating-company investment products.
- Prefer SEC evidence for filing/IPO facts, then issuer and official exchange sources where appropriate.
- Never guess, infer, fabricate, use stale values, or rely on ticker-only matching to fill gaps.
- Incorrect data is release-blocking; unresolved conflicts should remain blank.
- Preserve source/provenance where the architecture allows.

## Lifecycle and pricing

- Priced IPOs must populate Pricing Date and Final IPO Price when authoritative evidence is available.
- Preserve an authoritative preliminary Filing Price or price range from preceding S-1/S-1A filings when a company transitions to 424B4/Priced.
- A priced IPO with blank Filing Price must have its preceding S-1/S-1A history checked before the blank is accepted; if no reliable preliminary price was disclosed, leave it blank rather than guessing.
- A live current-price quote must never be attached to an issuer that is genuinely pre-pricing.
- Ticker/provider collisions and impossible states such as `Pre-pricing + live quote` are release-blocking defects.
- Lifecycle fixes must be generic at the issuer/lifecycle handoff level rather than one-off patches.

## Stanford display and research

- Do not show an “S” badge/tag.
- Confirmed Stanford-connected beneficial owners are shown using Stanford Cardinal red `#8C1515`.
- Red text requires a confirmed Stanford affiliation; ambiguous or weak matches do not qualify.
- The company name is Cardinal red only when at least one confirmed beneficial owner has a confirmed Stanford affiliation.
- The specific confirmed Stanford-affiliated beneficial owner is also Cardinal red in the company detail view.
- Person detail may show a concise Stanford connection note and a 1–5 confidence score where supported.
- Historical Stanford regrading/backfill from June 1, 2026 through the present is verified complete in the live feed. The June-present ownership refresh and SEC-confirmed Stanford recovery remain the canonical maintenance path for this coverage.

## Person detail

- Beneficial-owner/person detail stays inside the company view as a single-open accordion; do not restore a nested person modal.
- Show only filing-supported ownership, liquidity, lock-up, sale, and realized-cash facts.
- Do not force-fill unsupported fields with repeated “Unknown” values.
- Prefer clear liquidity/lock-up status and lock-up end date when supported.

## Activity UI

- Monthly qualifying IPO activity begins June 1, 2026 and advances through the actual current month.
- Recent Activity remains a horizontal ticker driven by existing qualifying activity data.
- The ticker must continue reliably after mouse/keyboard interaction while respecting reduced-motion accessibility preferences.
- The ticker is UI-only and must not alter ingestion/feed logic.

## Stanford visual styling

Use the current preliminary-version styling without a broad redesign. Preserve the function-first researcher workflow and the semantic meaning of Cardinal-red affiliation highlighting. Do not implement the future IPO Roll product mockup in this repository; that sellable product should be created later in a separate repository and consume a validated/versioned feed from this canonical research pipeline.

## Scale strategy

Keep one dataset rather than static monthly/yearly pages. When the qualifying feed reaches roughly 50–75 records, add pagination with 25 rows per page by default and optional 25/50/100 controls while preserving filters and sort across pages. Around 150–200+ records, add a Year filter.

## Change discipline

Before changing `docs/index.html`, check this file and `src/test_dashboard_ui.py`.

Before every repository commit, verify that the `Refresh Prospect Ownership History` workflow is neither running nor queued. If it is active, do not commit code or generated feed changes.

Keep lifecycle/data fixes separate from unrelated UI changes where practical. Run relevant regression tests and verify GitHub Pages before calling a change live. Never claim a fix is live, tests passed, or the feed is corrected until actually verified.
