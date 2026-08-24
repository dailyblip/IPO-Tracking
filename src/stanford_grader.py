"""
stanford_grader.py

For each person on the beneficial ownership grid:
1. Skip legal entities / combined affiliate rows that are not people.
2. Check the bio text extracted from the filing's Management section for a direct Stanford mention.
3. Run targeted public-web searches when the filing is silent.
4. For official issuer or Stanford results, inspect the actual public page rather than relying only on a search snippet.
5. Confirm only exact-person + Stanford University matches; use the LLM only for ambiguous evidence.
"""

from html import unescape
import json
import os
import re
import time
from urllib.parse import urlparse

import requests

SEARCH_API_URL = "https://api.search.brave.com/res/v1/web/search"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
MAX_SEARCH_ATTEMPTS = 2
REQUEST_DELAY_SECONDS = 0.5

DIRECT_MENTION_PATTERN = re.compile(r"\bstanford\b", re.IGNORECASE)
STANFORD_UNIVERSITY_PATTERN = re.compile(r"\bstanford\s+university\b", re.IGNORECASE)
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


class StanfordGraderError(Exception):
    pass


def _get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise StanfordGraderError(f"{name} environment variable is not set.")
    return value


def _anthropic_model() -> str:
    return os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL).strip() or DEFAULT_ANTHROPIC_MODEL


def is_likely_organization(person_name: str) -> bool:
    name = " ".join(str(person_name or "").split())
    if not name:
        return False
    if ORGANIZATION_PATTERN.search(name):
        return True
    return bool(re.search(r"\band\s+(?:related\s+)?affiliates?\b", name, re.IGNORECASE))


def check_bio_for_stanford(bio_text: str) -> dict | None:
    if not bio_text or not DIRECT_MENTION_PATTERN.search(bio_text):
        return None
    sentences = re.split(r"(?<=[.])\s+", bio_text)
    matching_sentence = next((s for s in sentences if DIRECT_MENTION_PATTERN.search(s)), bio_text[:300])
    return {
        "grade": 5,
        "justification": f'Directly stated in filing bio: "{matching_sentence.strip()}"',
        "source": "filing_bio",
    }


def brave_search(query: str) -> list:
    api_key = _get_env("BRAVE_SEARCH_API_KEY")
    response = requests.get(
        SEARCH_API_URL,
        headers={"Accept": "application/json", "X-Subscription-Token": api_key},
        params={"q": query, "count": 5},
        timeout=15,
    )
    response.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    data = response.json()
    return [
        {"title": item.get("title", ""), "snippet": item.get("description", ""), "link": item.get("url", "")}
        for item in data.get("web", {}).get("results", [])
    ]


google_search = brave_search


def run_search_fallback(person_name: str, company_name: str) -> list:
    all_results = []
    queries = [
        f'"{person_name}" "Stanford University"',
        f'"{person_name}" Stanford "{company_name}"',
    ]
    for i, query in enumerate(queries[:MAX_SEARCH_ATTEMPTS]):
        try:
            all_results.extend(brave_search(query))
        except requests.exceptions.RequestException as exc:
            print(f"[stanford_grader] Search attempt {i + 1} failed: {exc}")
    return all_results


def _normalized_words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(value or "").casefold())


def _normalized_phrase(value: str) -> str:
    return " ".join(_normalized_words(value))


def _company_identity_tokens(company_name: str) -> list[str]:
    return [token for token in _normalized_words(company_name) if len(token) >= 4 and token not in CORPORATE_NAME_WORDS]


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
    company_tokens = _company_identity_tokens(company_name)
    if company_tokens and any(token in hostname for token in company_tokens):
        return hostname
    return None


def _strong_official_search_match(person_name: str, company_name: str, search_results: list):
    person_phrase = _normalized_phrase(person_name)
    if not person_phrase:
        return None
    for result in search_results:
        if not isinstance(result, dict):
            continue
        evidence = f"{result.get('title') or ''} {result.get('snippet') or ''}"
        if person_phrase not in _normalized_phrase(evidence):
            continue
        if not STANFORD_UNIVERSITY_PATTERN.search(evidence):
            continue
        if not _authoritative_hostname(result.get("link", ""), company_name):
            continue
        return result
    return None


def _html_to_text(value: str) -> str:
    text = re.sub(r"(?is)<(?:script|style|noscript)\b.*?</(?:script|style|noscript)>", " ", str(value or ""))
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return " ".join(unescape(text).split())


