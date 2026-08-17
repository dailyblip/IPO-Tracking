"""
stanford_grader.py

For each person on the beneficial ownership grid:
1. Check the bio text extracted from the filing's Management section
   for a direct Stanford mention -> grade 5, no search needed.
2. If silent, run up to two web searches (Brave Search API) looking
   for a public Stanford connection.
3. Only when search returns Stanford-related evidence, score 0-5 using
   an LLM judgment call over the combined evidence. This avoids paid
   grading calls when there is nothing public to evaluate.

Requires:
- BRAVE_SEARCH_API_KEY
- ANTHROPIC_API_KEY (only when public Stanford evidence exists)
Optional:
- ANTHROPIC_MODEL (defaults to the documented Claude Sonnet 4 API ID)
"""

import json
import os
import re
import time

import requests

SEARCH_API_URL = "https://api.search.brave.com/res/v1/web/search"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

MAX_SEARCH_ATTEMPTS = 2
REQUEST_DELAY_SECONDS = 0.5

DIRECT_MENTION_PATTERN = re.compile(r"\bstanford\b", re.IGNORECASE)


class StanfordGraderError(Exception):
    pass


def _get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise StanfordGraderError(f"{name} environment variable is not set.")
    return value


def _anthropic_model() -> str:
    """Return configured model, falling back to a documented API model ID."""
    return os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL).strip() or DEFAULT_ANTHROPIC_MODEL


def check_bio_for_stanford(bio_text: str) -> dict:
    """Return grade 5 for a direct Stanford mention in filing bio text."""
    if not bio_text or not DIRECT_MENTION_PATTERN.search(bio_text):
        return None

    sentences = re.split(r"(?<=[.])\s+", bio_text)
    matching_sentence = next(
        (s for s in sentences if DIRECT_MENTION_PATTERN.search(s)), bio_text[:300]
    )

    return {
        "grade": 5,
        "justification": f"Directly stated in filing bio: \"{matching_sentence.strip()}\"",
        "source": "filing_bio",
    }


def brave_search(query: str) -> list:
    """Run a single query against the Brave Search API."""
    api_key = _get_env("BRAVE_SEARCH_API_KEY")
    headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
    params = {"q": query, "count": 5}
    response = requests.get(SEARCH_API_URL, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)

    data = response.json()
    return [
        {
            "title": item.get("title", ""),
            "snippet": item.get("description", ""),
            "link": item.get("url", ""),
        }
        for item in data.get("web", {}).get("results", [])
    ]


# Backward-compatible alias retained for earlier references.
google_search = brave_search


def run_search_fallback(person_name: str, company_name: str) -> list:
    """Run at most two targeted public-web searches."""
    all_results = []
    queries = [
        f'"{person_name}" "{company_name}" Stanford',
        f'"{person_name}" bio Stanford',
    ]

    for i, query in enumerate(queries[:MAX_SEARCH_ATTEMPTS]):
        try:
            all_results.extend(brave_search(query))
        except requests.exceptions.RequestException as e:
            print(f"[stanford_grader] Search attempt {i + 1} failed: {e}")

    return all_results


def _search_has_stanford_evidence(search_results: list) -> bool:
    """Return True only when retrieved public results actually mention Stanford."""
    for result in search_results:
        if not isinstance(result, dict):
            continue
        evidence = " ".join(
            str(result.get(field, "")) for field in ("title", "snippet", "link")
        )
        if DIRECT_MENTION_PATTERN.search(evidence):
            return True
    return False


def _build_grading_prompt(person_name: str, company_name: str, title: str,
                           bio_text: str, search_results: list) -> str:
    search_block = "\n".join(
        f"- \"{r['title']}\" - {r['snippet']} ({r['link']})" for r in search_results
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


def grade_via_llm(person_name: str, company_name: str, title: str,
                   bio_text: str, search_results: list) -> dict:
    """Ask Claude to weigh ambiguous public affiliation evidence."""
    api_key = _get_env("ANTHROPIC_API_KEY")
    prompt = _build_grading_prompt(person_name, company_name, title, bio_text, search_results)

    response = requests.post(
        ANTHROPIC_API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": _anthropic_model(),
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )

    if not response.ok:
        detail = response.text[:500].strip()
        raise StanfordGraderError(
            f"Anthropic grading request failed ({response.status_code})"
            + (f": {detail}" if detail else "")
        )

    data = response.json()
    text = "".join(
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text"
    )
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        parsed = json.loads(cleaned)
        grade = int(parsed["grade"])
        if not 0 <= grade <= 5:
            raise ValueError("grade outside 0-5")
        return {
            "grade": grade,
            "justification": str(parsed["justification"]),
            "source": "llm_judgment",
        }
    except (json.JSONDecodeError, KeyError, ValueError):
        return {
            "grade": 0,
            "justification": f"Grading call returned unparseable response; defaulted to 0. Raw: {text[:200]}",
            "source": "parse_error",
        }


def grade_stanford_affiliation(person_name: str, company_name: str,
                                title: str = "", bio_text: str = "") -> dict:
    """Return {grade, justification, source} from public evidence only."""
    direct_result = check_bio_for_stanford(bio_text)
    if direct_result:
        return direct_result

    search_results = run_search_fallback(person_name, company_name)
    if not _search_has_stanford_evidence(search_results):
        return {
            "grade": 0,
            "justification": "No public Stanford-affiliation evidence found in the filing bio or search results.",
            "source": "no_public_evidence",
        }

    return grade_via_llm(person_name, company_name, title, bio_text, search_results)


if __name__ == "__main__":
    import sys

    name_arg = sys.argv[1] if len(sys.argv) > 1 else "Jane Smith"
    company_arg = sys.argv[2] if len(sys.argv) > 2 else "Example Corp"
    result = grade_stanford_affiliation(name_arg, company_arg)
    print(json.dumps(result, indent=2))
