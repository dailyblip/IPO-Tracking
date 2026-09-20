"""Suppress person-level economic derivatives that public SEC evidence cannot attribute.

The Research Monitor may preserve an SEC-reported beneficial-ownership share count
while declining to turn that count into personal paper value, liquidity, or realized
cash when the filing explicitly says the shares are held by other entities and the
reporting person disclaims beneficial ownership except for an undisclosed pecuniary
interest. The same fail-closed rule applies when an SEC beneficial-ownership table
reports one household/group position under multiple people but does not establish
that the full position is economically attributable to each person individually. It
also rejects holder-level IPO sale economics that contradict the same holder's
disclosed pre-IPO position. Public-offering price multiplied by shares sold is not
published as holder-level cash realized because selling stockholders can bear
underwriting discounts and commissions; without explicit holder-level proceeds
provenance, that derived amount is not authoritative realized cash. Incorrect
personal economics are worse than a blank derived value.

The issuer-specific registry is intentionally narrow. Each entry must be tied to a
specific issuer, IPO accession, holder identity, disclosed share count, and primary
SEC evidence. A separate lifecycle registry is reserved for SEC-supported aggregate
fund positions whose exact post-offering share count may carry unchanged into a
later 424B4 accession; those entries still require the same issuer, holder identity,
and exact disclosed share count before suppression applies.
"""

from __future__ import annotations

import math

from ownership_parser import canonical_holder_name