def _official_page_match(person_name: str, company_name: str, search_results: list):
    """Inspect authoritative result pages when snippets omit the affiliation.

    A page may confirm only when it is HTTPS, is on Stanford's domain or a hostname
    tied to the issuer name, and the fetched page contains both the exact normalized
    person name and the phrase 'Stanford University'. This deliberately fails closed.
    """
    person_phrase = _normalized_phrase(person_name)
    if not person_phrase:
        return None

    seen = set()
    for result in search_results:
        if not isinstance(result, dict):
            continue
        link = str(result.get("link") or "")
        if not link or link in seen or not _authoritative_hostname(link, company_name):
            continue
        seen.add(link)
        try:
            response = requests.get(
                link,
                headers={"User-Agent": "ResearchMonitor/1.0 public-affiliation-verification"},
                timeout=15,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            print(f"[stanford_grader] Official page fetch failed for {link}: {exc}")
            continue
        page_text = _html_to_text(response.text)
        if person_phrase not in _normalized_phrase(page_text):
            continue
        if not STANFORD_UNIVERSITY_PATTERN.search(page_text):
            continue
        return {"link": link, "title": result.get("title", ""), "snippet": result.get("snippet", "")}
    return None


def _search_has_stanford_evidence(search_results: list) -> bool:
    for result in search_results:
        if not isinstance(result, dict):
            continue
        evidence = " ".join(str(result.get(field, "")) for field in ("title", "snippet", "link"))
        if DIRECT_MENTION_PATTERN.search(evidence):
            return True
    return False


def _build_grading_prompt(person_name: str, company_name: str, title: str, bio_text: str, search_results: list) -> str:
    search_block = "\n".join(
        f'- "{r["title"]}" - {r["snippet"]} ({r["link"]})' for r in search_results
    ) or "(no search results found)"
    return f"""You are assessing whether there is public evidence that a specific individual has a Stanford University affiliation (student, alumnus, faculty, researcher, or similar).

Person: {person_name}
Role/context: {title or "unknown"} at {company_name}

Filing bio text (may be empty):
{bio_text or "(none available)"}

Web search results:
{search_block}

Score their Stanford affiliation confidence from 0-5:
- 5 = Directly and unambiguously confirmed
- 3-4 = Reasonably confident with corroboration beyond name alone
- 1-2 = Weak or uncertain signal
- 0 = No relevant evidence or likely name collision

Do not give a score above 2 based on name matching alone. Require at least one corroborating detail tying the Stanford reference to this specific person.

Respond with ONLY a JSON object:
{{"grade": <integer 0-5>, "justification": "<one sentence>"}}"""


def grade_via_llm(person_name: str, company_name: str, title: str, bio_text: str, search_results: list) -> dict:
    api_key = _get_env("ANTHROPIC_API_KEY")
    prompt = _build_grading_prompt(person_name, company_name, title, bio_text, search_results)
    response = requests.post(
        ANTHROPIC_API_URL,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": _anthropic_model(), "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]},
        timeout=30,
    )
    if not response.ok:
        detail = response.text[:500].strip()
        raise StanfordGraderError(
            f"Anthropic grading request failed ({response.status_code})" + (f": {detail}" if detail else "")
        )
    data = response.json()
    text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(cleaned)
        grade = int(parsed["grade"])
        if not 0 <= grade <= 5:
            raise ValueError("grade outside 0-5")
        return {"grade": grade, "justification": str(parsed["justification"]), "source": "llm_judgment"}
    except (json.JSONDecodeError, KeyError, ValueError):
        return {
            "grade": 0,
            "justification": f"Grading call returned unparseable response; defaulted to 0. Raw: {text[:200]}",
            "source": "parse_error",
        }


def grade_stanford_affiliation(person_name: str, company_name: str, title: str = "", bio_text: str = "") -> dict:
    if is_likely_organization(person_name):
        return {
            "grade": 0,
            "justification": "Beneficial-owner label appears to be an organization or combined affiliate row; person-level Stanford grading skipped.",
            "source": "non_person_holder",
        }

    direct_result = check_bio_for_stanford(bio_text)
    if direct_result:
        return direct_result

    search_results = run_search_fallback(person_name, company_name)
    strong_match = _strong_official_search_match(person_name, company_name, search_results)
    if strong_match:
        return {
            "grade": 5,
            "justification": "Exact person match with Stanford University affiliation on an official public source: " + str(strong_match.get("link", "")),
            "source": "official_public_bio",
        }

    page_match = _official_page_match(person_name, company_name, search_results)
    if page_match:
        return {
            "grade": 5,
            "justification": "Exact person and Stanford University affiliation verified on an authoritative public page: " + str(page_match.get("link", "")),
            "source": "official_page_content",
        }

    if not _search_has_stanford_evidence(search_results):
        return {
            "grade": 0,
            "justification": "No public Stanford-affiliation evidence found in the filing bio, search results, or authoritative result pages.",
            "source": "no_public_evidence",
        }
    return grade_via_llm(person_name, company_name, title, bio_text, search_results)


if __name__ == "__main__":
    import sys
    name_arg = sys.argv[1] if len(sys.argv) > 1 else "Jane Smith"
    company_arg = sys.argv[2] if len(sys.argv) > 2 else "Example Corp"
    print(json.dumps(grade_stanford_affiliation(name_arg, company_arg), indent=2))
