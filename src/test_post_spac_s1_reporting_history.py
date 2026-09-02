import unittest
from unittest.mock import patch

import s1_registration_history_gate as gate


class PostSpacS1ReportingHistoryTests(unittest.TestCase):
    def _record(self, filed="2026-08-31"):
        return {
            "company": "StablecoinX Inc.",
            "cik": "2080215",
            "form": "S-1",
            "stage": "Pre-pricing",
            "filed": filed,
            "accession_no": "0001213900-26-095808",
        }

    def _submissions(self, forms, dates):
        count = len(forms)
        return {
            "filings": {
                "recent": {
                    "accessionNumber": [f"0000000000-26-{index:06d}" for index in range(count)],
                    "form": forms,
                    "fileNumber": ["333-000000"] * count,
                    "filingDate": dates,
                    "primaryDocument": ["document.htm"] * count,
                }
            }
        }

    @patch("s1_registration_history_gate.edgar_client._get_headers", return_value={})
    @patch("s1_registration_history_gate.edgar_client._request_json")
    def test_prior_8k_proves_issuer_was_already_reporting(self, request_json, _headers):
        request_json.return_value = self._submissions(
            ["S-1", "8-K"],
            ["2026-08-31", "2026-06-25"],
        )
        self.assertTrue(gate.already_reporting_before_registration(self._record()))

    @patch("s1_registration_history_gate.edgar_client._get_headers", return_value={})
    @patch("s1_registration_history_gate.edgar_client._request_json")
    def test_prior_foreign_issuer_reporting_forms_prove_already_public(self, request_json, _headers):
        for reporting_form in ("6-K", "6-K/A", "20-F", "20-F/A", "40-F", "40-F/A"):
            with self.subTest(reporting_form=reporting_form):
                request_json.return_value = self._submissions(
                    ["S-1", reporting_form],
                    ["2026-08-31", "2026-06-25"],
                )
                self.assertTrue(gate.already_reporting_before_registration(self._record()))

    @patch("s1_registration_history_gate.edgar_client._get_headers", return_value={})
    @patch("s1_registration_history_gate.edgar_client._request_json")
    def test_prior_private_registration_does_not_trigger_reporting_exclusion(self, request_json, _headers):
        request_json.return_value = self._submissions(
            ["S-1", "S-1/A"],
            ["2026-08-31", "2026-08-20"],
        )
        self.assertFalse(gate.already_reporting_before_registration(self._record()))

    @patch("s1_registration_history_gate.edgar_client._get_headers", return_value={})
    @patch("s1_registration_history_gate.edgar_client._request_json")
    def test_same_day_reporting_form_is_not_used_to_infer_event_order(self, request_json, _headers):
        request_json.return_value = self._submissions(
            ["S-1", "8-K"],
            ["2026-08-31", "2026-08-31"],
        )
        self.assertFalse(gate.already_reporting_before_registration(self._record()))

    @patch("s1_registration_history_gate.edgar_client._get_headers", return_value={})
    @patch("s1_registration_history_gate.edgar_client._request_json")
    def test_same_day_foreign_reporting_form_remains_ambiguous(self, request_json, _headers):
        request_json.return_value = self._submissions(
            ["S-1", "20-F"],
            ["2026-08-31", "2026-08-31"],
        )
        self.assertFalse(gate.already_reporting_before_registration(self._record()))


if __name__ == "__main__":
    unittest.main()
