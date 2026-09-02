"""Fail-closed validation and recovery for pre-pricing IPO point prices.

The generic SEC parser serves both final 424B4s and preliminary S-1/S-1A
registrations. Preliminary filings can mention unrelated dollar amounts near IPO
language, so a point Filing Price must be independently confirmed against explicit
cover-page pricing language before publication. Unsupported values are cleared,
along with any offering size derived from that value. Conversely, when an S-1
cover explicitly states an issuer-proposed per-share IPO price that the generic
parser missed, recover that public fact conservatively rather than leaving Filing
Price blank. SEC fetch failures never create or preserve an unverified value.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import dashboard_export
import filing_parser


COVER_TEXT_LIMIT = 30000
PLAIN_PRICE_TEXT_LIMIT = 12000


class PreliminaryPriceGateError(RuntimeError):
    """Raised when a published preliminary point price cannot be verified."""


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _fixed_price_label(value):
    text = str(value or "").strip()
    match = re.fullmatch(r"\$\s*(\d{1,4}(?:\.\d{1,4})?)", text)
    return _number(match.group(1)) if match else None


def _format_price_label(value):
    number = _number(value)
    return f"${number:,.2f}" if number is not None else None


def _fixed_price_candidate_key(filing: dict):
    """Return an exact filing identity for a point-price S-1 candidate.

    A CIK alone is not sufficient because multiple S-1 amendments for the same
    issuer can contain different pricing terms. Reuse a completed SEC validation
    only when the exact filing source and point-price label match.
    """
    if not isinstance(filing, dict):
        return None
    form = str(filing.get("form") or "").strip().upper()
    if form not in {"S-1", "S-1/A"}:
        return None
    if str(filing.get("price_range") or "").strip():
        return None
    raw_price = str(filing.get("filing_price") or "").strip()
    if not raw_price:
        return None
    source_identity = str(filing.get("accession_no") or filing.get("sec_url") or "").strip()
    if not source_identity:
        return None
    return form, source_identity, raw_price


def _explicitly_undetermined(text: str) -> bool:
    cover = " ".join(str(text or "").split())[:COVER_TEXT_LIMIT]
    patterns = (
        r"\b(?:price\s+range|initial\s+public\s+offering\s+price|public\s+offering\s+price)"
        r"[^.]{0,160}\b(?:has|have)\s+not\s+yet\s+been\s+determined\b",
        r"\b(?:number\s+of\s+shares[^.]{0,120}\band\s+)?(?:the\s+)?price\s+range"
        r"[^.]{0,160}\b(?:has|have)\s+not\s+yet\s+been\s+determined\b",
        r"\bwe\s+have\s+not\s+yet\s+determined\b[^.]{0,160}"
        r"\b(?:price\s+range|initial\s+public\s+offering\s+price)\b",
    )
    return any(re.search(pattern, cover, re.IGNORECASE) for pattern in patterns)


def _assumption_context(text: str, start: int) -> bool:
    prefix = text[max(0, start - 80) : start]
    return bool(
        re.search(
            r"\b(?:assumed|assuming|hypothetical|illustrative)\b",
            prefix,
            re.IGNORECASE,
        )
    )


def _matches_expected_price(match, expected: float) -> bool:
    candidate = _number(match.group("price"))
    return candidate is not None and abs(candidate - expected) < 0.00001


def _extract_authoritative_proposed_point_price(text: str):
    """Recover a direct issuer-proposed IPO point price from the prospectus cover.

    Issuer statements such as "We expect the initial public offering price ...
    to be $7.00 per share" and "The offering price per share ... is to be fixed
    at $5.00 per share" are authoritative preliminary Filing Prices even though
    final pricing has not occurred. Keep this deliberately narrower than generic
    assumed/sensitivity language elsewhere in the filing.
    """
    cover = " ".join(str(text or "").split())[:COVER_TEXT_LIMIT]
    if _explicitly_undetermined(cover):
        return None

    number = r"(?P<price>\d{1,4}(?:\.\d{1,4})?)\b"
    patterns = (
        rf"\bwe\s+(?:currently\s+)?(?:expect|estimate|anticipate)\s+(?:that\s+)?"
        rf"(?:the\s+)?initial\s+public\s+offering\s+price"
        rf"(?:\s+of\s+[^.$]{{1,100}}?)?\s+(?:will\s+be|to\s+be)\s+"
        rf"\$\s*{number}\s+per\s+share\b",
        rf"\bthe\s+initial\s+public\s+offering\s+price"
        rf"(?:\s+of\s+[^.$]{{1,100}}?)?\s+is\s+(?:currently\s+)?"
        rf"(?:expected|estimated|anticipated)\s+to\s+be\s+"
        rf"\$\s*{number}\s+per\s+share\b",
        rf"\bthe\s+(?:initial\s+public\s+)?offering\s+price\s+per\s+share"
        rf"(?:\s+of\s+[^.$]{{1,160}}?)?(?:\s+in\s+this\s+offering)?"
        rf"\s+is\s+to\s+be\s+fixed\s+at\s+\$\s*{number}\s+per\s+share\b",
    )
    for pattern in patterns:
        match = re.search(pattern, cover, re.IGNORECASE)
        if not match or _assumption_context(cover, match.start()):
            continue
        price = _number(match.group("price"))
        if price is not None:
            return price
    return None


def _extract_authoritative_primary_share_count(text: str):
    """Return an issuer-only base offering share count from explicit cover prose.

    This supports offering-value recovery only when the same cover identifies the
    transaction as the issuer's initial public offering and does not identify
    selling stockholders in the nearby offer description. The bounded context
    includes issuer-offer wording immediately before the formal IPO sentence,
    because some SEC covers state the share count first. It intentionally ignores
    greenshoe/over-allotment quantities.
    """
    cover = " ".join(str(text or "").split())[:COVER_TEXT_LIMIT]
    start = re.search(r"\bthis\s+is\s+an\s+initial\s+public\s+offering\b", cover, re.IGNORECASE)
    if not start:
        return None
    context = cover[max(0, start.start() - 1600) : min(len(cover), start.start() + 1800)]
    if re.search(
        r"\bselling\s+(?:stockholder|shareholder|securityholder)s?\b",
        context,
        re.IGNORECASE,
    ):
        return None
    if not re.search(
        r"\b(?:we\s+(?:are\s+)?offering|offered\s+by\s+us)\b",
        context,
        re.IGNORECASE,
    ):
        return None
    share_match = re.search(
        r"\bwe\s+(?:are\s+)?offering\s+(?:for\s+sale\s+)?(?:a\s+total\s+of\s+)?"
        r"(?:the\s+)?([\d,]{2,})\s+(?:[A-Za-z][A-Za-z0-9-]*\s+){0,5}shares\b",
        context,
        re.IGNORECASE,
    )
    if not share_match:
        share_match = re.search(r"\bof\s+([\d,]{2,})\s+shares\b", context, re.IGNORECASE)
    if not share_match:
        return None
    try:
        shares = int(share_match.group(1).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return shares if shares > 0 else None


def has_authoritative_fixed_price(text: str, expected_price: float) -> bool:
    """Return True only for explicit prospective per-share IPO terms.

    Aggregate commitments such as "$1.5 billion ... at the IPO price" are not
    per-share offering prices. A statement that terms remain undetermined wins
    over incidental dollar values elsewhere in the filing. Direct issuer-proposed
    cover prices are accepted even when the filing describes them as expected or
    estimated, because they are authoritative preliminary terms rather than a
    sensitivity assumption.
    """
    expected_price = _number(expected_price)
    if expected_price is None:
        return False

    cover = " ".join(str(text or "").split())[:COVER_TEXT_LIMIT]
    if _explicitly_undetermined(cover):
        return False

    proposed = _extract_authoritative_proposed_point_price(cover)
    if proposed is not None and abs(proposed - expected_price) < 0.00001:
        return True

    number = r"(?P<price>\d{1,4}(?:\.\d{1,4})?)\b"
    scaled = r"(?!\s*(?:thousand|million|billion)\b)"
    explicit_patterns = (
        rf"\binitial\s+public\s+offering\s+price\s+per\s+share"
        rf"\s*(?:is|of|:|-)?\s*\$\s*{number}{scaled}",
        rf"\binitial\s+public\s+offering\s+price"
        rf"\s*(?:is|of|:|-)\s*\$\s*{number}\s+per\s+share\b",
        rf"\bpublic\s+offering\s+price\s+per\s+share"
        rf"\s*(?:is|of|:|-)?\s*\$\s*{number}{scaled}",
        rf"\bpublic\s+offering\s+price"
        rf"\s*(?:is|of|:|-)\s*\$\s*{number}\s+per\s+share\b",
        rf"\bprice\s+to\s+(?:the\s+)?public\s+per\s+share"
        rf"\s*(?:is|of|:|-)?\s*\$\s*{number}{scaled}",
        rf"\bat\s+a\s+fixed\s+price\s+of\s+\$\s*{number}\s+per\s+share\b",
    )
    for pattern in explicit_patterns:
        for match in re.finditer(pattern, cover, re.IGNORECASE):
            if _assumption_context(cover, match.start()):
                continue
            if _matches_expected_price(match, expected_price):
                if "fixed price" in match.group(0).casefold():
                    nearby = cover[max(0, match.start() - 1000) : match.start()]
                    if not re.search(
                        r"\b(?:initial\s+public\s+offering|public\s+offering|"
                        r"we\s+are\s+offering\s+for\s+sale)\b",
                        nearby,
                        re.IGNORECASE,
                    ):
                        continue
                return True

    # Some fixed-price covers omit "per share" in the sentence because the SEC
    # pricing table supplies that header separately. Accept this only very near the
    # prospectus cover and never when the dollar amount is scaled.
    early = cover[:PLAIN_PRICE_TEXT_LIMIT]
    plain_patterns = (
        rf"\binitial\s+public\s+offering\s+price"
        rf"\s*(?:is|of|:|-)\s*\$\s*{number}{scaled}",
        rf"\bpublic\s+offering\s+price"
        rf"\s*(?:is|of|:|-)\s*\$\s*{number}{scaled}",
        rf"\bprice\s+to\s+(?:the\s+)?public"
        rf"\s*(?:is|of|:|-)\s*\$\s*{number}{scaled}",
    )
    for pattern in plain_patterns:
        for match in re.finditer(pattern, early, re.IGNORECASE):
            if _assumption_context(early, match.start()):
                continue
            if _matches_expected_price(match, expected_price):
                return True
    return False


def _load_sec_primary_text(filing: dict) -> str:
    index_url = str(filing.get("sec_url") or "").strip()
    form = str(filing.get("form") or "S-1").strip().upper()
    if not index_url:
        raise PreliminaryPriceGateError(
            f"{filing.get('company') or filing.get('id')}: point Filing Price has no SEC source URL"
        )
    document_url = filing_parser.find_primary_document_url(
        index_url, expected_form_types=[form] if form in {"S-1", "S-1/A"} else ["S-1", "S-1/A"]
    )
    soup = filing_parser.fetch_document(document_url)
    return soup.get_text(" ", strip=True)


def _clean_signals(signals):
    cleaned = []
    for signal in signals or []:
        text = str(signal or "")
        if text.startswith("Fixed offering price disclosed at "):
            continue
        if text.startswith("Preliminary offering price disclosed at "):
            continue
        if text.startswith("IPO size disclosed or derived at approximately "):
            continue
        cleaned.append(signal)
    no_price = "No preliminary price range or fixed offering price detected yet"
    if no_price not in cleaned:
        cleaned.append(no_price)
    return cleaned


def _clear_unverified_fixed_price(filing: dict) -> dict:
    cleaned = dict(filing)
    cleaned["filing_price"] = None
    if not str(cleaned.get("price_range") or "").strip():
        cleaned["priority"] = "Medium"
    if "ipo_size" in cleaned:
        cleaned["ipo_size"] = None
    if "value" in cleaned:
        cleaned["value"] = None
        cleaned["value_label"] = "—"
    if "offering_size_source" in cleaned:
        cleaned["offering_size_source"] = None
    if "offering_size_confidence" in cleaned:
        cleaned["offering_size_confidence"] = None
    cleaned["signals"] = _clean_signals(cleaned.get("signals"))
    return cleaned


def _recover_verified_fixed_price_size(filing: dict, filing_text: str, price: float) -> dict:
    """Fill missing issuer-only size after the same fixed Filing Price is SEC-verified.

    A fixed Filing Price can already be present from the generic parser while its
    cover-table share count is missing. Once that exact price has independently
    passed the cover-term gate, use only an explicit issuer-only share count from
    the same SEC cover to fill the otherwise blank base offering value. Conflicting
    existing share counts are left untouched and selling-holder deals remain blank.
    """
    shares = _extract_authoritative_primary_share_count(filing_text)
    if shares is None:
        return filing

    existing_shares = _number(filing.get("primary_offering_shares"))
    if existing_shares is not None and int(round(existing_shares)) != shares:
        return filing

    offering_value = int(round(shares * price))
    recovered = dict(filing)
    changed = False
    size_filled = False

    if existing_shares is None:
        recovered["primary_offering_shares"] = shares
        changed = True

    if "ipo_size" in recovered and _number(recovered.get("ipo_size")) is None:
        recovered["ipo_size"] = offering_value
        changed = True
        size_filled = True
    if "value" in recovered and _number(recovered.get("value")) is None:
        recovered["value"] = offering_value
        recovered["value_label"] = f"${offering_value:,.0f}"
        changed = True
        size_filled = True

    if changed:
        if not str(recovered.get("offering_size_source") or "").strip():
            recovered["offering_size_source"] = (
                "SEC preliminary prospectus cover: primary offering; issuer-only; verified point price"
            )
        if not str(recovered.get("offering_size_confidence") or "").strip():
            recovered["offering_size_confidence"] = "High"
        if size_filled:
            signals = list(recovered.get("signals") or [])
            size_prefix = "IPO size disclosed or derived at approximately "
            if not any(str(signal or "").startswith(size_prefix) for signal in signals):
                signals.append(f"{size_prefix}${offering_value:,.0f}")
            recovered["signals"] = signals

    return recovered


def _recover_missing_preliminary_terms(filing: dict, filing_text: str) -> dict:
    """Fill only explicit SEC-cover point terms for an otherwise blank S-1 row."""
    if str(filing.get("filing_price") or "").strip():
        return filing
    if str(filing.get("price_range") or "").strip():
        return filing

    price = _extract_authoritative_proposed_point_price(filing_text)
    if price is None:
        return filing

    recovered = dict(filing)
    price_label = _format_price_label(price)
    recovered["filing_price"] = price_label
    recovered["priority"] = "High"

    cleaned_signals = []
    for signal in recovered.get("signals") or []:
        text = str(signal or "")
        if text == "No preliminary price range or fixed offering price detected yet":
            continue
        if text.startswith("Fixed offering price disclosed at "):
            continue
        if text.startswith("Preliminary offering price disclosed at "):
            continue
        if text.startswith("IPO size disclosed or derived at approximately "):
            continue
        cleaned_signals.append(signal)
    cleaned_signals.append(f"Preliminary offering price disclosed at {price_label} per share")

    shares = _extract_authoritative_primary_share_count(filing_text)
    if shares is not None:
        offering_value = int(round(shares * price))
        recovered["primary_offering_shares"] = shares
        recovered["offering_size_source"] = (
            "SEC preliminary prospectus cover: primary offering; issuer-only; proposed point price"
        )
        recovered["offering_size_confidence"] = "High"
        if "ipo_size" in recovered:
            recovered["ipo_size"] = offering_value
        if "value" in recovered:
            recovered["value"] = offering_value
            recovered["value_label"] = f"${offering_value:,.0f}"
        cleaned_signals.append(
            f"IPO size disclosed or derived at approximately ${offering_value:,.0f}"
        )

    recovered["signals"] = cleaned_signals
    return recovered


def review_watch_payload(
    payload: dict,
    text_loader=_load_sec_primary_text,
    skip_candidate_keys=None,
):
    """Recover and verify point-price S-1 rows, reusing exact prior checks only."""
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("S-1 payload must contain a filings list")

    skip_candidate_keys = set(skip_candidate_keys or ())
    updated = dict(payload)
    updated_filings = []
    invalid_by_cik = {}
    checked = 0

    for filing in filings:
        if not isinstance(filing, dict):
            updated_filings.append(filing)
            continue
        if str(filing.get("form") or "").strip().upper() not in {"S-1", "S-1/A"}:
            updated_filings.append(filing)
            continue
        if str(filing.get("price_range") or "").strip():
            updated_filings.append(filing)
            continue

        raw_price = str(filing.get("filing_price") or "").strip()
        if not raw_price:
            try:
                filing_text = text_loader(filing)
            except Exception:
                # Missing preliminary terms may remain blank when SEC is unavailable;
                # never manufacture a value merely to improve field completeness.
                updated_filings.append(filing)
                continue
            recovered = _recover_missing_preliminary_terms(filing, filing_text)
            if recovered != filing:
                checked += 1
            updated_filings.append(recovered)
            continue

        candidate_key = _fixed_price_candidate_key(filing)
        has_size = (
            _number(filing.get("ipo_size")) is not None
            or _number(filing.get("value")) is not None
        )
        if candidate_key is not None and candidate_key in skip_candidate_keys and has_size:
            updated_filings.append(filing)
            continue

        expected = _fixed_price_label(raw_price)
        if expected is None:
            raise PreliminaryPriceGateError(
                f"{filing.get('company') or filing.get('id')}: pre-pricing Filing Price "
                f"{raw_price!r} is not a canonical fixed-dollar value or range"
            )

        checked += 1
        try:
            filing_text = text_loader(filing)
        except Exception as error:
            raise PreliminaryPriceGateError(
                f"{filing.get('company') or filing.get('id')}: could not verify "
                f"pre-pricing Filing Price {raw_price!r} against the SEC filing: {error}"
            ) from error

        if has_authoritative_fixed_price(filing_text, expected):
            updated_filings.append(
                _recover_verified_fixed_price_size(filing, filing_text, expected)
            )
            continue

        cik = re.sub(r"\D", "", str(filing.get("cik") or "")).zfill(10)
        if not cik.strip("0"):
            raise PreliminaryPriceGateError(
                f"{filing.get('company') or filing.get('id')}: unsupported point price has no CIK"
            )
        invalid_by_cik[cik] = raw_price
        updated_filings.append(_clear_unverified_fixed_price(filing))

    updated["filings"] = updated_filings
    return updated, invalid_by_cik, checked


def sanitize_queue_payload(payload: dict, invalid_by_cik: dict) -> dict:
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("Public feed must contain a filings list")
    if not invalid_by_cik:
        return payload

    updated = dict(payload)
    updated_filings = []
    for filing in filings:
        if not isinstance(filing, dict):
            updated_filings.append(filing)
            continue
        cik = re.sub(r"\D", "", str(filing.get("cik") or "")).zfill(10)
        expected_label = invalid_by_cik.get(cik)
        if (
            expected_label
            and str(filing.get("stage") or "").strip().casefold() == "pre-pricing"
            and str(filing.get("form") or "").strip().upper() in {"S-1", "S-1/A"}
            and not str(filing.get("price_range") or "").strip()
            and str(filing.get("filing_price") or "").strip() == expected_label
        ):
            updated_filings.append(_clear_unverified_fixed_price(filing))
        else:
            updated_filings.append(filing)
    updated["filings"] = updated_filings
    return updated


def _write_json_atomic(path: Path, payload: dict):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def enforce_preliminary_fixed_prices(
    watch_path,
    queue_path,
    text_loader=_load_sec_primary_text,
):
    watch_path = Path(watch_path)
    queue_path = Path(queue_path)
    watch_payload = json.loads(watch_path.read_text(encoding="utf-8"))
    queue_payload = json.loads(queue_path.read_text(encoding="utf-8"))

    text_cache = {}

    def cached_text_loader(filing):
        source_identity = str(
            filing.get("accession_no") or filing.get("sec_url") or filing.get("id") or ""
        ).strip()
        if not source_identity:
            return text_loader(filing)
        if source_identity not in text_cache:
            text_cache[source_identity] = text_loader(filing)
        return text_cache[source_identity]

    updated_watch, watch_invalid, watch_checked = review_watch_payload(
        watch_payload,
        text_loader=cached_text_loader,
    )
    checked_watch_keys = {
        candidate_key
        for filing in updated_watch.get("filings", [])
        if (candidate_key := _fixed_price_candidate_key(filing)) is not None
    }

    # The public queue can retain qualifying S-1 records that have rolled out of
    # s1_watch.json. First propagate any invalid watch result, then independently
    # recover or verify every remaining queue-only point Filing Price before release.
    prechecked_queue = sanitize_queue_payload(queue_payload, watch_invalid)
    updated_queue, queue_invalid, queue_checked = review_watch_payload(
        prechecked_queue,
        text_loader=cached_text_loader,
        skip_candidate_keys=checked_watch_keys,
    )

    invalid_by_cik = dict(watch_invalid)
    invalid_by_cik.update(queue_invalid)
    checked = watch_checked + queue_checked

    if updated_watch != watch_payload:
        _write_json_atomic(watch_path, updated_watch)
    if updated_queue != queue_payload:
        _write_json_atomic(queue_path, updated_queue)
        dashboard_export.write_dashboard_csv(updated_queue.get("filings", []), queue_path)

    return updated_watch, updated_queue, invalid_by_cik, checked


if __name__ == "__main__":
    import sys

    watch = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../docs/data/s1_watch.json")
    queue = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("../docs/data/filings.json")
    _, _, invalid, checked = enforce_preliminary_fixed_prices(watch, queue)
    print(
        f"Reviewed {checked} pre-pricing point-price record(s); "
        f"cleared {len(invalid)} unsupported value(s)"
    )