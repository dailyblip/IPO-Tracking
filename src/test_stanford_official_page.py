from unittest.mock import Mock, patch

import stanford_grader as grader


def _response(html):
    response = Mock()
    response.text = html
    response.raise_for_status.return_value = None
    return response


def test_official_issuer_page_can_confirm_when_search_snippet_is_silent():
    results = [{
        "title": "Nima Farzan - Latigo Biotherapeutics",
        "snippet": "President and Chief Executive Officer biography",
        "link": "https://latigobio.com/staff-member/nima-farzan-mba/",
    }]
    html = "<html><body><h1>Nima Farzan</h1><p>He earned a B.A. from Stanford University.</p></body></html>"
    with patch.object(grader, "run_search_fallback", return_value=results), \
            patch.object(grader.requests, "get", return_value=_response(html)), \
            patch.object(grader, "grade_via_llm") as llm:
        result = grader.grade_stanford_affiliation("Nima Farzan", "Latigo Biotherapeutics, Inc.")

    assert result["grade"] == 5
    assert result["source"] == "official_page_content"
    assert "latigobio.com" in result["justification"]
    llm.assert_not_called()


def test_official_page_does_not_confirm_without_exact_person():
    results = [{
        "title": "Leadership - Latigo Biotherapeutics",
        "snippet": "Executive biographies",
        "link": "https://latigobio.com/leadership/",
    }]
    html = "<html><body><p>Another executive earned a degree from Stanford University.</p></body></html>"
    with patch.object(grader, "run_search_fallback", return_value=results), \
            patch.object(grader.requests, "get", return_value=_response(html)), \
            patch.object(grader, "grade_via_llm") as llm:
        result = grader.grade_stanford_affiliation("Nima Farzan", "Latigo Biotherapeutics, Inc.")

    assert result["grade"] == 0
    assert result["source"] == "no_public_evidence"
    llm.assert_not_called()


def test_unofficial_page_is_never_fetched_for_deterministic_confirmation():
    results = [{
        "title": "Nima Farzan profile",
        "snippet": "Executive biography",
        "link": "https://example.com/nima-farzan",
    }]
    with patch.object(grader, "run_search_fallback", return_value=results), \
            patch.object(grader.requests, "get") as get, \
            patch.object(grader, "grade_via_llm") as llm:
        result = grader.grade_stanford_affiliation("Nima Farzan", "Latigo Biotherapeutics, Inc.")

    assert result["grade"] == 0
    assert result["source"] == "no_public_evidence"
    get.assert_not_called()
    llm.assert_not_called()
