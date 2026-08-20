"""
qc_review.py

Quality-control layer that runs after parsing/grading and before the
Sheets write. Two kinds of checks:

A. Deterministic sanity checks (no LLM needed): completeness, numeric
   plausibility, ticker resolution, lock-up date sanity, and
   comparison against the previous run's values for the same holder.

B. An LLM-based consistency check: does the Stanford grade's
   justification actually match what the source evidence (bio text or
   search snippets) showed? This is an independent second pass, not a
   re-derivation of the grade itself.

Each row dict gets two keys added: "QC Status" ("Verified" or "Needs
Review") and "QC Notes" (semicolon-joined list of specific issues).

Requires ANTHROPIC_API_KEY (same key used by stanford_grader.py) for
the LLM consistency check.
"""

import os
import json
from datetime import datetime
import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"

MIN_PLAUSIBLE_PRICE = 1.0
MAX_PLAUSIBLE_PRICE = 500.0
MIN_LOCKUP_DAYS = 30
MAX_LOCKUP_DAYS = 365
MATERIAL_CHANGE_THRESHOLD_PCT = 25.0  # flag if shares shift >25% run to run


def _to_float(value):
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except (ValueError, TypeError):
        return None


def _to_int(value):
    try:
        return int(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None


def check_completeness(row: dict) -> list:
    required_fields = ["Company Name", "Ticker", "Actual Price", "Holder Name", "Shares"]
    return [f"Missing {field}" for field in required_fields if not str(row.get(field, "")).strip()]


def check_numeric_plausibility(row: dict) -> list:
    issues = []

    actual_price = _to_float(row.get("Actual Price"))
    if actual_price is not None and not (MIN_PLAUSIBLE_PRICE <= actual_price <= MAX_PLAUSIBLE_PRICE):
        issues.append(f"Offering price ${actual_price} outside plausible range")

    current_price = _to_float(row.get("Current Price"))
    shares = _to_int(row.get("Shares"))
    cash_value = _to_float(row.get("Cash Value"))

    if current_price is not None and shares is not None and cash_value is not None:
        expected = current_price * shares
        if expected > 0:
            diff_pct = abs(expected - cash_value) / expected * 100
            if diff_pct > 1.0:  # allow small rounding drift
                issues.append(
                    f"Cash value ${cash_value:,.0f} doesn't match shares x current price (${expected:,.0f})"
                )

    return issues


def check_prospect_integrity(row: dict) -> list:
    """Cross-field checks for researcher-facing ownership/liquidity consistency."""
    issues = []
    price = _to_float(row.get("Actual Price"))
    current = _to_float(row.get("Current Price"))
    before = _to_int(row.get("Shares Before IPO"))
    sold = _to_int(row.get("Shares Sold in IPO"))
    after = _to_int(row.get("Shares After IPO"))
    shares = _to_int(row.get("Shares"))
    realized = _to_float(row.get("Cash Realized IPO"))
    cash_value = _to_float(row.get("Cash Value"))
    amount = _to_float(row.get("Amount Raised"))
    offering_shares = _to_int(row.get("IPO Size (Shares)"))

    if price is None and str(row.get("Date of Pricing") or "").strip():
        issues.append("Priced filing is missing final IPO price")
    if amount is None and price is not None and offering_shares is not None:
        issues.append("Offering value missing despite known IPO shares and final price")
    if before is not None and sold is not None:
        expected_after = before - sold
        if expected_after < 0:
            issues.append("Shares sold exceed shares held before IPO")
        elif after is None:
            issues.append("Post-IPO shares missing despite known before/sold values")
        elif after != expected_after:
            issues.append(f"Post-IPO shares do not reconcile: {before:,} - {sold:,} != {after:,}")
    if sold is not None and price is not None:
        expected_realized = sold * price
        if realized is None:
            issues.append("IPO cash proceeds missing despite known shares sold and final price")
        elif expected_realized and abs(expected_realized-realized)/expected_realized > 0.01:
            issues.append("IPO cash proceeds do not match shares sold x final price")
    if current is not None and (after is not None or shares is not None):
        held = after if after is not None else shares
        expected_value = held * current
        if cash_value is None:
            issues.append("Current holding value missing despite known shares and current price")
        elif expected_value and abs(expected_value-cash_value)/expected_value > 0.01:
            issues.append("Current holding value does not match post-IPO shares x current price")
    if row.get("Stanford Affiliation Confirmed") and not row.get("Stanford Justification"):
        issues.append("Stanford affiliation confirmed without supporting source/justification")
    return issues



def check_ticker_resolved(row: dict) -> list:
    if row.get("Current Price") in (None, "", "None"):
        return ["Current price could not be resolved for this ticker"]
    return []


def check_lockup_date(row: dict, ipo_date: str = None) -> list:
    issues = []
    expiry_str = row.get("Lock-Up Expiry")
    if not expiry_str or expiry_str in ("", "None"):
        return issues  # absence isn't necessarily an error

    try:
        expiry_date = datetime.fromisoformat(str(expiry_str)[:10])
    except ValueError:
        return [f"Lock-up expiry '{expiry_str}' is not a parseable date"]

    if ipo_date:
        try:
            ipo_dt = datetime.fromisoformat(str(ipo_date)[:10])
            days_diff = (expiry_date - ipo_dt).days
            if not (MIN_LOCKUP_DAYS <= days_diff <= MAX_LOCKUP_DAYS):
                issues.append(
                    f"Lock-up duration ({days_diff} days) outside plausible "
                    f"{MIN_LOCKUP_DAYS}-{MAX_LOCKUP_DAYS} day range"
                )
        except ValueError:
            pass

    return issues


def check_against_previous(row: dict, previous_row: dict) -> list:
    """
    Compare against the same holder's row from the prior run, if any.
    Flags material shifts as worth a human glance - prices moving is
    normal, but a sudden share-count change usually signals a parsing
    difference between runs rather than a real event.
    """
    if not previous_row:
        return []

    prev_shares = _to_int(previous_row.get("Shares"))
    curr_shares = _to_int(row.get("Shares"))
    if prev_shares and curr_shares and prev_shares != curr_shares:
        diff_pct = abs(curr_shares - prev_shares) / prev_shares * 100
        if diff_pct > MATERIAL_CHANGE_THRESHOLD_PCT:
            return [
                f"Share count changed {diff_pct:.0f}% since last run "
                f"({prev_shares:,} -> {curr_shares:,})"
            ]
    return []


def run_deterministic_checks(row: dict, previous_row: dict = None, ipo_date: str = None) -> list:
    issues = []
    issues.extend(check_completeness(row))
    issues.extend(check_numeric_plausibility(row))
    issues.extend(check_prospect_integrity(row))
    issues.extend(check_ticker_resolved(row))
    issues.extend(check_lockup_date(row, ipo_date))
    issues.extend(check_against_previous(row, previous_row))
    return issues


def llm_consistency_check(row: dict, source_excerpt: str) -> list:
    """
    Independent second pass over the Stanford grade: does the
    justification actually reflect the source evidence, and does the
    grade match the strength of that evidence? Catches overstated
    confidence and transcription mismatches - a different failure mode
    than the grader re-checking its own work.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ["ANTHROPIC_API_KEY not set - skipped LLM consistency check"]

    grade = row.get("Stanford Grade", "")
    justification = row.get("Stanford Justification", "")

    prompt = f"""Check this structured output against its source evidence for consistency. Be skeptical - look for overstated confidence, unsupported claims, or mismatches between the evidence and the grade given.

Source evidence:
{source_excerpt or "(no source excerpt available)"}

Structured output:
Grade: {grade}
Justification: {justification}

Does the justification accurately reflect the source evidence, and does the grade match the strength of evidence described? Respond with ONLY a JSON object, no other text:
{{"consistent": true or false, "issue": "<one sentence describing the problem, or empty string if consistent>"}}"""

    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        )
        cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)

        if not parsed.get("consistent", True) and parsed.get("issue"):
            return [f"LLM consistency check: {parsed['issue']}"]
        return []

    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
        return [f"LLM consistency check failed to run: {e}"]


def review_row(row: dict, previous_row: dict = None, ipo_date: str = None,
               source_excerpt: str = "") -> dict:
    """
    Run all QC checks against a single row and annotate it with
    "QC Status" and "QC Notes". Mutates and returns the row dict.
    """
    issues = run_deterministic_checks(row, previous_row, ipo_date)
    issues.extend(llm_consistency_check(row, source_excerpt))

    row["QC Status"] = "Verified" if not issues else "Needs Review"
    row["QC Notes"] = "; ".join(issues)
    return row


def review_rows(rows: list, previous_rows_by_key: dict = None,
                 ipo_dates_by_ticker: dict = None,
                 source_excerpts_by_key: dict = None) -> list:
    """
    Batch entry point. The three lookup dicts are all optional - pass
    {} (or omit) if not available, and the relevant checks are simply
    skipped for rows with no matching entry.

    previous_rows_by_key: {(ticker, holder_name_lower): row_dict}
    ipo_dates_by_ticker: {ticker: "YYYY-MM-DD"}
    source_excerpts_by_key: {(ticker, holder_name_lower): str}
    """
    previous_rows_by_key = previous_rows_by_key or {}
    ipo_dates_by_ticker = ipo_dates_by_ticker or {}
    source_excerpts_by_key = source_excerpts_by_key or {}

    reviewed = []
    for row in rows:
        ticker = row.get("Ticker", "").upper()
        key = (ticker, row.get("Holder Name", "").strip().lower())

        reviewed.append(review_row(
            row,
            previous_row=previous_rows_by_key.get(key),
            ipo_date=ipo_dates_by_ticker.get(ticker),
            source_excerpt=source_excerpts_by_key.get(key, ""),
        ))

    return reviewed


if __name__ == "__main__":
    # Quick manual test with a single fabricated row
    test_row = {
        "Company Name": "Test Co",
        "Ticker": "TEST",
        "Actual Price": "20.00",
        "Current Price": "22.50",
        "Holder Name": "Jane Example",
        "Shares": "1000000",
        "Cash Value": "22500000",
        "Stanford Grade": "3",
        "Stanford Justification": "Bio mentions Palo Alto but no direct Stanford mention found.",
        "Lock-Up Expiry": "2027-01-15",
    }
    result = review_row(test_row, source_excerpt="Jane Example lives in Palo Alto, California.")
    print(json.dumps(result, indent=2))
