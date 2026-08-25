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
STRONG_SENTENCE_BOUNDARY_PATTERN = re.compile(r"[.!?]\s+[A-Z]")
SEC_FOOTNOTE_SUFFIX_PATTERN = re.compile(r"(?:\s*\(\d+[a-z]?\))+$", re.I)
NON_PERSON_TYPES = {"entity", "fund", "trust"}
CONFIDENCE_PREFIX = "Confidence 5/5 — "
LEGACY_SEC_SOURCE_PREFIX = "SEC 424B4 management biography — "


def _clean_name(value: str) -> str:
    name = " ".join(str(value or "").split())
    return SEC_FOOTNOTE_SUFFIX_PATTERN.sub("", name).strip()


def _name_pattern(value: str):
    tokens = re.findall(r"[A-Za-z0-9]+", _clean_name(value))
    if len(tokens) < 2:
        return None
    return re.compile(r"\b" + r"\W+".join(re.escape(token) for token in tokens) + r"\b", re.I)


def _has_affiliation_language(context: str, stanford_start: int, stanford_end: int) -> bool:
    """Require affiliation language in the same prose sentence as Stanford.

    SEC biographies frequently contain abbreviations such as ``B.A.`` so a
    literal period cannot be treated as a sentence boundary. A period/question
    mark/exclamation point followed by whitespace and an uppercase letter is a
    conservative boundary signal for this purpose.
    """
    before = context[max(0, stanford_start - 450):stanford_start]
    for match in reversed(list(AFFILIATION_PATTERN.finditer(before))):
        if not STRONG_SENTENCE_BOUNDARY_PATTERN.search(before[match.end():]):
            return True

    after = context[stanford_end:min(len(context), stanford_end + 250)]
    boundary = STRONG_SENTENCE_BOUNDARY_PATTERN.search(after)
    same_sentence_after = after[:boundary.start()] if boundary else after
    return bool(AFFILIATION_PATTERN.search(same_sentence_after))


def _same_sentence_around_stanford(context: str, stanford_start: int, stanford_end: int) -> str:
    """Return conservative local prose around the Stanford reference."""
    before = context[max(0, stanford_start - 450):stanford_start]
    boundaries = list(STRONG_SENTENCE_BOUNDARY_PATTERN.finditer(before))
    start = boundaries[-1].end() if boundaries else 0

    after = context[stanford_end:min(len(context), stanford_end + 250)]
    boundary = STRONG_SENTENCE_BOUNDARY_PATTERN.search(after)
    end = boundary.start() if boundary else len(after)
    return " ".join((before[start:] + context[stanford_start:stanford_end] + after[:end]).split())


def _connection_note(context: str, stanford_start: int, stanford_end: int) -> str:
    """Summarize only the affiliation type explicitly supported by SEC prose."""
    sentence = _same_sentence_around_stanford(context, stanford_start, stanford_end)
    lowered = sentence.casefold()

    if re.search(r"\bprofessor\b|\bteaches?\b", lowered):
        return "SEC 424B4 management biography confirms a faculty or teaching role at Stanford University."
    if re.search(r"\bfellow\b", lowered):
        return "SEC 424B4 management biography confirms a fellowship connection to Stanford University."
    if re.search(r"\battended\b", lowered):
        return "SEC 424B4 management biography confirms attendance at Stanford University."
    if re.search(r"\bstudied\b", lowered):
        return "SEC 424B4 management biography confirms study at Stanford University."
    if re.search(r"\bgraduat(?:e|ed)\b|\bgraduate\s+of\b", lowered):
        return "SEC 424B4 management biography confirms graduation from Stanford University."

    degree_signal = re.search(
        r"\bdegree\b|\b(?:B\.?A\.?|B\.?S\.?|M\.?A\.?|M\.?S\.?|M\.?B\.?A\.?|J\.?D\.?|M\.?D\.?|Ph\.?D\.?)\b",
        sentence,
        re.I,
    )
    degree_verb = re.search(r"\bholds?\b|\bearned\b|\breceived\b", sentence, re.I)
    if degree_signal and degree_verb:
        return "SEC 424B4 management biography confirms a degree from Stanford University."

    return "SEC 424B4 management biography explicitly confirms a Stanford University affiliation."


def find_sec_stanford_evidence(full_text: str, person_name: str, peer_names=()) -> str | None:
    """Return a concise SEC-supported connection note for an exact person match."""
    text = " ".join(str(full_text or "").split())
    target_pattern = _name_pattern(person_name)
    if not text or target_pattern is None or not STANFORD_PATTERN.search(text):
        return None

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
        return _connection_note(window, stanford.start(), stanford.end())

    return None


def find_sec_stanford_affiliation(full_text: str, person_name: str, peer_names=()) -> bool:
    """Return True only for exact-person, explicit Stanford University evidence."""
    return bool(find_sec_stanford_evidence(full_text, person_name, peer_names))


def _needs_sec_note_upgrade(person: dict) -> bool:
    source = str(person.get("stanford_source") or "").strip()
    return bool(
        person.get("stanford_university_bio")
        and source.startswith(LEGACY_SEC_SOURCE_PREFIX)
        and not source.startswith(CONFIDENCE_PREFIX)
    )


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
            and (not person.get("stanford_university_bio") or _needs_sec_note_upgrade(person))
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
            note = find_sec_stanford_evidence(full_text, person["name"], peer_names)
            if not note:
                continue
            new_source = f"{CONFIDENCE_PREFIX}{note} Source: {document_url}"
            if person.get("stanford_university_bio") is True and person.get("stanford_source") == new_source:
                continue
            person["stanford_university_bio"] = True
            person["stanford_source"] = new_source
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
