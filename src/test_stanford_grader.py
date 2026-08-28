import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import stanford_grader as grader


def test_organization_holder_skips_openai():
    organization_names = [
        "Entities affiliated with Westlake BioPartners",
        "Foresite Capital",
        "Deep Track Biotechnology Master Fund, Ltd.",
        "OrbiMed Private Investments VIII, LP",
        "J. Jean Cui, Ph.D. and Y. Peter Li, Ph.D., MBA and related affiliates",
    ]
    for name in organization_names:
        with patch.object(grader, "grade_via_llm") as llm:
            result = grader.grade_stanford_affiliation(name, "Acme")
        assert result["grade"] == 0
        assert result["source"] == "non_person_holder"
        llm.assert_not_called()


def test_real_person_names_are_not_treated_as_organizations():
    assert grader.is_likely_organization("Beth Seidenberg, M.D.") is False
    assert grader.is_likely_organization("James B. Tananbaum, M.D.") is False
    assert grader.is_likely_organization("Jane Founder") is False


def test_direct_bio_short_circuits_openai():
    with patch.object(grader, "grade_via_llm") as llm:
        result = grader.grade_stanford_affiliation(
            "Jane Doe",
            "Acme",
            bio_text="Jane Doe earned an MBA from Stanford University.",
        )
    assert result["grade"] == 5
    assert result["source"] == "filing_bio"
    llm.assert_not_called()


def test_sec_footnote_suffix_is_removed():
    assert grader._clean_person_name("Nima Farzan(6)") == "Nima Farzan"


def test_openai_model_can_be_overridden():
    with patch.dict(os.environ, {"OPENAI_STANFORD_MODEL": "custom-model"}):
        assert grader._openai_model() == "custom-model"


def test_openai_web_search_request_and_response():
    response = Mock()
    response.ok = True
    response.json.return_value = {
        "output": [{
            "type": "message",
            "content": [{
                "type": "output_text",
                "text": (
                    '{"grade":5,"confirmed":true,'
                    '"justification":"Official issuer biography confirms a Stanford University B.A.",'
                    '"source_url":"https://latigobio.com/staff-member/nima-farzan-mba/"}'
                ),
            }],
        }]
    }

    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
            patch.object(grader.requests, "post", return_value=response) as post:
        result = grader.grade_via_llm(
            "Nima Farzan",
            "Latigo Biotherapeutics, Inc.",
            "CEO",
            "",
            [],
        )

    assert result["grade"] == 5
    assert result["source"] == "openai_web_research"
    assert "latigobio.com" in result["source_url"]
    payload = post.call_args.kwargs["json"]
    assert payload["tools"] == [{"type": "web_search"}]
    assert payload["model"] == grader.DEFAULT_OPENAI_MODEL
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"


def test_openai_error_includes_api_detail():
    response = Mock()
    response.ok = False
    response.status_code = 401
    response.text = '{"error":{"message":"invalid api key"}}'

    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
            patch.object(grader.requests, "post", return_value=response):
        try:
            grader.grade_via_llm("Jane Doe", "Acme", "CEO", "", [])
            assert False, "expected StanfordGraderError"
        except grader.StanfordGraderError as exc:
            assert "401" in str(exc)
            assert "invalid api key" in str(exc)


def test_unconfirmed_grade_five_is_downgraded():
    response = Mock()
    response.ok = True
    response.json.return_value = {
        "output": [{
            "type": "message",
            "content": [{
                "type": "output_text",
                "text": (
                    '{"grade":5,"confirmed":false,'
                    '"justification":"Possible match but not definitive.",'
                    '"source_url":"https://example.com"}'
                ),
            }],
        }]
    }

    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
            patch.object(grader.requests, "post", return_value=response):
        result = grader.grade_via_llm("Jane Doe", "Acme", "CEO", "", [])

    assert result["grade"] == 4
    assert result["source"] == "openai_web_research"


def test_invalid_grade_payload_fails_closed():
    response = Mock()
    response.ok = True
    response.json.return_value = {
        "output": [{
            "type": "message",
            "content": [{
                "type": "output_text",
                "text": '{"grade":9,"confirmed":true,"justification":"bad","source_url":""}',
            }],
        }]
    }

    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
            patch.object(grader.requests, "post", return_value=response):
        result = grader.grade_via_llm("Jane Doe", "Acme", "CEO", "", [])

    assert result["grade"] == 0
    assert result["source"] == "parse_error"


