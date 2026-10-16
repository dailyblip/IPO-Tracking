# IPO Roll: profiles, liquidity and ongoing discovery

Accepted development direction, September 28, 2026, following the owner's
"Proceed" response to the corrected Opus specification review. This document
records the corrections and acceptance gates; it is not a claim that the proposed
features are deployed. The development log records actual implementation status.
It supplements comprehensive-research.md and the existing product safeguards.

## Product and source rules

Preserve the graphite/teal/blue workspace, existing navigation, filters, column
dragging, Recent Activity and single-open company/person accordion. Keep the
holder action labeled exactly **Liquidity Analysis**. Add an evidence-linked
person profile across offerings without replacing these workflows. Prototype
save, alert and export success messages are demonstrations, not working features.
Only show success after an authenticated operation actually succeeds.

Full reviewed biographies remain institution-neutral, including factual school
or employer mentions. No special university branding, navigation, badges,
counters, highlighting or affiliation enrichment. Do not drop people because
biographies, quantities or relationships are missing; show their sourced capacity
or hold an unresolved identity explicitly.

Continue January 1, 2026–present coverage and independent SEC reconciliation.
The legacy Monitor inventory is reusable evidence/candidate input, not the census
denominator. Keep production ingestion, Python engine, Pages, schedules and main
unchanged. Commercial source payloads stay private and unpublished until the
existing evidence and rights gates are met.

## Identity and positions

Canonical cross-offering identity needs reviewed links between person records,
with evidence, reviewer provenance and an explicit unresolved state. A name
match, biography similarity or shared employer is only a proposal. CIK can aid
identity; reviewed non-CIK links must also be possible. Record organizations,
trusts, funds and aggregate groups distinctly from natural people.

A filing may have multiple reporting owners. Preserve every owner and the
owner-to-row relationship rather than assigning the entire filing to one person.
Separate personal economic ownership from beneficial ownership, voting/dispositive
power and fund/trust attribution. Record actual versus projected positions,
security class, instrument, conversion/exercise conditions, holding date and
source version. Do not count overlapping totals/components twice. A disclosed
historical position is not confirmation of current holdings.

Amendments reconcile facts and rows with explicit supersession/conflict evidence.
The newest filing does not automatically replace all earlier facts. Chronology
validation is event-specific: a pre-IPO holding/transaction is not intrinsically
invalid. Unknowns and conflicts remain visible; never manufacture zero values.

## Historical value, sales and timeline

Historical IPO-price estimates require reviewed quantities and demonstrated
compatibility with the authoritative final IPO price, security/class and
conversion basis. Label the estimate, holdings date, pricing date and exact
source. Never present it as current wealth, liquid cash or saleability.

Present compatible positions separately. No cross-class, cross-instrument,
actual/projected or personal/fund sum merely because a prototype has a total.
User-entered hypothetical scenarios remain visibly separate from established
facts and never alter shared records or a saved report.

Distinguish proposed sales, final offering terms and completed named-holder sales.
A final 424B4 with selling-holder terms does not alone prove that a sale closed.
Gross completed-sale proceeds require evidence of the named holder's shares
actually sold and the applicable price. Company offering proceeds are separate;
fees, taxes and net proceeds remain unknown without their own evidence.

The timeline retains sourced triggering events, exact contractual date rules,
exceptions, early releases, vesting, exercises, registration/resale conditions and
transfer restrictions. No default 180-day lock-up. Expiry alone does not establish
saleability. Preserve liquid/future/illiquid/insufficient-evidence categories with
conditional dates and expandable passages. Never predict stock prices or cash.

Paid quotes remain deferred and optional. Current market value is unavailable
without an approved licensed, security-matched feed. Preserve an integration
interface, but do not substitute IPO price for a current quote or request provider
setup as a standing blocker.

## Private immutable analysis

Generate only on the requesting signed-in account's action. Keep shared facts
separate from private reports, request state and history. Database RLS and server
authorization must hide other accounts' report contents and existence, including
guessed IDs. Repeated clicks reopen the saved version; explicit refresh creates
a new dated snapshot. Imports, price changes and date changes never rewrite old
reports. Preserve version `liquidity/1.6` and earlier readable snapshots; do not
reset versions to the prototype specification's older number.

Retain the current limits of 100 new reports/account and ten new versions per
account/offering/subject in rolling 24 hours. The proposed 200/20 values are not
adopted. Serialize creation across subjects and direct insertion paths; counts
must include the account's reports even if source access later hides them.
Reopen/replay at quota remains available. Rejected or rolled-back writes do not
consume a report slot. Test overlapping real database sessions and stale
transaction snapshots, not only sequential mocks. API quota responses should be
clear without exposing internal database diagnostics.

## Durable discovery, review and QA

Implement an isolated commercial staging path from independent SEC discovery to
capture, review, idempotent import and repeatable QA. Track issuer, registration,
accession, retrieval cutoff, freshness and incomplete intervals. Discover new
registrations, amendments and final pricing filings without owner-supplied names.
An 18-month monitoring window is an explicit scope, never proof of all-history
coverage. Reuse authorized Monitor artifacts and contact configuration without
redirecting production ingestion.

Automatic fact approval is not authorized by this specification. Evidence-linked
candidates with ambiguity/conflicts remain held. Any later automated promotion
must have a separately reviewed, narrow evidence contract and fail closed.
Optional AI extraction retains model/prompt/version provenance and treats filings
as untrusted; no new paid provider or account-private external transmission.

Run structural checks after every applied batch and rotate whole-source content
reviews with durable per-offering/per-track status, source hashes, checks actually
performed and next cursor. Missing evidence/checks are incomplete/unverified, not
passes. Include full rosters, biography continuations, every ownership row/note,
lineage, lifecycle/price arithmetic, position attribution, restrictions and private
report isolation. Automated consistency is not evidence of correct interpretation.
Keep QA payloads in private ops storage; repository handoffs are sanitized. No
public issue or external alert containing private evidence is authorized.

## Incremental delivery order and acceptance

1. Finish confirmed security/correctness review items: concurrency-safe quotas,
   owner-without-role behavior, idempotency/stale-refresh cases and meaningful
   reviewer/customer authorization QA. Multi-role aggregation and proxy limits
   already have implementation receipts in the development ledger.
2. Continue oldest unfinished historical roster/owner batches alongside closing
   discovery-to-capture-to-reviewed-import orchestration. Persist retrieval
   cutoff and independent inventory reconciliation rather than only a schedule.
3. Add reviewed canonical profile links and cross-offering traversal. Test
   homonyms, aliases, non-CIK links and multiple reporting owners before merging
   identities or presenting combined histories.
4. Add evidence-linked timeline and position-level historical/scenario views
   incrementally, with deterministic dates/amounts and immutable version tests.
5. Validate real authenticated desktop/mobile journeys when an authorized session
   is available. Simulated sessions and SQL role tests must be labeled separately.

Before every commit check Refresh Prospect Ownership History is neither active
nor pending/queued; never cancel or bypass it. Hold the shared development lock
before mutation. Record prepared/applied/committed/deployed/verified separately.
No launch, billing, DNS, spending, access expansion or main merge is authorized.
