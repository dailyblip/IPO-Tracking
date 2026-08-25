"""
Stanford affiliation grading for beneficial owners.

Release rule: a holder is confirmed only when an exact-person Stanford University
connection is stated in person-specific SEC filing context or independently verified
on an authoritative public Stanford, issuer, SEC, or official exchange page.

When filing evidence is silent, OpenAI Responses API web search is used for discovery
and identity assessment. A model result never becomes grade 5 by itself: the returned
source URL must pass deterministic page verification before the dashboard may apply
Cardinal-red highlighting.
"""

from html import unescape
import json
import os
import re
from urllib.parse import urlparse

import requests

OPENAI_RESPONSES_API_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"

STANFORD_UNIVERSITY_PATTERN = re.compile(r"\bstanford\s+university\b", re.IGNORECASE)
SEC_FOOTNOTE_SUFFIX_PATTERN = re.compile(r"(?:\s*\(\d+[a-z]?\))+$", re.IGNORECASE)
ORGANIZATION_PATTERN = re.compile(
    r"\b(?:entities? affiliated|affiliates?|asset management|capital|ventures?|partners?|"
    r"funds?|holdings?|management|trust|foundation|company|corporation|corp\.?|inc\.?|"
    r"llc|l\.l\.c\.?|lp|l\.p\.?|ltd\.?|limited|master fund|biopartners)\b",
    re.IGNORECASE,
)
CORPORATE_NAME_WORDS = {
    "inc", "incorporated", "corp", "corporation", "company", "co", "holdings",
    "therapeutics", "biotherapeutics", "pharmaceuticals", "pharma", "biosciences",
    "biotech", "technologies", "technology", "group", "limited", "ltd", "plc",
}
OFFICIAL_PUBLIC_HOSTS = {
    "sec.gov", "www.sec.gov", "nasdaq.com", "www.nasdaq.com", "nyse.com", "www.nyse.com",
}


class StanfordGraderError(Exception):
    pass


def _get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise StanfordGraderError(f"{name} environment variable is not set.")
    return value


def _openai_model() -> str:
    return os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL


def _clean_person_name(person_name: str) -> str:
    name = " ".join(str(person_name or "").split())
    return SEC_FOOTNOTE_SUFFIX_PATTERN.sub("", name).strip()


def is_likely_organization(person_name: str) -> bool:
    name = _clean_person_name(person_name)
    if not name:
        return False
    if ORGANIZATION_PATTERN.search(name):
        return True
    return bool(re.search(r"\band\s+(?:related\s+)?affiliates?\b", name, re.IGNORECASE))


def _normalized_words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(value or "").casefold())


def _normalized_phrase(value: str) -> str:
    return " ".join(_normalized_words(value))


def _person_pattern(person_name: str):
    tokens = _normalized_words(_clean_person_name(person_name))
    if not tokens:
        return None
    return re.compile(r"\b" + r"\W+".join(re.escape(token) for token in tokens) + r"\b", re.I)


def _person_specific_filing_context(person_name: str, bio_text: str) -> str:
    """Return only a sentence explicitly tying this exact holder to Stanford University.

    main.py can pass a broad Management-section fallback when a person-specific bio was
    not split successfully. Requiring the exact full holder name and Stanford University
    in the same sentence prevents a nearby executive's education from confirming the
    wrong beneficial owner. Person-specific parsed bios are separately flagged by main.py.
    """
    text = " ".join(str(bio_text or "").split())
    if not text or not STANFORD_UNIVERSITY_PATTERN.search(text):
        return ""
    pattern = _person_pattern(person_name)
    if pattern is None:
        return ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if pattern.search(sentence) and STANFORD_UNIVERSITY_PATTERN.search(sentence):
            return sentence
    return ""


def check_bio_for_stanford(bio_text: str, person_name: str = "") -> dict | None:
    context = _person_specific_filing_context(person_name, bio_text)
    if not context:
        return None
    return {
        "grade": 5,
        "justification": (
            f'Directly stated in SEC filing context for {_clean_person_name(person_name)}: '
            f'"{context.strip()}"'
        ),
        "source": "filing_bio",
        "source_url": "",
    }


def _company_identity_tokens(company_name: str) -> list[str]:
    return [
        token for token in _normalized_words(company_name)
        if len(token) >= 4 and token not in CORPORATE_NAME_WORDS
    ]


def _authoritative_hostname(link: str, company_name: str) -> str | None:
    try:
        parsed = urlparse(str(link or ""))
    except ValueError:
        return None
    if parsed.scheme != "https":
        return None
    hostname = (parsed.hostname or "").casefold()
    if not hostname:
        return None
    if hostname == "stanford.edu" or hostname.endswith(".stanford.edu"):
        return hostname
    if hostname in OFFICIAL_PUBLIC_HOSTS or hostname.endswith(".sec.gov"):
        return hostname
    company_tokens = _company_identity_tokens(company_name)
    if company_tokens and any(token in hostname for token in company_tokens):
        return hostname
    return None


def _html_to_text(value: str) -> str:
    text = re.sub(
        r"(?is)<(?:script|style|noscript)\b.*?</(?:script|style|noscript)>",
        " ",
        str(value or ""),
    )
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return " ".join(unescape(text).split())


