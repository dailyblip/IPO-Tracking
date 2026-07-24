"""
stanford_grader.py

For each person on the beneficial ownership grid:
1. Check the bio text extracted from the filing's Management section
   for a direct Stanford mention -> grade 5, no search needed.
2. If silent, run up to two web searches (Brave Search API) looking
   for a public Stanford connection.
3. Score 0-5 using an LLM judgment call over the combined evidence,
   requiring at least one corroborating detail (title, company, or
   location) beyond just the name matching - guards against common-name
   false positives.

Requires:
- BRAVE_SEARCH_API_KEY (brave.com/search/api - a single API key, no
  separate search-engine ID needed, unlike the old Google Custom
  Search setup)
- ANTHROPIC_API_KEY (used for the grading judgment call itself)
"""

import os
import re
import json
import time
import requests

SEARCH_API_URL = "https://api.search.brave.com/res/v1/web/search"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"

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


def check_bio_for_stanford(bio_text: str) -> dict:
    """
    Direct check against filing bio text. Returns a grade-5 result
    if "Stanford" appears, along with the matching sentence for context.
    Returns None if no mention is found (caller should proceed to search).
    """
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
    """
    Run a single query against the Brave Search API.
    Returns a list of {title, snippet, link} dicts (top results only).
    """
    api_key = _get_env("BRAVE_SEARCH_API_KEY")

    headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
    params = {"q": query, "count": 5}
    response = requests.get(SEARCH_API_URL, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)

    data = response.json()
    results = []
    for item in data.get("web", {}).get("results", []):
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("description", ""),
            "link": item.get("url", ""),
        })
    return results


# Kept as an alias so any earlier references (or notes) using the old
# name still resolve correctly.
google_search = brave_search


def run_search_fallback(person_name: str, company_name: str) -> list:
    """
    Run the two-attempt search fallback. First query pairs name with
    company (highest signal for corroboration); second is a looser
    "bio Stanford" query. Stops early if the first query already
    returns clearly relevant results, but always tries at most two.
    """
    all_results = []

    queries = [
        f'"{person_name}" "{company_name}" Stanford',
        f'"{person_name}" bio Stanford',
    ]

    for i, query in enumerate(queries[:MAX_SEARCH_ATTEMPTS]):
        try:
            results = brave_search(query)
            all_results.extend(results)
        except requests.exceptions.RequestException as e:
            print(f"[stanford_grader] Search attempt {i + 1} failed: {e}")
            continue

    return all_results


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
- 5 = Directly and unambiguously confirmed (explicit statement of degree/role at Stanford, clearly matching this specific person)
- 3-4 = Reasonably confident, corroborated by at least one matching detail beyond the name alone (same company, same professional role, same general time period, etc.)
- 1-2 = Weak or uncertain signal (name matches something Stanford-related but corroborating details are thin, ambiguous, or the match could plausibly be a different person)
- 0 = No relevant evidence found, or evidence points to a clear name collision with a different person

Important: do not give a score above 2 based on name matching alone. Require at least one corroborating detail (title, company, location, or time period) tying the Stanford reference to this specific person.

Respond with ONLY a JSON object, no other text:
{{"grade": <integer 0-5>, "justification": "<one sentence explaining the score and what corroboration, if any, was found>"}}"""


def grade_via_llm(person_name: str, company_name: str, title: str,
                   bio_text: str, search_results: list) -> dict:
    """
    Send the combined evidence (bio text + search results) to Claude for
    a judgment call, since this requires weighing ambiguous corroborating
    detail rather than simple keyword matching.
    """
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
            "model": ANTHROPIC_MODEL,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    text = "".join(
        block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
    )
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        parsed = json.loads(cleaned)
        return {
            "grade": int(parsed["grade"]),
            "justification": parsed["justification"],
            "source": "llm_judgment",
        }
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return {
            "grade": 0,
            "justification": f"Grading call returned unparseable response; defaulted to 0. Raw: {text[:200]}",
            "source": "parse_error",
        }


def grade_stanford_affiliation(person_name: str, company_name: str,
                                title: str = "", bio_text: str = "") -> dict:
    """
    Top-level entry point. Returns {"grade": int, "justification": str, "source": str}.
    """
    direct_result = check_bio_for_stanford(bio_text)
    if direct_result:
        return direct_result

    search_results = run_search_fallback(person_name, company_name)
    return grade_via_llm(person_name, company_name, title, bio_text, search_results)


if __name__ == "__main__":
    # Quick manual test: python stanford_grader.py "Jane Smith" "Example Corp"
    import sys

    name_arg = sys.argv[1] if len(sys.argv) > 1 else "Jane Smith"
    company_arg = sys.argv[2] if len(sys.argv) > 2 else "Example Corp"

    result = grade_stanford_affiliation(name_arg, company_arg)
    print(json.dumps(result, indent=2))
