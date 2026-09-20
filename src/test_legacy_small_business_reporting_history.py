import unittest

import archived_reporting_history_gate as archived_gate
import followon_sanitizer


class LegacySmallBusinessReportingHistoryTests(unittest.TestCase):
    FORMS = (
        "10SB12B", "10SB12B/A", "10SB12G", "10SB12G/A",
        "10QSB", "10QSB/A",
        "10KSB", "10KSB/A", "10KSB40", "10KSB40/A",
    )

    def test_recent_legacy_small_business_forms_prove_prior_reporting(self):
        for form in self.FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "424B4"],
                            "filingDate": ["2007-05-23", "2026-09-20"],
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

    def test_archived_legacy_small_business_forms_prove_prior_reporting(self):
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
                archived = {"form": [form], "filingDate": ["2007-05-23"]}
                self.assertTrue(
                    archived_gate.has_prior_reporting_history(
                        submissions,
                        "2026-09-01",
                        archive_loader=lambda _name, archived=archived: archived,
                    )
                )


if __name__ == "__main__":
    unittest.main()
