import unittest
from unittest.mock import patch

import archived_reporting_history_gate
import followon_sanitizer
import s1_registration_history_gate


SHORT_FORM_REPORTING_FORMS = (
    "S-3",
    "S-3/A",
    "S-3ASR",
    "S-3ASR/A",
    "S-3D",
    "S-3DPOS",
    "S-3MEF",
    "F-3",
    "F-3/A",
    "F-3ASR",
    "F-3ASR/A",
    "F-3D",
    "F-3DPOS",
    "F-3MEF",
)


class ShortFormReportingHistoryTests(unittest.TestCase):
    def test_final_gate_recognizes_prior_short_form_reporting(self):
        for form in SHORT_FORM_REPORTING_FORMS:
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

    def test_final_gate_does_not_infer_same_day_short_form_order(self):
        for form in SHORT_FORM_REPORTING_FORMS:
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

    def test_archived_gate_recognizes_prior_short_form_reporting(self):
        for form in SHORT_FORM_REPORTING_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form],
                            "filingDate": ["2026-08-01"],
                        },
                        "files": [],
                    }
                }
                self.assertTrue(
                    archived_reporting_history_gate.has_prior_reporting_history(
                        submissions,
                        "2026-08-02",
                    )
                )

    def test_archived_gate_does_not_infer_same_day_short_form_order(self):
        for form in SHORT_FORM_REPORTING_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form],
                            "filingDate": ["2026-08-02"],
                        },
                        "files": [],
                    }
                }
                self.assertFalse(
                    archived_reporting_history_gate.has_prior_reporting_history(
                        submissions,
                        "2026-08-02",
                    )
                )

    def test_prepricing_gate_recognizes_prior_short_form_reporting(self):
        record = {
            "form": "S-1",
            "stage": "Pre-pricing",
            "cik": "1234567",
            "filed": "2026-08-02",
            "accession_no": "0001234567-26-000002",
        }
        for form in SHORT_FORM_REPORTING_FORMS:
            with self.subTest(form=form), patch.object(
                s1_registration_history_gate,
                "_recent_submission_rows",
                return_value=[
                    {
                        "accession_no": record["accession_no"],
                        "form": "S-1",
                        "filing_date": "2026-08-02",
                    },
                    {
                        "accession_no": "0001234567-26-000001",
                        "form": form,
                        "filing_date": "2026-08-01",
                    },
                ],
            ):
                self.assertTrue(
                    s1_registration_history_gate.already_reporting_before_registration(
                        record
                    )
                )

    def test_prepricing_gate_does_not_infer_same_day_short_form_order(self):
        record = {
            "form": "S-1",
            "stage": "Pre-pricing",
            "cik": "1234567",
            "filed": "2026-08-02",
            "accession_no": "0001234567-26-000002",
        }
        for form in SHORT_FORM_REPORTING_FORMS:
            with self.subTest(form=form), patch.object(
                s1_registration_history_gate,
                "_recent_submission_rows",
                return_value=[
                    {
                        "accession_no": record["accession_no"],
                        "form": "S-1",
                        "filing_date": "2026-08-02",
                    },
                    {
                        "accession_no": "0001234567-26-000001",
                        "form": form,
                        "filing_date": "2026-08-02",
                    },
                ],
            ):
                self.assertFalse(
                    s1_registration_history_gate.already_reporting_before_registration(
                        record
                    )
                )


if __name__ == "__main__":
    unittest.main()
