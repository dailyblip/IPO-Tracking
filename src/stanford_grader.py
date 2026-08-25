"""
stanford_grader.py

Public-evidence Stanford affiliation grader for Research Monitor.

Order of operations:
1. Skip legal entities / aggregate affiliate rows.
2. Confirm explicit Stanford University mentions in person-specific SEC filing context.
3. If filing evidence is silent, use the OpenAI Responses API with built-in web search.
4. Fail closed: only unambiguous person-level evidence can receive grade 5.

Requires:
- OPENAI_API_KEY
Optional:
- OPENAI_STANFORD_MODEL (defaults to gpt-5.6-luna)
"""

import json
import os
import re

import requests

OPENAI_RESPONSES_API_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"

DIRECT_MENTION_PATTERN = re.compile(r"\bstanford\b", re.IGNORECASE)
STANFORD_UNIVERSITY_PATTERN = re.compile(r"\bstanford\s+university\b", re.IGNORECASE)
SEC_FOOTNOTE_SUFFIX_PATTERN = re.compile(r"(?:\s*\(\d+[a-z]?\))+$", re.IGNORECASE)
ORGANIZATION_PATTERN = re.compile(
    r"\b(?:entities? affiliated|affiliates?|asset management|capital|ventures?|partners?|"
    r"funds?|holdings?|management|trust|foundation|company|corporation|corp\.?|inc\.?|"
    r"llc|l\.l\.c\.?|lp|l\.p\.?|ltd\.?|limited|master fund|biopartners)\b",
    re.IGNORECASE,
)


class StanfordGraderError(Exception):
    pass


def _get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise StanfordGraderError(f"{name} environment variable is not set.")
    return value


def _openai_model() -> str:
    return os.environ.get("OPENAI_STANFORD_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL


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


def _person_specific_filing_context(person_name: str, bio_text: str, radius: int = 2500) -> str:
    """Return filing text near the exact person when Stanford University appears nearby."""
    text = " ".join(str(bio_text or "").split())
    if not text or not STANFORD_UNIVERSITY_PATTERN.search(text):
        return ""

    clean_name = _clean_person_name(person_name)
    if not clean_name:
        return ""

    if len(text) <= 4000:
        if _normalized_phrase(clean_name) in _normalized_phrase(text) or len(text) <= 1200:
            return text

    tokens = _normalized_words(clean_name)
    if not tokens:
        return ""
    pattern = re.compile(r"\b" + r"\W+".join(re.escape(token) for token in tokens) + r"\b", re.I)
    for match in pattern.finditer(text):
        start = max(0, match.start() - radius)
        end = min(len(text), match.end() + radius)
        window = text[start:end]
        if STANFORD_UNIVERSITY_PATTERN.search(window):
            return window
    return ""


def check_bio_for_stanford(bio_text: str, person_name: str = "") -> dict | None:
    context = _person_specific_filing_context(person_name, bio_text) if person_name else str(bio_text or "")
    if not context or not STANFORD_UNIVERSITY_PATTERN.search(context):
        return None

    sentences = re.split(r"(?<=[.!?])\s+", context)
    matching_sentence = next(
        (sentence for sentence in sentences if STANFORD_UNIVERSITY_PATTERN.search(sentence)),
        context[:400],
    )
    return {
        "grade": 5,
        "justification": (
            f'Direct Stanford University affiliation stated in SEC filing context for '
            f'{_clean_person_name(person_name) or "holder"}: "{matching_sentence.strip()}"'
        ),
        "source": "filing_bio",
    }


def _build_openai_prompt(person_name: str, company_name: str, title: str, bio_text: str) -> str:
    clean_name = _clean_person_name(person_name)
    filing_excerpt = " ".join(str(bio_text or "").split())[:6000]
    return f"""Research whether this exact person has a public affiliation with Stanford University.

Person: {clean_name}
Current/IPO company: {company_name}
Role/context: {title or "unknown"}

SEC filing context, if available:
{filing_excerpt or "(none)"}

Use public web search. Prioritize, in order:
1. stanford.edu
2. the issuer/company's official website
3. SEC filings
4. other reputable public sources only as corroboration.

Identity matching is critical. Do not treat a same-name person as a match without corroborating role/company/biographical details.

Return ONLY one JSON object with exactly these keys:
{{
  "grade": <integer 0-5>,
  "confirmed": <true or false>,
  "justification": "<concise factual explanation>",
  "source_url": "<best supporting public URL or empty string>"
}}

Scoring:
5 = direct, unambiguous Stanford University affiliation for this exact person.
3-4 = credible but not definitive.
1-2 = weak/ambiguous.
0 = no relevant evidence or likely mismatch.

Set confirmed=true ONLY when grade=5 and the exact-person match is unambiguous.
"""


def _extract_response_text(data: dict) -> str:
    chunks = []
    for item in data.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for block in item.get("content", []):
            if isinstance(block, dict) and block.get("type") == "output_text":
                chunks.append(str(block.get("text", "")))
    return "".join(chunks).strip()


def grade_via_llm(
    person_name: str,
    company_name: str,
    title: str,
    bio_text: str,
    search_results: list | None = None,
) -> dict:
    """Use OpenAI Responses API + built-in web search for public affiliation research."""
    api_key = _get_env("OPENAI_API_KEY")
    prompt = _build_openai_prompt(person_name, company_name, title, bio_text)

    response = requests.post(
        OPENAI_RESPONSES_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": _openai_model(),
            "input": prompt,
            "tools": [{"type": "web_search"}],
            "max_output_tokens": 300,
        },
        timeout=60,
    )
    if not response.ok:
        detail = response.text[:500].strip()
        raise StanfordGraderError(
            f"OpenAI Stanford research request failed ({response.status_code})"
            + (f": {detail}" if detail else "")
        )

    text = _extract_response_text(response.json())
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(cleaned)
        grade = int(parsed["grade"])
        confirmed = bool(parsed["confirmed"])
        justification = str(parsed["justification"]).strip()
        source_url = str(parsed.get("source_url") or "").strip()

        if not 0 <= grade <= 5:
            raise ValueError("grade outside 0-5")
        if confirmed and grade != 5:
            raise ValueError("confirmed requires grade 5")
        if grade == 5 and not confirmed:
            grade = 4

        return {
            "grade": grade,
            "justification": justification,
            "source": "openai_web_research",
            "source_url": source_url,
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return {
            "grade": 0,
            "justification": f"OpenAI research returned an invalid grading payload; defaulted to 0. Raw: {text[:200]}",
            "source": "parse_error",
            "source_url": "",
        }


# Backward-compatible names retained so older imports do not fail.
def brave_search(query: str) -> list:
    raise StanfordGraderError("Brave Search is no longer used; Stanford research now uses OPENAI_API_KEY.")


google_search = brave_search


def run_search_fallback(person_name: str, company_name: str) -> list:
    """Legacy compatibility shim. Search is performed inside the OpenAI Responses call."""
    return []


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
        }

    direct_result = check_bio_for_stanford(bio_text, person_name=person_name)
    if direct_result:
        return direct_result

    # No Brave dependency: one OpenAI Responses request performs both public search and grading.
    return grade_via_llm(_clean_person_name(person_name), company_name, title, bio_text, [])


if __name__ == "__main__":
    import sys

    name_arg = sys.argv[1] if len(sys.argv) > 1 else "Jane Smith"
    company_arg = sys.argv[2] if len(sys.argv) > 2 else "Example Corp"
    print(json.dumps(grade_stanford_affiliation(name_arg, company_arg), indent=2))
