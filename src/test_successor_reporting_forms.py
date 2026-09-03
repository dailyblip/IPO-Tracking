import unittest
from unittest.mock import patch

import followon_sanitizer
import s1_registration_history_gate


SUCCESSOR_REPORTING_FORMS = (
    "8-K12B",
    "8-K12B/A",
    "8-K12G3",
    "8-K12G3/A",
    "8-K15D5",
    "8-K15D5/A",
)


class SuccessorReportingFormTests(unittest.TestCase):
    def test_followon_gate_recognizes_prior_successor_reporting_forms(self):
        for form in SUCCESSOR_REPORTING_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form],
                            "filingDate": ["2026-08-01"],
                        }
                    }
                }
                self.assertTrue(
                    followon_sanitizer.has_prior_periodic_report(
                        submissions, "2026-08-02"
                    )
                )

    def test_followon_gate_does_not_infer_same_day_order(self):
        for form in SUCCESSOR_REPORTING_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form],
                            "filingDate": ["2026-08-02"],
                        }
                    }
                }
                self.assertFalse(
                    followon_sanitizer.has_prior_periodic_report(
                        submissions, "2026-08-02"
                    )
                )

    def test_s1_gate_recognizes_prior_successor_reporting_forms(self):
        record = {
            "form": "S-1",
            "stage": "Pre-pricing",
            "cik": "1234567",
            "filed": "2026-08-02",
        }
        for form in SUCCESSOR_REPORTING_FORMS:
            with self.subTest(form=form), patch.object(
                s1_registration_history_gate,
                "_recent_submission_rows",
                return_value=[{"form": form, "filing_date": "2026-08-01"}],
            ):
                self.assertTrue(
                    s1_registration_history_gate.already_reporting_before_registration(
                        record
                    )
                )

    def test_s1_gate_does_not_infer_same_day_order(self):
        record = {
            "form": "S-1",
            "stage": "Pre-pricing",
            "cik": "1234567",
            "filed": "2026-08-02",
        }
        for form in SUCCESSOR_REPORTING_FORMS:
            with self.subTest(form=form), patch.object(
                s1_registration_history_gate,
                "_recent_submission_rows",
                return_value=[{"form": form, "filing_date": "2026-08-02"}],
            ):
                self.assertFalse(
                    s1_registration_history_gate.already_reporting_before_registration(
                        record
                    )
                )


if __name__ == "__main__":
    unittest.main()
