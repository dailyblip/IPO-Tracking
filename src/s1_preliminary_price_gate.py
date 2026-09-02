"""Fail-closed validation for fixed pre-pricing IPO prices.

The generic SEC parser serves both final 424B4s and preliminary S-1/S-1A
registrations. Preliminary filings can mention unrelated dollar amounts near IPO
language, so a fixed Filing Price must be independently confirmed against explicit
cover-page pricing language before publication. Unsupported values are cleared,
along with any offering size derived from that value. SEC fetch failures block
publication rather than accepting an unverified price.
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
    """Raised when a published preliminary fixed price cannot be verified."""


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


def has_authoritative_fixed_price(text: str, expected_price: float) -> bool:
    """Return True only for explicit prospective per-share/fixed IPO terms.

    Aggregate commitments such as "$1.5 billion ... at the IPO price" are not
    per-share offering prices. A statement that terms remain undetermined wins
    over incidental dollar values elsewhere in the filing.
    """
    expected_price = _number(expected_price)
    if expected_price is None:
        return False

    cover = " ".join(str(text or "").split())[:COVER_TEXT_LIMIT]
    if _explicitly_undetermined(cover):
        return False

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
            f"{filing.get('company') or filing.get('id')}: fixed Filing Price has no SEC source URL"
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


def review_watch_payload(payload: dict, text_loader=_load_sec_primary_text):
    """Verify every fixed-price pre-pricing row and clear unsupported values."""
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise ValueError("S-1 watch payload must contain a filings list")

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
            updated_filings.append(filing)
            continue

        cik = re.sub(r"\D", "", str(filing.get("cik") or "")).zfill(10)
        if not cik.strip("0"):
            raise PreliminaryPriceGateError(
                f"{filing.get('company') or filing.get('id')}: unsupported fixed price has no CIK"
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


def enforce_preliminary_fixed_prices(watch_path, queue_path):
    watch_path = Path(watch_path)
    queue_path = Path(queue_path)
    watch_payload = json.loads(watch_path.read_text(encoding="utf-8"))
    queue_payload = json.loads(queue_path.read_text(encoding="utf-8"))

    updated_watch, invalid_by_cik, checked = review_watch_payload(watch_payload)
    updated_queue = sanitize_queue_payload(queue_payload, invalid_by_cik)

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
        f"Verified {checked} fixed pre-pricing Filing Price record(s); "
        f"cleared {len(invalid)} unsupported value(s)"
    )
