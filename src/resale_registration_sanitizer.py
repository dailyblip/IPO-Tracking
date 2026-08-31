"""Fail closed on resale-only S-1/S-1A registrations before publication.

The primary S-1 watcher already applies the shared IPO eligibility gate. This
module is a final release-time defense for filing HTML whose iXBRL/layout markup
splits otherwise definitive resale-cover language enough to evade the narrower
upstream regex. It never infers from offering size, ticker, or missing fields.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from dashboard_export import write_dashboard_csv
import filing_parser

S1_FORMS = {"S-1", "S-1/A"}
_SELLING_HOLDER_RE = re.compile(
    r"\bselling\s+(?:securityholders|stockholders|shareholders)\b",
    re.IGNORECASE,
)
_RESALE_ACTION_RE = re.compile(r"\b(?:resale|offer\s+and\s+sale)\b", re.IGNORECASE)
_POST_LISTING_TRADING_RE = re.compile(
    r"\b(?:our|the company(?:'s)?) common stock (?:began|commenced) trading\b",
    re.IGNORECASE,
)
_NO_ISSUER_PROCEEDS_FROM_COVERED_SHARES_RE = re.compile(
    r"\bwe (?:will|would) not receive any (?:of )?(?:the )?proceeds from (?:"
    r"(?:the )?sale of (?:the )?shares(?: of (?:our )?common stock)? covered by this prospectus"
    r"|any sale of (?:our )?common stock by (?:the )?selling\s+"
    r"(?:securityholders|stockholders|shareholders) pursuant to this prospectus"
    r")\b",
    re.IGNORECASE,
)


def looks_like_resale_only_cover(filing_text: str) -> bool:
    """Return True only for explicit prospectus-cover resale language.

    A resale registration commonly says that "this prospectus relates to" an
    offer/resale "from time to time" by selling holders. Normal IPOs with a
    secondary component instead describe issuer shares and selling-holder shares
    as the current underwritten offering. Requiring all four cover concepts keeps
    this fallback narrow while tolerating large iXBRL/layout insertions between
    them.

    A second, equally deterministic variant covers post-listing registrations
    filed after a merger or other transaction: the prospectus states that the
    common stock already began/commenced trading, identifies selling holders, and
    states that the issuer receives no proceeds from the shares covered by or sold
    by selling holders pursuant to that prospectus. Requiring all three facts
    avoids treating an ordinary IPO with a secondary component as a resale-only
    registration.
    """
    normalized = " ".join(str(filing_text or "").split())
    if not normalized:
        return False

    lowered = normalized.casefold()
    anchor = "this prospectus relates to"
    start = 0
    while True:
        position = lowered.find(anchor, start)
        if position < 0:
            break
        # The cover can contain long tagged lists of resale-share categories.
        # A bounded window prevents unrelated risk-factor references later in the
        # filing from being combined into a false resale classification.
        window = normalized[position : position + 15_000]
        window_lower = window.casefold()
        if (
            "from time to time" in window_lower
            and _SELLING_HOLDER_RE.search(window)
            and _RESALE_ACTION_RE.search(window)
        ):
            return True
        start = position + len(anchor)

    front_matter = normalized[:125_000]
    return bool(
        _POST_LISTING_TRADING_RE.search(front_matter)
        and _SELLING_HOLDER_RE.search(front_matter)
        and _NO_ISSUER_PROCEEDS_FROM_COVERED_SHARES_RE.search(front_matter)
    )


def _visible_filing_text(soup) -> str:
    """Return filing text without hidden inline-XBRL metadata.

    Inline-XBRL filings can place a very large ``ix:header``/``ix:hidden`` block
    ahead of visible prospectus cover language. BeautifulSoup includes that hidden
    metadata in ``get_text()``, which can push otherwise adjacent cover concepts
    outside the deliberately bounded resale-classifier windows. Remove only the
    non-visible iXBRL header/hidden containers; do not drop visible filing text.
    """
    for tag in soup.find_all():
        name = str(getattr(tag, "name", "") or "").casefold()
        if name in {"ix:header", "ix:hidden"} or name.endswith(":header") or name.endswith(":hidden"):
            tag.decompose()
    return soup.get_text(" ", strip=True)


def _fetch_filing_text(record: dict) -> str:
    index_url = str(record.get("sec_url") or "").strip()
    if not index_url:
        return ""
    document_url = filing_parser.find_primary_document_url(
        index_url, expected_form_types=["S-1", "S-1/A"]
    )
    soup = filing_parser.fetch_document(document_url)
    return _visible_filing_text(soup)


def _excluded_accessions(payload: dict) -> set[str]:
    excluded: set[str] = set()
    for record in payload.get("filings", []):
        if str(record.get("form") or "").strip().upper() not in S1_FORMS:
            continue
        accession = str(record.get("accession_no") or record.get("id") or "").strip()
        if not accession:
            continue
        try:
            filing_text = _fetch_filing_text(record)
        except Exception as error:
            # SEC/network/parser failures are transient. Preserve the published
            # row rather than deleting it without a completed evidence check.
            print(f"[resale_registration_sanitizer] Could not evaluate {accession}: {error}")
            continue
        if looks_like_resale_only_cover(filing_text):
            excluded.add(accession)
            print(f"[resale_registration_sanitizer] Excluding resale-only registration {accession}")
    return excluded


def sanitize_payload(payload: dict, excluded_accessions: set[str]) -> dict:
    sanitized = dict(payload)
    sanitized["filings"] = [
        record
        for record in payload.get("filings", [])
        if str(record.get("accession_no") or record.get("id") or "").strip()
        not in excluded_accessions
    ]
    return sanitized


def sanitize_files(s1_watch_path: Path, queue_path: Path) -> set[str]:
    s1_payload = json.loads(s1_watch_path.read_text(encoding="utf-8"))
    excluded = _excluded_accessions(s1_payload)
    if not excluded:
        return set()

    queue_payload = json.loads(queue_path.read_text(encoding="utf-8"))
    s1_payload = sanitize_payload(s1_payload, excluded)
    queue_payload = sanitize_payload(queue_payload, excluded)

    s1_watch_path.write_text(
        json.dumps(s1_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    queue_path.write_text(
        json.dumps(queue_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_dashboard_csv(queue_payload.get("filings", []), queue_path)
    return excluded


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    if len(args) != 2:
        raise SystemExit(
            "Usage: python resale_registration_sanitizer.py <s1_watch.json> <filings.json>"
        )
    excluded = sanitize_files(Path(args[0]), Path(args[1]))
    print(f"Excluded {len(excluded)} resale-only S-1/S-1A registration(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
