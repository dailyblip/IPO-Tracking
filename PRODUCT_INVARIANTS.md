# Research Monitor Product Invariants

These are intentional product decisions, not suggestions. Future changes must preserve them unless the user explicitly asks to change them. New requirements are additive unless they explicitly supersede an older requirement.

## Priority order

1. Lifecycle correctness for priced/trading IPOs.
2. In-company expandable beneficial-owner detail.
3. Reliable Recent Activity ticker motion.
4. Restrained Stanford visual-style alignment.
5. Pagination only when the qualifying feed reaches roughly 50–75 records; add a Year filter only around 150–200+ records.

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
- Omit IPOs below $100 million in offering size/value.
- If size cannot be established reliably from authoritative public evidence, do not publish the issuer in the qualifying main feed.
- Omit SPACs, reverse SPACs, ETFs, ETNs, closed-end funds, interval funds, mutual funds, trusts, BDCs, commodity pools, unit investment trusts, grantor trusts, pooled investment vehicles, and other non-operating-company investment products.
- Prefer SEC evidence for filing/IPO facts, then issuer and official exchange sources where appropriate.
- Never guess, infer, fabricate, use stale values, or rely on ticker-only matching to fill gaps.
- Incorrect data is release-blocking; unresolved conflicts should remain blank.
- Preserve source/provenance where the architecture allows.

## Lifecycle and pricing

- Priced IPOs must populate Pricing Date and Final IPO Price when authoritative evidence is available.
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
- Historical Stanford regrading/backfill from June 1, 2026 through the present remains required until verified complete in the live feed.

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

Use a restrained Stanford-aligned visual system without turning the monitor into a marketing site. Preserve the function-first researcher workflow and the semantic meaning of Cardinal-red affiliation highlighting. Favor official Stanford palette values, Source-family typography with safe system fallbacks, strong white space, and accessible contrast. Do not add or imitate protected Stanford wordmark/logo artwork unless explicitly requested and properly sourced.

## Scale strategy

Keep one dataset rather than static monthly/yearly pages. When the qualifying feed reaches roughly 50–75 records, add pagination with 25 rows per page by default and optional 25/50/100 controls while preserving filters and sort across pages. Around 150–200+ records, add a Year filter.

## Change discipline

Before changing `docs/index.html`, check this file and `src/test_dashboard_ui.py`.

Before every repository commit, verify that the `Refresh Prospect Ownership History` workflow is neither running nor queued. If it is active, do not commit code or generated feed changes.

Keep lifecycle/data fixes separate from unrelated UI changes where practical. Run relevant regression tests and verify GitHub Pages before calling a change live. Never claim a fix is live, tests passed, or the feed is corrected until actually verified.
