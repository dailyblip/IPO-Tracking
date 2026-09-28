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
   Explicitly enumerate named controllers in each footnote; missing people remain
   visible even when the surrounding note has already been reviewed.
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
- Reuse the applied source-backed organization/group attribution model. PicPay is
  the first verified organization-holder batch: reported holder, beneficiary
  entitlement and control authority remain separate in the grid/private snapshot.
  Full-cohort holder/controller coverage is still incomplete.
- Generalize holdings review with reconciled security/attribution contracts; then
  implement supported filing-price values and actual sale proceeds.
- Keep independent IPO census review advancing. Resolve every Monitor difference;
  do not label any month complete while census or cutoff checks remain open.

Current applied batch, tests and next exact files are in `development-log.md` and
`backfill-2026.md`.

## Dual-class rows, duplicate identities and entity managers — September 28 UTC

AGI extends the complete-table contract to a 17-column principal-shareholders
table with Class A/Class B quantities, proposed-sale columns and base/full-option
projected snapshots. Import the pre and base-post quantities separately. Preserve
the full-option alternative and proposed-sale cells in reviewed evidence rather
than treating them as simultaneous holdings or completed sales. Every selected
dash remains a null position.

The officers/directors aggregate and repeated Marciano Testa 5% row overlap named
rows and are audited without duplicate positions. AGI Partners and the Lumina and
Vinci funds remain organizations. Marciano Testa's filing-named control of AGI
Partners is not a copy of that entity's quantities into personal economics. The
footnotes also name Lumina and Vinci organization investment managers; until the
attribution model can represent organization-to-organization authority without
duplicating holdings, retain those links as unverified structured data with full
evidence and limitations.

AGI now has all 14 management biographies and 68 selected ownership positions.
Any-position coverage is 22 of 94 offerings, leaving 72 without records. The next
oldest priced no-position cursor is ARKO Petroleum. This does not establish
historical value, current ownership, liquidity, full-cohort ownership or an
independently complete IPO census.

## Up-C Class A/Class B alternatives and deemed ownership — September 28 UTC

SOLV extends the full-table contract to a post-Transactions Up-C table with Class
A and Class B quantities on pre-offering, base projected-after and full-option
columns. Import the pre/base-post snapshots separately. The full-option columns
are mutually exclusive alternatives and cannot be presented or summed as current
simultaneous holdings. Every selected dash stays visible as a null position.

American Securities' sponsor total remains on the reported group and SOLV Energy
Management Holdings LP remains an organization. Named people in the sponsor
control chain receive only the filing-supported control or reported-beneficial-
owner link, including its express disclaimer; the four group snapshots are never
copied into personal economics. Management Holdings' Class B total and the
one-for-one executive interests also remain separate rather than additive.
Redemption/exchange mechanics, current ownership, historical IPO-price
compatibility and liquidity require separate evidence.

All 19 management biographies, 68 selected positions and 20 attributions are now
present. Any-position coverage is 21 of 94 offerings, leaving 73 without records.
The next oldest priced no-position cursor is AGI Inc; this does not establish
full-cohort ownership, historical value, liquidity or an independently complete
IPO census.

## Proposed-sale tables and mixed conversion totals — September 28 UTC

Once Upon a Farm extends the complete-table contract to a seven-column principal-
and-selling-holder table. Preserve before and projected-after beneficial totals as
alternative snapshots and retain the proposed-sale column as reviewed evidence.
A proposed offered quantity is not a completed sale, realized proceeds or proof of
saleability. Filing dashes remain explicit null positions so named people do not
disappear.

The table's 29 non-overlapping subjects include people, organizations, reported
fund groups and eight anonymized holder buckets. The overlapping ten-person
management aggregate is not imported again. Cambridge and CAVU quantities stay on
their reported groups; Filipp Chebotarev and Brett Thomas receive control-authority
links only, never copied personal economics. Mixed issued shares, conversions,
warrants, trusts and options prevent automatic historical IPO-price values.
All ten management biographies and 58 selected positions are now present. Current
any-position coverage is 20 of 94 offerings, leaving 74 without records. The next
equal-date cursors are SOLV Energy and AGI Inc; this does not establish full-cohort
ownership, historical value, liquidity or an independently complete IPO census.

## Footnote markers, repeated fund rows and one-share discrepancies — September 28 UTC

AgomAb extends the complete-table contract to filings that place `*` in both the
quantity and percentage cells for less-than-one-percent holders. These rows remain
visible as explicit null positions; `*` is never parsed as zero or used to remove a
person. Zero-width EDGAR layout glyphs may be ignored for row-identity comparison,
but exact duplicate occurrence counts remain enforced.

Every repeated person/fund total is stored once on the reported holder and linked
to the named person with the filing-supported attribution type. The officers/
executives aggregate is not added to its overlapping subjects. When the filing's
reported Tim Knotnerus total differs by one share from its listed components, the
reported aggregate is retained with the discrepancy and no residual is invented.
AgomAb has all 11 management biographies, 26 selected positions and 44 attribution
links. Current any-position coverage is 19 of 94 offerings, leaving 75 without
records. Next cursor is Once Upon a Farm; this checkpoint does not establish full-
cohort ownership, historical value, liquidity or an independent complete IPO
census.

