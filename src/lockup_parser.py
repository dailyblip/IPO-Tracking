"""Research-grade extraction of holder lock-up terms from SEC prospectus text.

The parser is deliberately conservative. It structures holder transfer restrictions,
rejects nearby but unrelated Rule 144/registration-rights/greenshoe timing, and keeps
staggered release tranches only when the prospectus supplies enough evidence.
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
    """Return plausible time periods; lock-up relevance is filtered later."""
    patterns = [
        (r"\b(\d{2,3})[-\s]?day\s+lock-?up\b", "days"),
        (r"\block-?up(?:\s+period)?(?:\s+of|\s+for)?\s*(\d{2,3})\s+days\b", "days"),
        (r"\bperiod(?:\s+ending|\s+continuing|\s+of)?[^.;]{0,140}?\b(\d{2,3})\s+days\s+after\b", "days"),
        (r"\b(\d{2,3})\s+days\s+(?:after|following)\s+(?:the\s+date\s+of\s+)?(?:this\s+prospectus|the\s+prospectus|the\s+offering|this\s+offering|the\s+ipo\s+date|the\s+ipo)\b", "days"),
        # Staggered schedules are often phrased simply "25% ... for 180 days".
        (r"\bfor\s+(?:a\s+period\s+of\s+)?(\d{2,3})\s+days\b", "days"),
        (r"\bfor\s+(?:a\s+)?period\s+of\s+(?:up\s+to\s+)?(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|twelve|eighteen|twenty-four)(?:\s*\(\s*\d+\s*\))?\s+months?\b", "months"),
        (r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|twelve|eighteen|twenty-four)(?:\s*\(\s*\d+\s*\))?\s+months?\s+after\b", "months"),
        (r"\b(\d{1,2}|one|two|three)(?:\s*\(\s*\d+\s*\))?\s+years?\s+(?:after|following|from)\b", "years"),
    ]
    found = []
    seen = set()
    for pattern, unit in patterns:
        for match in re.finditer(pattern, text, re.I):
            value = _number(match.group(1))
            if not value:
                continue
            key = (match.start(), match.end(), value, unit)
            if key in seen:
                continue
            seen.add(key)
            found.append((match.start(), match.end(), value, unit, match.group(0)))
    return sorted(found, key=lambda item: item[0])


def _clause_context(text: str, start: int, end: int) -> str:
    """Keep scope language tied to the same sentence/semicolon clause."""
    left_floor = max(0, start - 1800)
    right_cap = min(len(text), end + 1800)
    before = text[left_floor:start]
    after = text[end:right_cap]
    left_candidates = [before.rfind(". "), before.rfind("; ")]
    left_cut = max(left_candidates)
    left = left_floor + (left_cut + 2 if left_cut >= 0 else 0)
    right_candidates = [i for i in (after.find(". "), after.find("; ")) if i >= 0]
    right = end + (min(right_candidates) if right_candidates else len(after))
    return _norm(text[left:right])


def _scope_tags(context: str):
    lowered = context.lower()
    tags = []
    if "substantially all" in lowered and any(x in lowered for x in ("shares", "securities", "stockholders", "holders", "capital stock")):
        tags.append("substantially_all_holders")
    if "all other shares" in lowered or "all other stockholders" in lowered or "all other holders" in lowered:
        tags.append("all_other_holders")
    if "director" in lowered:
        tags.append("directors")
    if "executive officer" in lowered or re.search(r"\bofficers\b", lowered):
        tags.append("executive_officers")
    if "selling stockholder" in lowered or "selling shareholder" in lowered:
        tags.append("selling_stockholders")
    if "5%" in context or "five percent" in lowered:
        tags.append("five_percent_holders")
    if "record holders" in lowered or "certain other holders" in lowered or "certain of our stockholders" in lowered:
        tags.append("certain_other_holders")
    return list(dict.fromkeys(tags))


def _special_holder(context: str, duration_text: str):
    after = re.search(
        re.escape(duration_text) + r"\s+for\s+([A-Z][A-Za-z0-9.&' -]{1,50}?)(?:[;,.)]|\s+and\b|\s+with\b|$)",
        context,
    )
    if after:
        return _norm(after.group(1)).strip(" ,.-")
    for match in re.finditer(r"\b([A-Z][A-Za-z0-9.&'-]{2,30}(?:\s+[A-Z][A-Za-z0-9.&'-]{2,30}){0,3})\s+Lock-?Up\b", context):
        value = _norm(match.group(1)).strip(" ,.-")
        if value.lower() not in {"lock up", "market standoff", "day", "days", "period", "the company"}:
            return value
    return None


def _direct_lockup_relation(context: str, duration_text: str) -> bool:
    """Require the duration itself to govern a holder transfer restriction."""
    lowered = context.lower()
    matched = duration_text.lower()
    if "lock-up" in matched or "lockup" in matched:
        return True

    unrelated = (
        "underwriters’ option", "underwriters' option", "over-allotment", "overallotment",
        "rule 144", "registration rights", "demand registration", "form s-1",
        "section 203", "business combination", "interested stockholder",
    )
    if any(term in lowered for term in unrelated):
        return False

    has_holder_restriction = bool(re.search(
        r"(?:agreed|agree|subject to)[^.;]{0,420}?(?:not to|will not|may not)[^.;]{0,260}?"
        r"(?:sell|transfer|dispose|offer|pledge|hedge)|"
        r"(?:will not|may not)[^.;]{0,260}?(?:sell|transfer|dispose|offer|pledge|hedge)",
        lowered,
        re.I,
    ))
    has_lockup_label = "lock-up" in lowered or "lockup" in lowered or "market standoff" in lowered
    if has_holder_restriction:
        return True
    if has_lockup_label and re.search(r"staggered|early\s+lock-?up\s+release|lock-?up\s+release", lowered):
        return True
    return False


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
        score += 6
    if any(tag in scope_tags for tag in ("substantially_all_holders", "all_other_holders")):
        score += 6
    if special_holder:
        score += 5
    if "registration rights" in lowered or "demand registration" in lowered:
        score -= 10
    if "form s-1" in lowered and not scope_tags and not special_holder:
        score -= 5
    issuer_only = (
        ("we have agreed" in lowered or "the company" in lowered)
        and not scope_tags and not special_holder
        and any(x in lowered for x in ("issue", "issuance", "registration statement"))
    )
    if issuer_only:
        score -= 8
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


def _tranche_evidence(context: str, duration_text: str):
    """Return an explicitly stated tranche percentage, or a remainder marker."""
    pos = context.lower().find(duration_text.lower())
    if pos < 0:
        return None, None
    before = context[max(0, pos - 320):pos]
    # Keep only the local comma-delimited phrase when possible so an earlier 25%
    # is not accidentally assigned to a later 'remainder' tranche.
    local = re.split(r"[,;]", before)[-1]
    if re.search(r"\b(?:the\s+)?(?:remainder|remaining)\b", local, re.I):
        return None, "remainder"
    matches = list(re.finditer(r"(\d{1,3}(?:\.\d+)?)\s*%", local))
    if matches:
        pct = float(matches[-1].group(1))
        if 0 < pct <= 100:
            return pct, "explicit_percent"
    # SEC prose may put the percentage just before a long share-description phrase.
    matches = list(re.finditer(r"(\d{1,3}(?:\.\d+)?)\s*%", before))
    if matches:
        pct = float(matches[-1].group(1))
        tail = before[matches[-1].end():]
        if len(tail) <= 220 and 0 < pct <= 100 and not re.search(r"\b(?:remainder|remaining)\b", tail, re.I):
            return pct, "explicit_percent"
    return None, None


def _covers_full_position(context: str, tags, tranche_percent):
    lowered = context.lower()
    if tranche_percent is not None:
        return True
    if set(tags) & {"substantially_all_holders", "all_other_holders"} and re.search(
        r"(?:lock-?up securities|their shares|all (?:of )?(?:their )?shares|all securities)",
        lowered,
    ):
        return True
    return False


def _complete_remainder_tranche(terms):
    """Infer only the arithmetic remainder of an otherwise explicit 100% schedule."""
    remainder = [term for term in terms if term.get("tranche_label") == "remainder" and term.get("tranche_percent") is None]
    if len(remainder) != 1:
        return
    explicit = [term.get("tranche_percent") for term in terms if term.get("tranche_percent") is not None]
    if not explicit:
        return
    total = sum(float(x) for x in explicit)
    missing = 100.0 - total
    if 0 < missing <= 100 and 99.999 <= total + missing <= 100.001:
        remainder[0]["tranche_percent"] = missing
        remainder[0]["tranche_label"] = "arithmetic_remainder"
        remainder[0]["covers_full_position"] = True


def _candidate_terms(text: str):
    terms = []
    for start, end, value, unit, matched in _duration_matches(text):
        context = _clause_context(text, start, end)
        if not _direct_lockup_relation(context, matched):
            continue
        tags = _scope_tags(context)
        special = _special_holder(context, matched)
        score = _score(context, tags, special)
        if score < 6:
            continue
        tranche_percent, tranche_label = _tranche_evidence(context, matched)
        terms.append({
            "duration_value": value,
            "duration_unit": unit,
            "duration_days": value if unit == "days" else None,
            "scope_tags": tags,
            "scope": _scope_label(tags),
            "special_holder": special,
            "tranche_percent": tranche_percent,
            "tranche_label": tranche_label,
            "covers_full_position": _covers_full_position(context, tags, tranche_percent),
            "has_staggered_releases": bool(
                tranche_percent is not None
                or tranche_label == "remainder"
                or re.search(r"staggered|early release|release(?:d|s)?\s+(?:of|for)|more than\s+\d+%", context, re.I)
            ),
            "score": score,
            "source_text": context,
        })
    unique = []
    seen = set()
    for term in sorted(terms, key=lambda t: (-t["score"], t["duration_unit"], t["duration_value"])):
        key = (
            term["duration_value"], term["duration_unit"], term.get("tranche_percent"),
            (term.get("special_holder") or "").lower(), tuple(term.get("scope_tags") or []),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(term)
    _complete_remainder_tranche(unique)
    return unique


def _primary_weight(term):
    tags = set(term.get("scope_tags") or [])
    breadth = 0
    if tags & {"substantially_all_holders", "all_other_holders"}:
        breadth += 20
    breadth += 6 * len(tags & {"directors", "executive_officers", "selling_stockholders"})
    breadth += 2 * len(tags & {"five_percent_holders", "certain_other_holders"})
    return term.get("score", 0) + breadth


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
    general = [t for t in terms if not t.get("special_holder") and t.get("scope_tags")]
    primary = max(general, key=_primary_weight, default=None)
    if primary is None:
        general = [t for t in terms if not t.get("special_holder")]
        primary = max(general, key=_primary_weight, default=None)
    if primary is None and len(terms) == 1:
        primary = terms[0]

    distinct_schedules = {
        (t["duration_value"], t["duration_unit"], t.get("tranche_percent"), t.get("special_holder"))
        for t in terms
    }
    structured = len(distinct_schedules) > 1 or any(t.get("has_staggered_releases") for t in terms)
    raw = primary.get("source_text") if primary else (terms[0].get("source_text") if terms else None)
    confidence = "High" if primary and _primary_weight(primary) >= 16 else ("Medium" if primary else "Unresolved")
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
