# IPO Roll completion gates

Checkpoint: September 28, 2026 (Pacific). This checklist defines observable
completion for the authorized commercial staging product. It is not a launch
approval. Applied-batch receipts and private recovery hashes belong in
`development-log.md`; monthly evidence coverage belongs in `backfill-2026.md`.

## Current baseline

Staging has **94 offerings, 556 people, 463 biography records, 795 positions,
193 attribution links and 34 components**. Thirty offerings have positions;
**64 have none**. Position counts include separate classes and before/projected-
after snapshots; they are not distinct owners or additive holdings. There are
zero quotes and zero reviewed historical-value claims. The thirteen existing
account-private reports were preserved unchanged.

Independent census reconciliation and full-cohort source-content review remain
incomplete. A passing structural audit means its specific consistency checks
passed. It does not establish complete rosters, correct interpretation, complete
footnotes, source freshness, liquidity or an exhaustive IPO census.

## Acceptance checklist

| Gate | Implemented or verified now | Required to close |
| --- | --- | --- |
| January 1–present inventory | Source-reviewed canonical cohort and private SEC candidate inventory exist. | Reconcile every relevant issuer/registration/accession through a stated cutoff, including older registrations priced in 2026. Record source-backed exclusions and unresolved holds; finish monthly coverage without treating the legacy feed as the denominator. |
| Continuous discovery and refresh | Date-only live discovery run `36516858295` succeeded at commit prefix `3e378`: two daily indexes, 111 filing candidates, comprising 4 captured/review-pending, 20 capture-pending and 87 held. No canonical offering was added. Queue evidence is durable in private `ops.sec_artifacts`. | Automatically restore the prior checkpoint, run a durable controller/scheduler, retry missing intervals/captures and reconcile source-reviewed updates to existing registrations. The September 28 cutoff remains conservatively incomplete. A successful one-off discovery run is not an operating end-to-end ingestion service. |
| Full source depth | Reviewed batches preserve class/basis distinctions, entity attribution, biographies and explicit unknown quantities. | For each exact current source, account for the entire management table, all biography continuations, all ownership rows and every linked footnote/controller. Store separate per-track pass/fail/unverified status and a rotating review cursor. Complete the 64 offerings currently without positions and the remaining depth review on the other 30. |
| Safe holder presentation | Natural holders with qualifying ownership evidence can appear without a separate role. Neutral footnote-named relationships preserve people without implying issuer ownership/control. Component rows retain reported class and holder attribution. | Continue current-source and no-duplicate validation as new batches arrive; resolve held identities and overlapping quantities with evidence. No person may disappear because a biography or quantity is missing. |
| Filing-based historical value | Reviewed-compatible-value contract is implemented, applied, tested and verified on Render at commit prefix `fae7`; only new/explicitly refreshed reports freeze claims. | Import genuinely compatible source-reviewed claims and verify actual report output. Alamar's pro-forma BEFORE rows are held and produce zero estimates. Security/class, quantity, conversion basis, final price and all relevant dates must reconcile. No aggregate beneficial-total multiplication. |
| Holder-sale proceeds and liquidity | Private reports preserve sourced footnotes, conditional timelines and liquid/future/illiquid/unknown categories. | Finish holder-specific restriction, vesting, exercise, conversion, resale and overlap review. Completed-sale proceeds require evidence of actual named-holder sales and applicable prices; proposed sales and issuer proceeds do not qualify. A lock-up boundary alone never establishes saleability. |
| Private report integrity | Isolation SQL passed; all thirteen pre-existing reports remain unchanged. Reopen and explicit versioned refresh are implemented. | Preserve account ownership, guessed-ID/read/write denial and immutable older snapshots through every release. Complete outstanding genuinely concurrent-session quota verification and live cross-account browser journeys. Simulated fixtures are separate evidence. |
| Profile and user journeys | Profile/scenario interface exists; simulated-fixture browser checks passed. | Complete authorized live reviewer desktop/mobile and cross-account browser QA. Finish reviewed cross-offering identity links and traversal, including aliases/homonyms, before presenting combined histories. An available name match is not a verified identity link. |

“Complete” requires receipts for these gates. Missing evidence or an unavailable
check stays incomplete/unverified. Keep unresolved interpretation visible and
withhold unsupported quantities, values or classifications. Never turn an
unknown into zero or a structural pass into an accuracy claim.

## Next executable work

1. Review compatible valuation evidence without forcing Alamar's pro-forma BEFORE
   quantities into actual holdings; retain explicit unknowns until the basis is supported.
2. Continue the source-depth cursor with **AEVEX**, offering
   `c1bde1e8-34a7-5ab6-ae78-371a3956d10a`, accession
   `0001193125-26-162601`; then **Elmet**, accession
   `0001213900-26-047144`. Reconcile source versions before replay or mutation.
3. Close the discovery checkpoint-restore/controller/scheduler gap alongside
   historical review, including source-reviewed existing-registration refresh.
4. Run structural and targeted evidence/privacy checks for each applied batch;
   checkpoint the next whole-source audit cursor privately.

## Authorization and owner dependencies

No new owner decision, paid quote feed or AI provider is needed for continued
staging development. Current market value remains unavailable without a later
approved licensed feed; filing-based work does not depend on purchasing one.
Live reviewer testing requires an authorized signed-in session when available;
credentials belong in the proper service, never in chat.

Commercial source rights, production Auth/payments/billing, unresolved launch
security configuration and production release remain separate owner gates.
Production launch, DNS changes, charges and merging into main are not authorized.
Preserve Research Monitor, production ingestion/schedules and legacy Pages/JSON.
Preserve institution-neutral source biographies and the approved commercial UI
without institution-specific branding, highlighting or special searches.

Hold the shared development lock before mutation. Before every commit verify
that Refresh Prospect Ownership History is neither active nor pending/queued;
never cancel it or bypass the guard. A bounded batch closes a checkpoint, not
the product or the recurring development task.
