from unittest.mock import patch

import stanford_grader as grader


def test_top_level_research_failure_does_not_become_public_evidence():
    error = grader.StanfordGraderError(
        'OpenAI Stanford research request failed (429): insufficient_quota secret detail'
    )
    with patch.object(grader, 'grade_via_llm', side_effect=error):
        result = grader.grade_stanford_affiliation('Jane Doe', 'Acme', 'CEO', '')

    assert result == {
        'grade': 0,
        'justification': '',
        'source': 'research_unavailable',
        'source_url': '',
    }
    assert 'quota' not in result['justification'].lower()
    assert 'openai' not in result['justification'].lower()
