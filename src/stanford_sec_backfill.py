"""Backfill SEC-confirmed Stanford affiliations for published beneficial owners.

This utility is deliberately conservative. It only upgrades an existing public
beneficial-owner record when the issuer's 424B4 contains person-specific text
that ties that exact name to Stanford University with explicit affiliation
language. It does not add new people, infer affiliations, or use same-name web
matches.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import dashboard_export
import filing_parser


STANFORD_PATTERN = re.compile(r"\bstanford\s+university\b", re.I)
AFFILIATION_PATTERN = re.compile(
    r"(?:\bholds?\b|\bearned\b|\breceived\b|\bgraduat(?:e|ed)\b|"
    r"\battended\b|\bstudied\b|\bdegree\b|\bprofessor\b|\bfellow\b|"
    r"\bserved\b|\bteaches?\b|\bgraduate\s+of\b)",
    re.I,
)
SEC_FOOTNOTE_SUFFIX_PATTERN = re.compile(r"(?:\s*\(\d+[a-z]?\))+$", re.I)
NON_PERSON_TYPES = {"entity", "fund", "trust"}


def _clean_name(value: str) -> str:
    name = " ".join(str(value or "").split())
    return SEC_FOOTNOTE_SUFFIX_PATTERN.sub("", name).strip()


def _name_pattern(value: str):
    tokens = re.findall(r"[A-Za-z0-9]+", _clean_name(value))
    if len(tokens) < 2:
        return None
    return re.compile(r"\b" + r"\W+".join(re.escape(token) for token in tokens) + r"\b", re.I)


def _has_affiliation_language(context: str, stanford_start: int, stanford_end: int) -> bool:
    boundaries = list(re.finditer(r"[.!?]\s+(?=[A-Z])", context))
    sentence_start = max(
        (boundary.end() for boundary in boundaries if boundary.end() <= stanford_start),
        default=0,
    )
    sentence_end = next(
        (boundary.start() for boundary in boundaries if boundary.start() >= stanford_end),
        len(context),
    )
    sentence = context[sentence_start:sentence_end]
    return bool(AFFILIATION_PATTERN.search(sentence))


def find_sec_stanford_affiliation(full_text: str, person_name: str, peer_names=()) -> bool:
    """Return True only for exact-person, explicit Stanford University evidence.

    A candidate is rejected when another disclosed person's full name appears
    between the target person's name and the Stanford reference. This prevents
    a management roster or one person's biography from incorrectly assigning a
    neighboring person's Stanford credential to the target holder.
    """
    text = " ".join(str(full_text or "").split())
    target_pattern = _name_pattern(person_name)
    if not text or target_pattern is None or not STANFORD_PATTERN.search(text):
        return False

    peer_patterns = []
    target_clean = _clean_name(person_name).casefold()
    for peer in peer_names or ():
        peer_clean = _clean_name(peer)
        if not peer_clean or peer_clean.casefold() == target_clean:
            continue
        pattern = _name_pattern(peer_clean)
        if pattern is not None:
            peer_patterns.append(pattern)

    for target in target_pattern.finditer(text):
        window = text[target.start(): min(len(text), target.end() + 1800)]
        stanford = STANFORD_PATTERN.search(window)
        if not stanford:
            continue
        if not _has_affiliation_language(window, stanford.start(), stanford.end()):
            continue

        contaminated = False
        for peer_pattern in peer_patterns:
            peer = peer_pattern.search(window, target.end() - target.start())
            if peer and peer.start() < stanford.start():
                contaminated = True
                break
        if contaminated:
            continue
        return True

    return False


def _eligible_filing(filing: dict, start_date: str | None, end_date: str | None) -> bool:
    if str(filing.get("form") or "").upper() != "424B4":
        return False
    filed = str(filing.get("filed") or "")
    if start_date and filed < start_date:
        return False
    if end_date and filed > end_date:
        return False
    return True


def enrich_feed(feed_path, start_date=None, end_date=None) -> dict:
    path = Path(feed_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    filings = payload.get("filings")
    if not isinstance(filings, list):
        raise SystemExit("Research Monitor feed must contain a filings list")

    changed_people = 0
    checked_filings = 0
    failures = []

    for filing in filings:
        if not isinstance(filing, dict) or not _eligible_filing(filing, start_date, end_date):
            continue
        people = filing.get("people") or []
        candidates = [
            person for person in people
            if isinstance(person, dict)
            and person.get("name")
            and str(person.get("holder_type") or "").casefold() not in NON_PERSON_TYPES
            and not person.get("stanford_university_bio")
        ]
        if not candidates:
            continue

        index_url = str(filing.get("sec_url") or "").strip()
        if not index_url.startswith("https://www.sec.gov/"):
            failures.append(f"{filing.get('company')}: missing SEC filing URL")
            continue

        try:
            document_url = filing_parser.find_primary_document_url(
                index_url, expected_form_types=["424B4"]
            )
            soup = filing_parser.fetch_document(document_url)
        except Exception as error:
            failures.append(f"{filing.get('company')}: {error}")
            continue

        checked_filings += 1
        full_text = soup.get_text(" ", strip=True)
        peer_names = [
            person.get("name") for person in people
            if isinstance(person, dict)
            and person.get("name")
            and str(person.get("holder_type") or "").casefold() not in NON_PERSON_TYPES
        ]

        for person in candidates:
            if find_sec_stanford_affiliation(full_text, person["name"], peer_names):
                person["stanford_university_bio"] = True
                person["stanford_source"] = f"SEC 424B4 management biography — {document_url}"
                changed_people += 1
                print(
                    f"[stanford_sec_backfill] confirmed {person['name']} "
                    f"({filing.get('company')}) from SEC filing"
                )

    if changed_people:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        dashboard_export.write_dashboard_csv(payload.get("filings", []), path)

    print(
        f"[stanford_sec_backfill] checked {checked_filings} filing(s); "
        f"confirmed {changed_people} Stanford-affiliated beneficial owner(s)"
    )
    if failures:
        print(
            f"[stanford_sec_backfill] {len(failures)} filing(s) could not be checked; "
            "left unchanged rather than guessed"
        )
        for failure in failures[:10]:
            print(f"[stanford_sec_backfill] unresolved: {failure}")

    return {
        "checked_filings": checked_filings,
        "confirmed_people": changed_people,
        "failures": failures,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill SEC-confirmed Stanford affiliations in the public Research Monitor feed"
    )
    parser.add_argument("feed", nargs="?", default="../docs/data/filings.json")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    args = parser.parse_args()
    enrich_feed(args.feed, start_date=args.start, end_date=args.end)


if __name__ == "__main__":
    main()
