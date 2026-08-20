"""Research-grade extraction of holder lock-up terms from SEC prospectus text.

The goal is conservative structure, not aggressive inference. We identify holder-facing
transfer restrictions, separate them from registration-rights timing and issuer-only
restrictions, and preserve multiple schedules when a prospectus has special holder terms.
"""
from __future__ import annotations

import re

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "eighteen": 18, "twenty-four": 24,
}


def _norm(value: str) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _number(value: str):
    value = str(value or "").strip().lower()
    if value.isdigit():
        return int(value)
    return WORD_NUMBERS.get(value)


def _duration_matches(text: str):
    patterns = [
        (r"\b(\d{2,3})[-\s]?day\s+lock-?up\b", "days"),
        (r"\block-?up(?:\s+period)?(?:\s+of|\s+for)?\s*(\d{2,3})\s+days\b", "days"),
        (r"\bperiod(?:\s+ending|\s+continuing|\s+of)?[^.;]{0,140}?\b(\d{2,3})\s+days\s+after\b", "days"),
        (r"\b(\d{2,3})\s+days\s+after\s+the\s+date\s+of\s+(?:this|the)\s+prospectus\b", "days"),
        (r"\bfor\s+(?:a\s+)?period\s+of\s+(?:up\s+to\s+)?(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|twelve|eighteen|twenty-four)(?:\s*\(\s*\d+\s*\))?\s+months?\b", "months"),
        (r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|twelve|eighteen|twenty-four)(?:\s*\(\s*\d+\s*\))?\s+months?\s+after\b", "months"),
        (r"\b(\d{1,2}|one|two|three)(?:\s*\(\s*\d+\s*\))?\s+years?\s+(?:after|following|from)\b", "years"),
    ]
    found = []
    for pattern, unit in patterns:
        for match in re.finditer(pattern, text, re.I):
            value = _number(match.group(1))
            if value:
                found.append((match.start(), match.end(), value, unit, match.group(0)))
    return sorted(found, key=lambda item: item[0])


def _scope_tags(context: str):
    lowered = context.lower()
    tags = []
    if "substantially all" in lowered and any(x in lowered for x in ("shares", "securities", "stockholders", "holders")):
        tags.append("substantially_all_holders")
    if "all other shares" in lowered or "all other stockholders" in lowered:
        tags.append("all_other_holders")
    if "director" in lowered:
        tags.append("directors")
    if "executive officer" in lowered or "officers" in lowered:
        tags.append("executive_officers")
    if "selling stockholder" in lowered or "selling shareholder" in lowered:
        tags.append("selling_stockholders")
    if "5%" in context or "five percent" in lowered:
        tags.append("five_percent_holders")
    if "record holders" in lowered or "certain other holders" in lowered or "certain of our stockholders" in lowered:
        tags.append("certain_other_holders")
    return list(dict.fromkeys(tags))


def _special_holder(context: str, duration_text: str):
    # Named schedules are kept separate from the general holder lock-up.
    patterns = [
        r"\b([A-Z][A-Za-z0-9.&' -]{1,50})\s+Lock-?Up\b",
        r"\block-?up\s+(?:period\s+)?for\s+([A-Z][A-Za-z0-9.&' -]{1,50}?)(?:[;,.)]|\s+with\b|\s+starting\b|\s+through\b)",
        r"\b(?:for|held by)\s+([A-Z][A-Za-z0-9.&' -]{1,50}?)\s*[:;,]\s*[^.;]{0,80}?" + re.escape(duration_text),
    ]
    for pattern in patterns:
        matches = list(re.finditer(pattern, context, re.I if "Lock" in pattern else 0))
        if not matches:
            continue
        value = _norm(matches[-1].group(1)).strip(" ,.-")
        value = re.sub(r"^(?:the|an?)\s+", "", value, flags=re.I)
        if value and value.lower() not in {"general", "holder", "shareholder", "stockholder", "company"}:
            return value
    # Common SEC construction: "366-day lock-up for Elon Musk".
    after = re.search(re.escape(duration_text) + r"\s+for\s+([A-Z][A-Za-z0-9.&' -]{1,50}?)(?:[;,.)]|\s+and\b|\s+with\b)", context)
    if after:
        return _norm(after.group(1)).strip(" ,.-")
    return None