def _verify_authoritative_source(person_name: str, company_name: str, link: str) -> dict | None:
    """Fetch a claimed source and deterministically verify exact person + Stanford University."""
    hostname = _authoritative_hostname(link, company_name)
    if not hostname:
        return None
    try:
        response = requests.get(
            link,
            headers={"User-Agent": "ResearchMonitor/1.0 public-affiliation-verification"},
            timeout=20,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print(f"[stanford_grader] Authoritative source fetch failed for {link}: {exc}")
        return None

    page_text = _html_to_text(response.text)
    if not STANFORD_UNIVERSITY_PATTERN.search(page_text):
        return None
    person_phrase = _normalized_phrase(_clean_person_name(person_name))
    if not person_phrase or person_phrase not in _normalized_phrase(page_text):
        return None
    return {"link": link, "hostname": hostname}


def _build_openai_prompt(person_name: str, company_name: str, title: str, bio_text: str) -> str:
    filing_context = " ".join(str(bio_text or "").split())[:1800]
    return f"""Research whether this specific beneficial owner has a confirmed Stanford University affiliation.

Person: {_clean_person_name(person_name)}
Company: {company_name}
Role/context: {title or "unknown"}
SEC filing context (identity corroboration only; may be empty): {filing_context or "(none)"}

Use public web search. Prefer, in order: Stanford University pages, the issuer's official site, SEC filings, and official exchange pages. Distinguish the exact person from namesakes using company, role, biography, or other corroborating identity facts.

Scoring:
- 5: explicit, unambiguous Stanford University affiliation for this exact person with a reliable source URL.
- 3-4: plausible evidence but identity/source is not strong enough for confirmation.
- 1-2: weak or name-only signal.
- 0: no reliable relevant evidence.

Never score 5 from a name match alone. Never infer education or affiliation. If evidence conflicts or identity cannot be resolved, do not score 5. Return the strongest single source URL supporting the result, or an empty string if none."""


def _response_output_text(data: dict) -> str:
    chunks = []
    for item in data.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                chunks.append(str(content.get("text") or ""))
    return "".join(chunks).strip()


def research_via_openai(person_name: str, company_name: str, title: str = "", bio_text: str = "") -> dict:
    """Use OpenAI Responses API + web search to discover public affiliation evidence."""
    api_key = _get_env("OPENAI_API_KEY")
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "grade": {"type": "integer", "minimum": 0, "maximum": 5},
            "justification": {"type": "string"},
            "source_url": {"type": "string"},
            "source_title": {"type": "string"},
        },
        "required": ["grade", "justification", "source_url", "source_title"],
    }
    response = requests.post(
        OPENAI_RESPONSES_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": _openai_model(),
            "input": _build_openai_prompt(person_name, company_name, title, bio_text),
            "tools": [{"type": "web_search"}],
            "tool_choice": "required",
            "include": ["web_search_call.action.sources"],
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "stanford_affiliation_research",
                    "strict": True,
                    "schema": schema,
                }
            },
        },
        timeout=60,
    )
    if not response.ok:
        detail = response.text[:500].strip()
        raise StanfordGraderError(
            f"OpenAI research request failed ({response.status_code})"
            + (f": {detail}" if detail else "")
        )

    text = _response_output_text(response.json())
    try:
        parsed = json.loads(text)
        grade = int(parsed["grade"])
        if not 0 <= grade <= 5:
            raise ValueError("grade outside 0-5")
        source_url = str(parsed.get("source_url") or "").strip()
        return {
            "grade": grade,
            "justification": str(parsed.get("justification") or "").strip(),
            "source_url": source_url,
            "source_title": str(parsed.get("source_title") or "").strip(),
            "source": "openai_web_research",
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return {
            "grade": 0,
            "justification": f"OpenAI returned an invalid structured result; defaulted to 0. Raw: {text[:200]}",
            "source_url": "",
            "source": "parse_error",
        }


def grade_via_llm(person_name: str, company_name: str, title: str, bio_text: str, search_results=None) -> dict:
    """Backward-compatible wrapper for older callers/tests."""
    return research_via_openai(person_name, company_name, title, bio_text)


def grade_stanford_affiliation(
    person_name: str,
    company_name: str,
    title: str = "",
    bio_text: str = "",
) -> dict:
    if is_likely_organization(person_name):
        return {
            "grade": 0,
            "justification": (
                "Beneficial-owner label appears to be an organization or combined affiliate row; "
                "person-level Stanford grading skipped."
            ),
            "source": "non_person_holder",
            "source_url": "",
        }

    direct_result = check_bio_for_stanford(bio_text, person_name=person_name)
    if direct_result:
        return direct_result

    result = research_via_openai(
        _clean_person_name(person_name),
        company_name,
        title=title,
        bio_text=bio_text,
    )
    if result.get("grade") != 5:
        return result

    source_url = str(result.get("source_url") or "").strip()
    verified = _verify_authoritative_source(person_name, company_name, source_url)
    if verified:
        return {
            "grade": 5,
            "justification": (
                f"Exact person and Stanford University affiliation verified on authoritative public source: {source_url}"
            ),
            "source": "openai_verified_official",
            "source_url": source_url,
        }

    return {
        "grade": 4,
        "justification": (
            "OpenAI found a potential Stanford affiliation, but the cited source could not be "
            "independently verified as an authoritative exact-person source; not confirmed."
        ),
        "source": "openai_unverified",
        "source_url": source_url,
    }


if __name__ == "__main__":
    import sys

    name_arg = sys.argv[1] if len(sys.argv) > 1 else "Jane Smith"
    company_arg = sys.argv[2] if len(sys.argv) > 2 else "Example Corp"
    print(json.dumps(grade_stanford_affiliation(name_arg, company_arg), indent=2))
