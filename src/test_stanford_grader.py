import os
from unittest.mock import Mock, patch

import stanford_grader as grader


def test_organization_holder_skips_search_and_llm():
    organization_names = [
        "Entities affiliated with Westlake BioPartners",
        "Foresite Capital",
        "Deep Track Biotechnology Master Fund, Ltd.",
        "OrbiMed Private Investments VIII, LP",
        "J. Jean Cui, Ph.D. and Y. Peter Li, Ph.D., MBA and related affiliates",
    ]

    for name in organization_names:
        with patch.object(grader, "run_search_fallback") as search, \
                patch.object(grader, "grade_via_llm") as llm:
            result = grader.grade_stanford_affiliation(name, "Acme")

        assert result["grade"] == 0
        assert result["source"] == "non_person_holder"
        search.assert_not_called()
        llm.assert_not_called()


def test_real_person_names_are_not_treated_as_organizations():
    assert grader.is_likely_organization("Beth Seidenberg, M.D.") is False
    assert grader.is_likely_organization("James B. Tananbaum, M.D.") is False
    assert grader.is_likely_organization("Jane Founder") is False


def test_direct_bio_short_circuits_search():
    with patch.object(grader, "run_search_fallback") as search:
        result = grader.grade_stanford_affiliation(
            "Jane Doe",
            "Acme",
            bio_text="Jane earned an MBA from Stanford University.",
        )

    assert result["grade"] == 5
    assert result["source"] == "filing_bio"
    search.assert_not_called()


def test_no_public_evidence_skips_llm():
    results = [{
        "title": "Jane Doe - Acme",
        "snippet": "Executive biography",
        "link": "https://example.com/jane",
    }]
    with patch.object(grader, "run_search_fallback", return_value=results), \
            patch.object(grader, "grade_via_llm") as llm:
        result = grader.grade_stanford_affiliation("Jane Doe", "Acme")

    assert result["grade"] == 0
    assert result["source"] == "no_public_evidence"
    llm.assert_not_called()


def test_stanford_search_evidence_calls_llm():
    results = [{
        "title": "Jane Doe",
        "snippet": "Stanford alumna and Acme executive",
        "link": "https://example.com/jane",
    }]
    expected = {"grade": 4, "justification": "Matched role and company.", "source": "llm_judgment"}
    with patch.object(grader, "run_search_fallback", return_value=results), \
            patch.object(grader, "grade_via_llm", return_value=expected) as llm:
        result = grader.grade_stanford_affiliation("Jane Doe", "Acme")

    assert result == expected
    llm.assert_called_once()


def test_search_fallback_prioritizes_exact_person_stanford_query():
    calls = []

    def fake_search(query):
        calls.append(query)
        return []

    with patch.object(grader, "brave_search", side_effect=fake_search):
        grader.run_search_fallback("Nima Farzan", "Latigo Biotherapeutics")

    assert calls == [
        '"Nima Farzan" "Stanford University"',
        '"Nima Farzan" Stanford "Latigo Biotherapeutics"',
    ]


def test_model_can_be_overridden():
    with patch.dict(os.environ, {"ANTHROPIC_MODEL": "custom-model"}):
        assert grader._anthropic_model() == "custom-model"


def test_anthropic_error_includes_api_detail():
    response = Mock()
    response.ok = False
    response.status_code = 400
    response.text = '{"error":{"message":"invalid model"}}'

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
            patch.object(grader.requests, "post", return_value=response):
        try:
            grader.grade_via_llm("Jane Doe", "Acme", "CEO", "", [])
            assert False, "expected StanfordGraderError"
        except grader.StanfordGraderError as exc:
            assert "400" in str(exc)
            assert "invalid model" in str(exc)


def test_grade_range_is_validated():
    response = Mock()
    response.ok = True
    response.json.return_value = {
        "content": [{"type": "text", "text": '{"grade": 9, "justification": "bad"}'}]
    }

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
            patch.object(grader.requests, "post", return_value=response):
        result = grader.grade_via_llm("Jane Doe", "Acme", "CEO", "", [])

    assert result["grade"] == 0
    assert result["source"] == "parse_error"