def test_top_level_uses_openai_when_filing_is_silent():
    expected = {
        "grade": 5,
        "justification": "Confirmed.",
        "source": "openai_web_research",
        "source_url": "https://profiles.stanford.edu/jane-doe",
    }
    with patch.object(grader, "grade_via_llm", return_value=expected) as llm:
        result = grader.grade_stanford_affiliation("Jane Doe(4)", "Acme", "CEO", "")

    assert result == expected
    llm.assert_called_once_with("Jane Doe", "Acme", "CEO", "", [])


def test_research_cache_reuses_unchanged_evidence_and_tracks_usage():
    researched = {
        "grade": 0,
        "justification": "No Stanford affiliation found.",
        "source": "openai_web_research",
        "source_url": "",
        "_usage": {"input_tokens": 120, "output_tokens": 20, "total_tokens": 140},
    }
    with tempfile.TemporaryDirectory() as directory:
        cache_path = Path(directory) / "cache.json"
        with patch.dict(os.environ, {"STANFORD_RESEARCH_CACHE_PATH": str(cache_path)}), \
                patch.object(grader, "grade_via_llm", return_value=researched) as llm:
            first = grader.grade_stanford_affiliation("Jane Doe", "Acme", "CEO", "No Stanford mention.")
            second = grader.grade_stanford_affiliation("Jane Doe", "Acme", "CEO", "No Stanford mention.")

        assert first == second
        assert "_usage" not in first
        llm.assert_called_once()
        payload = json.loads(cache_path.read_text())
        assert payload["usage"] == {
            "requests": 1,
            "input_tokens": 120,
            "output_tokens": 20,
            "total_tokens": 140,
        }


def test_research_cache_invalidates_when_evidence_changes():
    researched = {
        "grade": 0,
        "justification": "No Stanford affiliation found.",
        "source": "openai_web_research",
        "source_url": "",
    }
    with tempfile.TemporaryDirectory() as directory:
        cache_path = Path(directory) / "cache.json"
        with patch.dict(os.environ, {"STANFORD_RESEARCH_CACHE_PATH": str(cache_path)}), \
                patch.object(grader, "grade_via_llm", return_value=researched) as llm:
            grader.grade_stanford_affiliation("Jane Doe", "Acme", "CEO", "First filing evidence.")
            grader.grade_stanford_affiliation("Jane Doe", "Acme", "CEO", "Changed filing evidence.")

        assert llm.call_count == 2


def test_unrelated_long_filing_text_does_not_invalidate_person_cache():
    researched = {
        "grade": 0,
        "justification": "No Stanford affiliation found.",
        "source": "openai_web_research",
        "source_url": "",
    }
    first_filing = "Unrelated cover text. " * 300
    changed_filing = "Different unrelated cover text. " * 300
    with tempfile.TemporaryDirectory() as directory:
        cache_path = Path(directory) / "cache.json"
        with patch.dict(os.environ, {"STANFORD_RESEARCH_CACHE_PATH": str(cache_path)}), \
                patch.object(grader, "grade_via_llm", return_value=researched) as llm:
            grader.grade_stanford_affiliation("Jane Doe", "Acme", "CEO", first_filing)
            grader.grade_stanford_affiliation("Jane Doe", "Acme", "CEO", changed_filing)

        assert llm.call_count == 1


def test_long_filing_prompt_keeps_only_context_near_person():
    text = ("Unrelated disclosure. " * 200) + "Jane Doe is Chief Executive Officer." + ("More disclosure. " * 200)
    prompt = grader._build_openai_prompt("Jane Doe", "Acme", "CEO", text)
    assert "Jane Doe is Chief Executive Officer." in prompt
    assert len(prompt) < 5000


def test_transient_research_failure_is_not_cached():
    with tempfile.TemporaryDirectory() as directory:
        cache_path = Path(directory) / "cache.json"
        with patch.dict(os.environ, {"STANFORD_RESEARCH_CACHE_PATH": str(cache_path)}), \
                patch.object(grader, "grade_via_llm", side_effect=grader.StanfordGraderError("temporary")) as llm:
            grader.grade_stanford_affiliation("Jane Doe", "Acme", "CEO", "")
            grader.grade_stanford_affiliation("Jane Doe", "Acme", "CEO", "")

        assert llm.call_count == 2
        assert not cache_path.exists()
