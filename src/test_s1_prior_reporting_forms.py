import unittest
from unittest.mock import patch

import followon_sanitizer
import s1_registration_history_gate as gate


class S1PriorReportingFormsTests(unittest.TestCase):
    def _record(self):
        return {
            "company": "Already Public Co",
            "cik": "0002000100",
            "accession_no": "0000000000-26-000200",
            "form": "S-1",
            "stage": "Pre-pricing",
        }

    def _rows(self, prior_form):
        return [
            {
                "accession_no": "0000000000-26-000200",
                "form": "S-1",
                "filing_date": "2026-09-10",
                "acceptance_datetime": "20260910120000",
            },
            {
                "accession_no": "0000000000-26-000100",
                "form": prior_form,
                "filing_date": "2026-09-09",
                "acceptance_datetime": "20260909120000",
            },
        ]

    def test_s1_gate_uses_same_prior_reporting_evidence_as_final_gate(self):
        self.assertEqual(followon_sanitizer.REPORTING_FORMS, gate.REPORTING_FORMS)

    def test_previously_missing_reporting_families_exclude_later_s1(self):
        for prior_form in (
            "10-12G",
            "10KSB",
            "15-12G",
            "20FR12B",
            "DEF 14A",
            "424B4",
        ):
            with self.subTest(prior_form=prior_form), patch.object(
                gate, "_recent_submission_rows", return_value=self._rows(prior_form)
            ):
                self.assertTrue(gate.already_reporting_before_registration(self._record()))

    def test_ipo_contemporaneous_8a_and_s8_are_not_generic_reporting_evidence(self):
        self.assertNotIn("8-A12B", gate.REPORTING_FORMS)
        self.assertNotIn("8-A12G", gate.REPORTING_FORMS)
        self.assertNotIn("S-8", gate.REPORTING_FORMS)
        self.assertNotIn("S-8 POS", gate.REPORTING_FORMS)

    def test_same_day_prior_form_requires_strict_acceptance_order(self):
        current = {
            "accession_no": "0000000000-26-000200",
            "form": "S-1",
            "filing_date": "2026-09-10",
            "acceptance_datetime": "20260910120000",
        }
        later_424b4 = {
            "accession_no": "0000000000-26-000201",
            "form": "424B4",
            "filing_date": "2026-09-10",
            "acceptance_datetime": "20260910130000",
        }
        with patch.object(
            gate,
            "_recent_submission_rows",
            return_value=[current, later_424b4],
        ):
            self.assertFalse(gate.already_reporting_before_registration(self._record()))


if __name__ == "__main__":
    unittest.main()
