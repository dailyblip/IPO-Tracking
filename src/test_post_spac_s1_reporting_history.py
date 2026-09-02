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


if __name__ == "__main__":
    unittest.main()