## Two stock classes, explicit dash rows and biography continuation — September 28 UTC

Forgent extends the full-table contract to an Up-C ownership table that reports
Class A and Class B positions across before, base projected-after and full-option
scenarios. Import the reviewed before and base-post snapshots separately. The
full-option columns are mutually exclusive alternatives and must not be added as
simultaneous holdings. Every named dash row remains a null position for each
selected class/basis so a person does not disappear and unknown is not displayed
as zero.

The one populated Neos holder group stays a group. Peter Jonna's named place at the
top of the control chain is a control-authority link, not a copy of group quantities
into personal economics. Incentive-unit values, excluded RSUs, disclaimers and
Opco/Class B distinctions prevent an automatic IPO-price value or liquidity result.

Whole-section reconciliation also detected an existing biography that ended one
block early. A roster count was not accepted as complete until the reviewed
continuation was applied and the fresh canonical excerpt matched both source blocks.
Forgent now has all 11 complete management biographies and 48 selected ownership
positions. Current any-position coverage is 18 of 94 offerings, leaving 76 without
records. Next cursor is AgomAb Therapeutics; this checkpoint does not establish
full-cohort ownership, historical value, liquidity or an independent complete IPO
census.

## Aggregate holder groups and voting-only shares — September 28 UTC

York demonstrates the full-table rule for an issuer whose ownership section mixes
named people, aggregate fund groups, restricted shares, corporate-conversion
figures and shares subject only to a director-election voting agreement. Every
reported table row is either represented or explicitly audited as overlapping. The
two aggregate groups remain groups; named upstream managers remain controller
links; voting-only shares excluded by the table are not silently added; the
officers/directors total is not counted on top of named people.

Current any-position coverage is 13 of 94 offerings, leaving 81 without records.
The next oldest no-position cursor is Veradermics. Reuse this exact-row/group/control
contract and retain incomplete components, restrictions and economics as unknown.

## One quantity with two percentages and conflicting dates — September 28 UTC

Veradermics adds a fail-closed contract for a table that reports one beneficial-
ownership quantity beside both before- and after-offering percentages. The source
also conflicts internally: the table introduction names September 30, 2025, while
its denominators and option window use December 31, 2025. A reviewed release may
store the quantity once as `position_basis = unspecified` with a null holdings date
only when the exact conflict and limitation are retained in evidence. It must not
clone the quantity into pre/post snapshots or select a date by assumption.

The complete Veradermics review accounts for all 11 management biographies, six
holder groups, seven direct named-person rows, eight named controllers and audited
overlaps/discrepancies. Current any-position coverage is 14 of 94 offerings,
leaving 80 without records. Next cursor is Bob's Discount Furniture. This extension
does not establish value, liquidity, personal economics or full-cohort completion.

## Reported beneficial owner without inferred control — September 28 UTC

Ethos extends the party model with `reported_beneficial_owner` for a named SEC table
row that repeats an organization's totals without establishing personal economic
ownership or control. It is distinct from beneficiary entitlement and control
authority. The organization remains the reported holder; the person remains
discoverable and linked; the quantity is stored once. Exact aliases and duplicate
rows require source-reviewed contracts, and every intentionally omitted aggregate
or repeated row is retained with a reason.

Ethos is the first full principal/selling-stockholder-table application of this
contract: 28 unique reported holder/group rows, 53 imported positions, 28
attribution records and four audited duplicate/aggregate rows not imported again.
Current any-position coverage is 12 of 94 offerings, leaving 82 without records.
This is not a whole-cohort or month-completeness claim. Next cursor is York; reuse
the same full-table accounting rather than importing only easily parsed people.

## Base post-offering versus full-option alternatives — September 28 UTC

Bob's Discount Furniture extends the full-table rule to a filing that reports
pre-offering quantities, shares offered, projected post-offering quantities without
the underwriter option and a separate projected column with the option exercised.
The selected base post-offering column and the full-option column are mutually
exclusive scenarios: store the reviewed base snapshot once and explicitly hold the
alternative rather than summing or presenting both as simultaneous positions.

Every unique reported ownership subject remains represented, including null records
for filing dashes. The overlapping officers/directors aggregate is audited without
double counting. A footnote that names several partners but requires joint decisions
and expressly denies individual direction does not establish individual control
authority, personal economic ownership or a personal share quantity. The holder
group remains the reported owner and the named management biographies remain
discoverable independently of whether they have a disclosed quantity.

The Bob's review accounts for all 19 management biographies, 16 unique ownership
subjects, 32 selected positions and all 12 footnotes. Current any-position coverage
is 15 of 94 offerings, leaving 79 without records. Next cursor is Eikon
Therapeutics. This checkpoint does not establish current value, liquidity, full-
cohort ownership completion or an independent complete IPO census.

## One quantity with pre/post percentages and attributed duplicate row — September 28 UTC

