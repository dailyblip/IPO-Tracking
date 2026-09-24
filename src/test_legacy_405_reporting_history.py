import unittest
from unittest.mock import patch

import archived_reporting_history_gate as archived_gate
import followon_sanitizer
import s1_registration_history_gate as s1_gate


class Legacy405ReportingHistoryTests(unittest.TestCase):
    FORMS = ("10-K405", "10-K405/A", "10KT405", "10KT405/A")

    def _s1_record(self):
        return {
            "company": "Legacy Reporting Co",
            "cik": "0002000100",
            "accession_no": "0000000000-26-000200",
            "form": "S-1",
            "stage": "Pre-pricing",
        }

    def test_all_reporting_classifiers_include_legacy_405_forms(self):
        for form in self.FORMS:
            with self.subTest(form=form):
                self.assertIn(form, followon_sanitizer.REPORTING_FORMS)
                self.assertIn(form, s1_gate.REPORTING_FORMS)
                self.assertIn(form, archived_gate.REPORTING_FORMS)

    def test_recent_legacy_405_forms_prove_prior_reporting(self):
        for form in self.FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "S-1"],
                            "filingDate": ["2002-03-15", "2026-09-20"],
                        },
                        "files": [],
                    }
                }
                self.assertTrue(
                    followon_sanitizer.has_prior_periodic_report(
                        submissions, "2026-09-20"
                    )
                )
                self.assertTrue(
                    archived_gate.has_prior_reporting_history(
                        submissions, "2026-09-20"
                    )
                )

                rows = [
                    {
                        "accession_no": "0000000000-26-000200",
                        "form": "S-1",
                        "filing_date": "2026-09-20",
                        "acceptance_datetime": "20260920120000",
                    },
                    {
                        "accession_no": "0000000000-02-000100",
                        "form": form,
                        "filing_date": "2002-03-15",
                        "acceptance_datetime": "20020315120000",
                    },
                ]
                with patch.object(
                    s1_gate, "_recent_submission_rows", return_value=rows
                ):
                    self.assertTrue(
                        s1_gate.already_reporting_before_registration(
                            self._s1_record()
                        )
                    )

    def test_archived_legacy_405_forms_prove_prior_reporting(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["S-1"],
                    "filingDate": ["2026-09-01"],
                },
                "files": [
                    {
                        "name": "CIK0000000001-submissions-001.json",
                        "filingFrom": "1996-01-01",
                        "filingTo": "2008-12-31",
                    }
                ],
            }
        }

        for form in self.FORMS:
            with self.subTest(form=form):
                archived = {"form": [form], "filingDate": ["2002-03-15"]}
                self.assertTrue(
                    archived_gate.has_prior_reporting_history(
                        submissions,
                        "2026-09-01",
                        archive_loader=lambda _name, archived=archived: archived,
                    )
                )


if __name__ == "__main__":
    unittest.main()
