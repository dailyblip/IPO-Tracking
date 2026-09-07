from unittest.mock import patch

import stanford_grader as grader


def test_openai_research_prompt_prioritizes_authoritative_sources_and_exact_identity():
    prompt = grader._build_openai_prompt(
        "Nima Farzan",
        "Latigo Biotherapeutics, Inc.",
        "President and Chief Executive Officer",
        "",
    )

    assert "Person: Nima Farzan" in prompt
    assert "stanford.edu" in prompt
    assert "issuer/company's official website" in prompt
    assert "SEC filings" in prompt
    assert "Identity matching is critical" in prompt
    assert "same-name person" in prompt


def test_confirmed_authoritative_openai_result_is_preserved():
    result = {
        "grade": 5,
        "justification": "Issuer biography confirms a Stanford University degree for the exact person.",
        "source": "openai_web_research",
        "source_url": "https://latigobio.com/staff-member/nima-farzan-mba/",
    }
    with patch.object(grader, "grade_via_llm", return_value=result) as research:
        actual = grader.grade_stanford_affiliation(
            "Nima Farzan",
            "Latigo Biotherapeutics, Inc.",
        )

    assert actual == result
    research.assert_called_once()


def test_no_public_evidence_fails_closed_without_cardinal_signal():
    result = {
        "grade": 0,
        "justification": "No unambiguous Stanford University affiliation found for the exact person.",
        "source": "openai_web_research",
        "source_url": "",
    }
    with patch.object(grader, "grade_via_llm", return_value=result):
        actual = grader.grade_stanford_affiliation(
            "Nima Farzan",
            "Latigo Biotherapeutics, Inc.",
        )

    assert actual["grade"] == 0
    assert actual["source_url"] == ""


def test_unconfirmed_grade_five_from_openai_is_downgraded(monkeypatch):
    class Response:
        ok = True
        text = ""

        @staticmethod
        def json():
            return {
                "output": [{
                    "type": "message",
                    "content": [{
                        "type": "output_text",
                        "text": '{"grade":5,"confirmed":false,"justification":"Ambiguous identity","source_url":"https://example.com"}',
                    }],
                }],
                "usage": {},
            }

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(grader.requests, "post", lambda *args, **kwargs: Response())

    actual = grader.grade_via_llm("Nima Farzan", "Latigo Biotherapeutics, Inc.", "", "")

    assert actual["grade"] == 4
    assert actual["source"] == "openai_web_research"