Eikon Therapeutics extends the full-table contract to a source that reports one
December 31, 2025 quantity beside both pre- and projected post-offering percentages.
The quantity is a pre-offering beneficial total and is stored once. A projected
post-offering quantity must not be reverse-calculated from its percentage.

The repeated Joshua Wolfe row exactly matches the Lux-affiliated holder-group total.
Keep the group quantity once and link Wolfe as the SEC-reported beneficial owner
with shared voting/dispositive authority and the source disclaimer; do not turn the
fund amount into his personal economics. Apply the same separation to other fund
controllers and Mahler's named ultimate beneficial owner. Leon Chen remains visible
with a null direct row while the source expressly says he has no voting or
dispositive power over the Column Group securities.

The complete review accounts for all ten management biographies, 14 table rows,
15 footnotes, 13 selected positions, ten attributions and both held overlaps.
Current any-position coverage is 16 of 94 offerings, leaving 78 without records.
Next cursor is SpyGlass Pharma. This does not establish current value, vesting,
liquidity, personal economics, full-cohort ownership completion or a complete IPO
census.

## Repeated director rows and named fund controllers — September 28 UTC

SpyGlass extends the one-quantity contract to a table with six reported holder
organizations/groups, direct named-person rows, repeated director rows and an
overlapping officers/directors aggregate. The repeated Ali Behbahani/NEA, Kirk
Nielsen/Vensana and Geoff Pardo/Gilde amounts stay on their reported holders and are
linked to the people as reported beneficial owners; they are not copied into a
second personal position. Named footnote controllers remain searchable and linked
without invented biographies or personal economics.

The complete review accounts for all 14 management biographies, every unique table
subject, all linked footnotes, 14 selected pre-offering positions, 18 attributions
and the held aggregate/repeated rows. Filing dashes remain null. Current any-position
coverage is 17 of 94 offerings, leaving 77 without records. Next cursor is Forgent
Power Solutions, then Once Upon a Farm and AgomAb. This is a source-reviewed batch,
not a complete ownership cohort, independent SEC census, value or liquidity claim.

## Mixed fund, trust, conversion and option totals — September 28 UTC

Generate Biomedicines extends the complete-table contract to a two-snapshot table
whose reported totals combine issued common stock, preferred-conversion shares,
options exercisable within 60 days, trusts, funds and attributed authority. Store
the filing's January 15, 2026 before-offering and projected after-offering totals
as alternative snapshots; never sum them or treat either total as a homogeneous
issued-common position.

The Flagship quantity remains on the reported holder group. Dr. Noubar Afeyan's
source-backed voting/investment control link carries the direct-ownership and
beneficial-ownership disclaimers and does not establish personal economic ownership.
His separate person row explicitly incorporates the Flagship shares plus options,
so those rows overlap and must not be summed. The same evidence-first distinction
applies to trusts and Stéphane Bancel's OCHA control statement. The overlapping
15-person aggregate is audited without duplicate import.

The complete review accounts for all 15 management biographies, twelve unique
ownership subjects, 24 selected positions and all thirteen footnotes. Any-position
coverage is now 24 of 94 offerings, leaving 70 without records. No current quote,
historical IPO-price value, completed sale, liquidity or full-cohort/census claim
is established by this batch.

## Repeatable checks now available

Run `scripts/audit_staging_data.sql` read-only after each applied batch and retain
its private per-offering/source-version matrix. It checks identity, lifecycle and
source alignment only. Join separately reviewed section receipts by exact offering
and source hash; its unverified fields must not be promoted by row counts. Run
`audit_people_coverage.py` against the fresh inventory and retained artifact roots
for additional unreviewed leads. Missing local files must be restored, not treated
as zero gaps. These tools do not yet constitute the complete scheduled ingestion
and rotating source-content audit pipeline; durable cursor/orchestration remains
required alongside independent SEC census review.

## Quantity import independent of liquidity review — September 28 UTC

`build_disclosed_holdings.py` accepts explicitly reviewed whole ownership-table
rows against exact raw HTML cell boundaries and normalized-source hashes. This
allows reported beneficial totals to appear before full instrument/restriction
decomposition. Aggregate totals remain labeled, pre/post alternatives separate,
null distinct from zero; no inferred components/values or completed-sale proceeds.
All same-source overlaps fail closed pending explicit review. Missing quantities
never suppress people, and complete biographies do not imply ownership completeness.

Current quantity coverage is eight of 94 offerings with any records, not eight
complete tables. Private 94-company/source-version queue plus per-track structural
audit is checkpointed with the first batch. Next no-position cursor: BitGo. The
remaining 86 and entity/group/controller gaps remain development work, requiring
no owner-supplied company list. See development-log for source-backed counts.

The next batch extended the contract to exact multiple-series rows. BitGo and
EquipmentShare Class A/Class B totals now remain distinct on each before/projected
after basis; alternate offering scenarios and overlapping co-founder/group totals
cannot be summed. Current any-position coverage is 10 of 94 offerings, with 84
still unverified. The next preserved source/version cursor is PicPay.