# SEC Form 3 filed 2026-06-11 by Antonio J. Gracias for SpaceX states that the
# 503,414,530 reported shares are held of record by 30 Valor entities. It says he
# may be deemed to beneficially own those shares because of his positions with the
# entities/general partners and that he disclaims beneficial ownership except to
# the extent of his pecuniary interest. The filing does not quantify that personal
# pecuniary interest, so the Monitor must not publish the full position's value or
# liquidity as Antonio Gracias's personal economics.
# https://www.sec.gov/Archives/edgar/data/1495158/000162828026042633/xslF345X03/wk-form3_1781226087.xml
#
# BlossomHill Therapeutics' 2026-08-07 424B4 reports 2,089,279 shares for director
# Carl L. Gordon, Ph.D., CFA solely through OrbiMed Private Investments VIII, LP.
# Footnote (3) says the shares are held by OPI VIII and that each member of the
# OrbiMed Advisors management committee, including Dr. Gordon, disclaims beneficial
# ownership. The SEC table may retain the reported beneficial-ownership count, but
# the Monitor must not present the fund position's value as Dr. Gordon's economics.
# The same 424B4 reports a single 3,973,138-share household/affiliate position for
# married co-founders J. Jean Cui and Y. Peter Li and repeats that aggregate count
# under each person. Footnote (1) says it combines Dr. Cui's direct shares, Dr. Li's
# direct shares, a family trust over which both have voting/dispositive power, and
# RongShan shares managed by Dr. Li; it also says each spouse may be deemed to own
# the other's securities indirectly. The filing supports the SEC beneficial-owner
# count for each person, but not treating the same full household position as each
# person's separate paper value or liquidity. Preserve the counts and suppress the
# duplicated person-level economics.
# https://www.sec.gov/Archives/edgar/data/1839970/000119312526340215/d98958d424b4.htm
#
# BlossomHill's issuer-specific 2026-08-06 Form 3 for Bihua Chen reports the same
# Cormorant fund position through Cormorant Asset Management and its managed funds.
# It identifies Ms. Chen as manager of Cormorant and the funds' general partners,
# and every reporting person disclaims beneficial ownership except to the extent of
# its or her pecuniary interest. That personal interest is not quantified. Preserve
# the SEC-reported aggregate beneficial-ownership count, but do not present the full
# Cormorant position's value or liquidity as Ms. Chen's personal economics.
# https://www.sec.gov/Archives/edgar/data/1839970/000123191926000839/xslF345X06/form3-08072026_120822.xml
#
# Latigo Biotherapeutics' 2026-08-07 424B4 reports the Westlake and Foresite fund
# positions under directors Beth Seidenberg and James B. Tananbaum. Their issuer-
# specific Forms 3 confirm that the securities are held of record by the underlying
# venture funds and that each director disclaims beneficial ownership except to the
# extent of an unquantified pecuniary interest. Preserve the SEC-reported beneficial-
# ownership counts, but do not present the full venture-fund positions as personal
# paper value or liquidity.
# https://www.sec.gov/Archives/edgar/data/2056611/000110465926092240/xslF345X03/tm2622411-1_3seq1.xml
# https://www.sec.gov/Archives/edgar/data/2056611/000158175426000003/xslF345X03/form3-08072026_120818.xml
#
# Scribe Therapeutics' 2026-07-23 424B4 reports 697,650 shares under director
# Behzad Aghazadeh and 348,825 shares under director Carl L. Gordon. The accompanying
# footnotes state that Dr. Aghazadeh's shares are held by Avoro funds and that he
# disclaims beneficial ownership except to the extent of a pecuniary interest, if
# any; Dr. Gordon's shares are held by OrbiMed Private Investments VIII, L.P., and
# every member of the OrbiMed Advisors management committee, including Dr. Gordon,
# disclaims beneficial ownership. Neither footnote quantifies personal economics.
# Preserve the SEC-reported table counts, but suppress full fund-position value and
# liquidity from the person records.
# https://www.sec.gov/Archives/edgar/data/1853921/000119312526316503/d21355d424b4.htm
#
# Yesway's 2026-04-21 Form 4 and issuer-specific Form 3 for Thomas N. Trkla identify
# large Brookwood-held positions as indirect. The Form 3 states that Mr. Trkla has a
# controlling interest in Brookwood Financial Partners, LLC and therefore may be
# deemed to share beneficial ownership of securities held of record by Brookwood;
# other large positions are likewise reported through Brookwood aggregator entities.
# The Monitor's 46,225,020-share Trkla row is an aggregate beneficial-ownership fact,
# but the filings do not establish that the full Brookwood-controlled position is his
# personal economic interest. Preserve the reported share count while suppressing the
# full aggregate position's derived personal value/liquidity.
# https://www.sec.gov/Archives/edgar/data/1859836/000110465926047051/xslF345X03/tm2612184-10_3seq1.xml
# https://www.sec.gov/Archives/edgar/data/1859836/000110465926050375/xslF345X03/tm2612184-12_4seq1.xml
#
# Electra Therapeutics' final 2026-09-17 424B4 reports 5,551,837 shares under Carl
# L. Gordon and 6,347,539 shares under Beth Seidenberg. The related footnotes continue
# to attribute those positions to OrbiMed-affiliated and Westlake/Bio Partners fund
# entities rather than establishing the entire positions as the directors' personal
# economics. These final counts differ from the preceding S-1/A counts, so keep this
# release-blocking suppression accession-specific and exact-count constrained.
# https://www.sec.gov/Archives/edgar/data/2088082/000119312526395670/d23848d424b4.htm
_UNSUPPORTED_PERSON_ECONOMICS = {
    (
        "0001181412",
        "0001628280-26-042639",
        canonical_holder_name("Antonio J. Gracias"),
    ): 503_414_530,
    (
        "0001839970",
        "0001193125-26-340215",
        canonical_holder_name("Carl L. Gordon, Ph.D., CFA"),
    ): 2_089_279,
    (
        "0001839970",
        "0001193125-26-340215",
        canonical_holder_name("J. Jean Cui, Ph.D."),
    ): 3_973_138,
    (
        "0001839970",
        "0001193125-26-340215",
        canonical_holder_name("Y. Peter Li, Ph.D., MBA"),
    ): 3_973_138,
    (
        "0001839970",
        "0001193125-26-340215",
        canonical_holder_name("Bihua Chen, MBA"),
    ): 3_301_534,
    (
        "0002056611",
        "0001193125-26-340329",
        canonical_holder_name("Beth Seidenberg, M.D."),
    ): 13_199_669,
    (
        "0002056611",
        "0001193125-26-340329",
        canonical_holder_name("James B. Tananbaum, M.D."),
    ): 9_041_328,
    (
        "0001853921",
        "0001193125-26-316503",
        canonical_holder_name("Behzad Aghazadeh, Ph.D."),
    ): 697_650,
    (
        "0001853921",
        "0001193125-26-316503",
        canonical_holder_name("Carl L. Gordon, Ph.D., CFA"),
    ): 348_825,
    (
        "0001859836",
        "0001104659-26-047210",
        canonical_holder_name("Thomas N. Trkla"),
    ): 46_225_020,
    (
        "0002088082",
        "0001193125-26-395670",
        canonical_holder_name("Carl L. Gordon, Ph.D., C.F.A."),
    ): 5_551_837,
    (
        "0002088082",
        "0001193125-26-395670",
        canonical_holder_name("Beth Seidenberg, M.D."),
    ): 6_347_539,
}

# Electra Therapeutics' 2026-09-14 S-1/A (File No. 333-298617) reports identical
# aggregate positions under the affiliated fund rows and directors Carl L. Gordon
# and Beth Seidenberg. Footnote (13) maps Dr. Gordon's entire 5,548,593-share
# post-offering count to the OrbiMed fund position in footnote (2); that footnote
# states that Dr. Gordon is one of the OrbiMed Advisors management-committee members
# and expressly disclaims beneficial ownership of the underlying fund shares.
# Footnote (14) maps Dr. Seidenberg's entire 6,341,824-share post-offering count to
# the Westlake fund position in footnote (3). Footnote (3) says the securities are
# held by Westlake Fund I / Fund II and that Dr. Seidenberg may be deemed to have
# voting and dispositive power as the sole managing director of the funds' general
# partners; it does not establish that the entire fund position is her personal
# economic interest. Preserve the SEC beneficial-ownership counts while suppressing
# personal paper value/liquidity. These exact post-offering counts are allowed to
# survive an S-1/A -> 424B4 accession change only while issuer, holder, and share
# count all remain unchanged.
# https://www.sec.gov/Archives/edgar/data/2088082/000119312526389755/d61940ds1a.htm
_UNSUPPORTED_PERSON_ECONOMICS_LIFECYCLE = {
    (
        "0002088082",
        canonical_holder_name("Carl L. Gordon, Ph.D., C.F.A."),
    ): 5_548_593,
    (
        "0002088082",
        canonical_holder_name("Beth Seidenberg, M.D."),
    ): 6_341_824,
}

