import json
import os
import unittest
from unittest.mock import Mock, patch

import stanford_grader as grader


class StanfordGraderTests(unittest.TestCase):
    def test_organization_holder_skips_openai(self):
        organization_names = [
            "Entities affiliated with Westlake BioPartners",
            "Foresite Capital",
            "Deep Track Biotechnology Master Fund, Ltd.",
            "OrbiMed Private Investments VIII, LP",
            "J. Jean Cui, Ph.D. and Y. Peter Li, Ph.D., MBA and related affiliates",
        ]
        for name in organization_names:
            with self.subTest(name=name), patch.object(grader, "research_via_openai") as research:
                result = grader.grade_stanford_affiliation(name, "Acme")
            self.assertEqual(result["grade"], 0)
            self.assertEqual(result["source"], "non_person_holder")
            research.assert_not_called()

    def test_real_person_names_are_not_treated_as_organizations(self):
        self.assertFalse(grader.is_likely_organization("Beth Seidenberg, M.D."))
        self.assertFalse(grader.is_likely_organization("James B. Tananbaum, M.D."))
        self.assertFalse(grader.is_likely_organization("Jane Founder"))

    def test_sec_footnote_suffix_is_removed(self):
        self.assertEqual(grader._clean_person_name("Nima Farzan(6)"), "Nima Farzan")
        self.assertEqual(grader._clean_person_name("Nima Farzan (6)(7)"), "Nima Farzan")

    def test_direct_exact_person_filing_evidence_short_circuits_openai(self):
        with patch.object(grader, "research_via_openai") as research:
            result = grader.grade_stanford_affiliation(
                "Jane Doe",
                "Acme",
                bio_text="Jane Doe earned an MBA from Stanford University and joined Acme in 2020.",
            )
        self.assertEqual(result["grade"], 5)
        self.assertEqual(result["source"], "filing_bio")
        research.assert_not_called()

    def test_unrelated_stanford_mention_in_filing_does_not_confirm_holder(self):
        bio = (
            "Jane Doe serves as Chief Executive Officer. "
            "Another Executive earned a degree from Stanford University."
        )
        with patch.object(
            grader,
            "research_via_openai",
            return_value={
                "grade": 0,
                "justification": "No evidence.",
                "source_url": "",
                "source": "openai_web_research",
            },
        ) as research:
            result = grader.grade_stanford_affiliation("Jane Doe", "Acme", bio_text=bio)
        self.assertEqual(result["grade"], 0)
        research.assert_called_once()

    def test_openai_request_uses_web_search_and_structured_output(self):
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "grade": 5,
                                    "justification": "Official Stanford profile confirms the affiliation.",
                                    "source_url": "https://profiles.stanford.edu/jane-doe",
                                    "source_title": "Jane Doe | Stanford Profiles",
                                }
                            ),
                        }
                    ],
                }
            ]
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), patch.object(
            grader.requests, "post", return_value=response
        ) as post:
            result = grader.research_via_openai("Jane Doe", "Acme")

        self.assertEqual(result["grade"], 5)
        self.assertEqual(result["source"], "openai_web_research")
        request = post.call_args.kwargs
        self.assertEqual(request["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(request["json"]["tools"], [{"type": "web_search"}])
        self.assertEqual(request["json"]["tool_choice"], "required")
        self.assertEqual(request["json"]["text"]["format"]["type"], "json_schema")
        self.assertFalse(request["json"]["store"])

    def test_model_can_be_overridden(self):
        with patch.dict(os.environ, {"OPENAI_MODEL": "custom-model"}, clear=False):
            self.assertEqual(grader._openai_model(), "custom-model")

    def test_openai_error_includes_api_detail(self):
        response = Mock()
        response.ok = False
        response.status_code = 400
        response.text = '{"error":{"message":"invalid model"}}'
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), patch.object(
            grader.requests, "post", return_value=response
        ):
            with self.assertRaises(grader.StanfordGraderError) as context:
                grader.research_via_openai("Jane Doe", "Acme")
        self.assertIn("400", str(context.exception))
        self.assertIn("invalid model", str(context.exception))

    def test_out_of_range_grade_fails_closed(self):
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "grade": 9,
                                    "justification": "bad",
                                    "source_url": "https://profiles.stanford.edu/jane-doe",
                                    "source_title": "bad",
                                }
                            ),
                        }
                    ],
                }
            ]
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), patch.object(
            grader.requests, "post", return_value=response
        ):
            result = grader.research_via_openai("Jane Doe", "Acme")
        self.assertEqual(result["grade"], 0)
        self.assertEqual(result["source"], "parse_error")

    def test_grade_five_is_downgraded_when_source_cannot_be_verified(self):
        discovered = {
            "grade": 5,
            "justification": "Potential match.",
            "source_url": "https://example.com/jane",
            "source": "openai_web_research",
        }
        with patch.object(grader, "research_via_openai", return_value=discovered), patch.object(
            grader, "_verify_authoritative_source", return_value=None
        ):
            result = grader.grade_stanford_affiliation("Jane Doe", "Acme")
        self.assertEqual(result["grade"], 4)
        self.assertEqual(result["source"], "openai_unverified")

    def test_verified_authoritative_source_confirms_grade_five(self):
        discovered = {
            "grade": 5,
            "justification": "Stanford profile found.",
            "source_url": "https://profiles.stanford.edu/jane-doe",
            "source": "openai_web_research",
        }
        with patch.object(grader, "research_via_openai", return_value=discovered), patch.object(
            grader,
            "_verify_authoritative_source",
            return_value={"link": discovered["source_url"], "hostname": "profiles.stanford.edu"},
        ):
            result = grader.grade_stanford_affiliation("Jane Doe", "Acme")
        self.assertEqual(result["grade"], 5)
        self.assertEqual(result["source"], "openai_verified_official")
        self.assertEqual(result["source_url"], discovered["source_url"])

    def test_non_authoritative_hostname_is_rejected_before_fetch(self):
        with patch.object(grader.requests, "get") as get:
            result = grader._verify_authoritative_source(
                "Jane Doe", "Acme", "https://random-example.net/jane-doe"
            )
        self.assertIsNone(result)
        get.assert_not_called()

    def test_authoritative_page_requires_exact_person_and_stanford_university(self):
        response = Mock()
        response.ok = True
        response.text = (
            "<html><body><h1>Jane Doe</h1>"
            "<p>Jane Doe earned a degree from Stanford University.</p></body></html>"
        )
        response.raise_for_status.return_value = None
        with patch.object(grader.requests, "get", return_value=response):
            result = grader._verify_authoritative_source(
                "Jane Doe", "Acme", "https://profiles.stanford.edu/jane-doe"
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["hostname"], "profiles.stanford.edu")


if __name__ == "__main__":
    unittest.main()
