# Comprehensive researcher pivot

Owner approved continuing this pivot September 27, 2026. IPO Roll must exceed
Research Monitor in useful, source-backed coverage and quick reference. Preserve
the existing engine, Research Monitor, legacy feed/Pages and production schedules.
Commercial work stays on `ipo-roll/foundation` and authorized private staging.

## Completion criteria

Track these independently for each exact issuer/registration/current filing:

| Track | Evidence required before marking complete |
| --- | --- |
| Offering inventory | Independent SEC census reconciliation, including pre-2026 registrations priced in 2026; exact-filing inclusion/exclusion/hold dispositions and freshness cutoff |
| Management roster | Every row in the source management table accounted for, including nominees and departure qualifiers |
| Biographies | Every available complete person-specific biography attached and searchable; continuations across page breaks preserved; missing biography explicitly recorded |
| Ownership roster | Every individual, organization and aggregate group row represented or explicitly held; do not manufacture biographies or collapse funds into people |
| Footnotes | Every note accounted for, including named controllers, attribution disclaimers, overlapping positions and conversion/award conditions |
| Quantities | Security classes, actual/projected basis, holdings dates and components reconcile; overlapping totals excluded from sums |
| Values | Compatible reviewed historical IPO-price position basis, or actual named-holder completed-sale evidence; otherwise unavailable |
| Liquidity | Person-specific conditional restrictions with evidence; unknown retained; lock-up end alone is insufficient |

An imported company, discovered name, captured filing, passing parser test or
management-complete result does not satisfy the other tracks. The legacy feed is
an inventory to reconcile, not an independent completeness denominator.

## Evidence and presentation

The owner's later instruction to include **every available biography** requires
institution-neutral source handling. Preserve factual education/employment text,
including Stanford when it actually appears in a reviewed SEC biography. This
does not restore Stanford branding, navigation, counters, highlighting, special
affiliation search or legacy institutional enrichment. Generic biography search
treats all source-supported institutions the same. Do not censor or silently
drop a person because of a school mention.

Keep the compact researcher layout: management/holder accordion, readable
stock-class grid, retained stake and documented sale proceeds side by side, and
expandable evidence. Private Liquidity Analysis remains on-demand, static and
timestamped with explicit versioned refresh. Data imports never rewrite reports.
Paid quotes and new AI providers remain deferred, with no new spending authorized.

## Reconciliation workflow

1. Acquire the shared development lock; reconcile current branch and staging.
2. Reuse retained Monitor/SEC artifacts and verify source hashes/registration.
3. Select complete management/table/biography sections and explicitly account for
   every normalized source block. Confirm identity aliases; never merge by name alone.
4. Apply missing source-reviewed biographies/roles through the replay-safe
   supplement importer; import quantities only through separately reviewed contracts.
5. Run `reconcile_people_roster.py` against a fresh timestamped canonical snapshot.
   It requires matching offering/source, rejects gaps/overlap, compares full
   biography text, and retains entity/group/footnote work as pending.
6. Archive private reviews/results in staging `ops.sec_artifacts`; approved import
   manifests remain in `ops.pilot_manifests`. Never put private payloads in Git.
7. Test reviewer RPC/source/search, customer/anonymous denial, exact replay and
   unchanged private report fingerprints. Live authenticated browser QA is separate.
8. Check the ownership-history workflow guard immediately before each commit.

The new reconciler is a coverage check for **explicitly reviewed sections**. It
does not autonomously prove the section boundaries are exhaustive, classify every
filing, interpret footnotes, approve financial facts or declare a company complete.

## Next priorities

- Finish the January cohort's management/ownership reconciliation, then continue
  oldest-first through the remaining cohort; restore missing retained artifacts.
- Add source-backed organization/group and footnote-controller representation
  without requiring a biography, including name-only discovery for reviewed
  people without biographies. Preserve source attribution and account access.
- Generalize holdings review with reconciled security/attribution contracts; then
  implement supported filing-price values and actual sale proceeds.
- Keep independent IPO census review advancing. Resolve every Monitor difference;
  do not label any month complete while census or cutoff checks remain open.

Current applied batch, tests and next exact files are in `development-log.md` and
`backfill-2026.md`.