_DERIVED_ECONOMIC_FIELDS = (
    "cash_value",
    "ipo_value",
    "liquid_shares",
    "liquid_value",
    "locked_shares",
    "locked_value",
    "cash_realized_ipo",
    "valuation_as_of",
)


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _money(value):
    value = _number(value)
    if value is None or value <= 0:
        return None
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def suppress_unsupported_person_economics(filing: dict) -> dict:
    """Return a copy with unsupported person-level economic derivatives cleared.

    The SEC-reported beneficial-owner share quantity remains a public fact even when
    economic attribution is unsupported. Separately, when the same holder has an
    authoritative pre-IPO share count, a claimed IPO sale cannot exceed that position;
    impossible sale/realized-cash fields fail closed while the underlying ownership
    facts remain intact. A public offering price is the buyer-facing price and is not
    treated as holder-level cash realized without explicit proceeds provenance.

    Issuer-specific accession entries apply only while the exact disclosed share
    count still matches. The lifecycle registry is likewise exact-count constrained,
    but may persist across an accession change for the same issuer/holder when SEC
    evidence already establishes that the reported position is an aggregate fund
    position rather than supported personal economics.
    """
    if not isinstance(filing, dict):
        return filing

    cik = str(filing.get("cik") or "").strip()
    accession = str(filing.get("accession_no") or "").strip()
    people = filing.get("people")
    if not isinstance(people, list):
        return dict(filing)

    normalized = dict(filing)
    normalized_people = []
    changed = False
    position_value_suppressed = False

    for person in people:
        if not isinstance(person, dict):
            normalized_people.append(person)
            continue

        normalized_person = dict(person)

        # The pipeline currently derives this field from shares sold times the
        # public offering price. That is a gross buyer-price amount, not supported
        # holder-level realized cash: selling stockholders can pay underwriting
        # discounts/commissions and the filing may not allocate net proceeds by
        # holder. Preserve the explicit sale share count, but fail closed on cash.
        if normalized_person.get("cash_realized_ipo") not in (None, ""):
            normalized_person["cash_realized_ipo"] = None
            changed = True

        shares_before_ipo = _number(person.get("shares_before_ipo"))
        shares_sold_ipo = _number(person.get("shares_sold_ipo"))
        if (
            shares_before_ipo is not None
            and shares_before_ipo >= 0
            and shares_sold_ipo is not None
            and shares_sold_ipo > shares_before_ipo
        ):
            for field in ("shares_sold_ipo", "cash_realized_ipo"):
                if normalized_person.get(field) not in (None, ""):
                    normalized_person[field] = None
                    changed = True

        holder_key = canonical_holder_name(person.get("name"))
        key = (cik, accession, holder_key)
        expected_shares = _UNSUPPORTED_PERSON_ECONOMICS.get(key)
        if expected_shares is None:
            expected_shares = _UNSUPPORTED_PERSON_ECONOMICS_LIFECYCLE.get((cik, holder_key))
        observed_shares = _number(person.get("shares"))

        if expected_shares is not None and observed_shares == float(expected_shares):
            for field in _DERIVED_ECONOMIC_FIELDS:
                if normalized_person.get(field) not in (None, ""):
                    normalized_person[field] = None
                    changed = True
                    position_value_suppressed = True

        normalized_people.append(normalized_person)

    if not changed:
        return normalized

    normalized["people"] = normalized_people

    # Keep the filing-level largest-holding signal synchronized only when a holder's
    # paper-value field was suppressed. Sale-only repairs do not alter current values.
    if position_value_suppressed:
        signals = filing.get("signals")
        if isinstance(signals, list):
            prefix = "Largest named holding currently valued at approximately "
            remaining_values = [
                _number(person.get("cash_value"))
                for person in normalized_people
                if isinstance(person, dict)
            ]
            remaining_values = [value for value in remaining_values if value is not None and value > 0]
            replacement = f"{prefix}{_money(max(remaining_values))}" if remaining_values else None
            updated_signals = []
            replaced = False
            for signal in signals:
                if isinstance(signal, str) and signal.startswith(prefix):
                    if replacement and not replaced:
                        updated_signals.append(replacement)
                        replaced = True
                    continue
                updated_signals.append(signal)
            normalized["signals"] = updated_signals

    return normalized