def _score(context: str, scope_tags, special_holder: str | None):
    lowered = context.lower()
    score = 0
    if "lock-up" in lowered or "lockup" in lowered:
        score += 6
    if "underwriter" in lowered:
        score += 3
    if "agreed" in lowered or "will not" in lowered or "subject to" in lowered:
        score += 3
    if any(tag in scope_tags for tag in ("directors", "executive_officers", "selling_stockholders")):
        score += 5
    if any(tag in scope_tags for tag in ("substantially_all_holders", "all_other_holders")):
        score += 5
    if special_holder:
        score += 4
    if "registration rights" in lowered or "demand registration" in lowered:
        score -= 8
    if "form s-1" in lowered and not scope_tags and not special_holder:
        score -= 5
    if "we have agreed" in lowered and not scope_tags and not special_holder:
        # Usually an issuer issuance lock-up rather than a holder liquidity restriction.
        score -= 4
    return score


def _scope_label(tags):
    labels = {
        "substantially_all_holders": "substantially all pre-IPO holders",
        "all_other_holders": "all other covered holders",
        "directors": "directors",
        "executive_officers": "executive officers",
        "selling_stockholders": "selling stockholders",
        "five_percent_holders": "5%+ holders",
        "certain_other_holders": "certain other holders",
    }
    return ", ".join(labels[tag] for tag in tags if tag in labels) or None


def _candidate_terms(text: str):
    terms = []
    for start, end, value, unit, matched in _duration_matches(text):
        left = max(0, start - 900)
        right = min(len(text), end + 900)
        context = text[left:right]
        tags = _scope_tags(context)
        special = _special_holder(context, matched)
        score = _score(context, tags, special)
        if score < 6:
            continue
        # Preserve a concise source excerpt around the matched duration.
        source_left = max(0, start - 450)
        source_right = min(len(text), end + 650)
        excerpt = _norm(text[source_left:source_right])
        terms.append({
            "duration_value": value,
            "duration_unit": unit,
            "duration_days": value if unit == "days" else None,
            "scope_tags": tags,
            "scope": _scope_label(tags),
            "special_holder": special,
            "has_staggered_releases": bool(re.search(r"staggered|early release|release(?:d|s)?\s+(?:of|for)|more than\s+\d+%", context, re.I)),
            "score": score,
            "source_text": excerpt,
        })
    # Deduplicate repeated prospectus text/TOC echoes while retaining different schedules.
    unique = []
    seen = set()
    for term in sorted(terms, key=lambda t: (-t["score"], t["duration_unit"], t["duration_value"])):
        key = (
            term["duration_value"], term["duration_unit"],
            (term.get("special_holder") or "").lower(), tuple(term.get("scope_tags") or []),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(term)
    return unique


def extract_holder_lockup_info(text: str) -> dict:
    """Extract structured holder lock-up terms from flattened prospectus text."""
    text = _norm(text)
    if not text or not re.search(r"lock-?up|market standoff", text, re.I):
        return {
            "raw_text": None, "duration_days": None, "duration_value": None,
            "duration_unit": None, "scope": None, "scope_tags": [], "terms": [],
            "structured": False, "confidence": "None",
        }

    terms = _candidate_terms(text)
    general = [t for t in terms if not t.get("special_holder")]
    # Prefer broad holder coverage and explicit officer/director/seller language.
    primary = max(general, key=lambda t: t["score"], default=None)
    if primary is None and len(terms) == 1:
        primary = terms[0]

    distinct_schedules = {(t["duration_value"], t["duration_unit"], t.get("special_holder")) for t in terms}
    structured = len(distinct_schedules) > 1 or any(t.get("has_staggered_releases") for t in terms)
    raw = primary.get("source_text") if primary else (terms[0].get("source_text") if terms else None)
    confidence = "High" if primary and primary["score"] >= 12 else ("Medium" if primary else "Unresolved")
    return {
        "raw_text": raw,
        "duration_days": primary.get("duration_days") if primary else None,
        "duration_value": primary.get("duration_value") if primary else None,
        "duration_unit": primary.get("duration_unit") if primary else None,
        "scope": primary.get("scope") if primary else None,
        "scope_tags": primary.get("scope_tags") if primary else [],
        "terms": terms,
        "structured": structured,
        "confidence": confidence,
    }
