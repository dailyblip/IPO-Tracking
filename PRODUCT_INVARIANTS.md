# Research Monitor Product Invariants

These are intentional product decisions, not suggestions. Future changes must preserve them unless the user explicitly asks to change them.

## Main filing queue

The main queue contains exactly these columns, in this default order:

1. Company Name
2. Ticker
3. Form
4. Stage
5. Filed
6. IPO Size / Offering Value
7. Filing Price
8. Final IPO Price
9. Current Price

**Do not add a Public Signals / Signal column to the main queue.** Signal data may remain in the feed or backend for other uses, but it must not appear as a queue column or be included in the main queue search unless explicitly requested.

## Stanford display

- Do not show an “S” badge/tag.
- Confirmed Stanford-connected beneficial owners are shown using Cardinal-red text.
- Red text requires a confirmed Stanford affiliation; ambiguous or weak matches do not qualify.
- The individual detail record may show a short Stanford connection note and a 1–5 confidence score.

## Change discipline

Before changing `docs/index.html`, check this file and `src/test_dashboard_ui.py`.
If a requested change conflicts with an invariant, do not silently reinterpret the invariant. Only change it when the user explicitly requests that product behavior to change.
