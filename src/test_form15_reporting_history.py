import unittest

import archived_reporting_history_gate as archived_gate
import followon_sanitizer


SECTION_12_TERMINATION_FORMS = (
    "15-12B",
    "15-12B/A",
    "15-12G",
    "15-12G/A",
)
SECTION_15D_SUSPENSION_FORMS = ("15-15D", "15-15D/A")


class Form15ReportingHistoryTests(unittest.TestCase):
    def test_section12_form15_variants_prove_prior_reporting_in_recent_history(self):
        for form in SECTION_12_TERMINATION_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "424B4"],
                            "filingDate": ["2026-05-14", "2026-06-01"],
                        }
                    }
                }
                self.assertTrue(
                    followon_sanitizer.has_prior_periodic_report(
                        submissions,
                        "2026-06-01",
                    )
                )

    def test_section15d_form15_does_not_by_itself_disqualify_a_later_ipo(self):
        for form in SECTION_15D_SUSPENSION_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "424B4"],
                            "filingDate": ["2026-02-17", "2026-06-04"],
                        }
                    }
                }
                self.assertFalse(
                    followon_sanitizer.has_prior_periodic_report(
                        submissions,
                        "2026-06-04",
                    )
                )

    def test_section12_form15_variants_prove_prior_reporting_in_archived_history(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["S-1"],
                    "filingDate": ["2026-09-01"],
                },
                "files": [
                    {
                        "name": "CIK0000000001-submissions-001.json",
                        "filingFrom": "2020-01-01",
                        "filingTo": "2025-12-31",
                    }
                ],
            }
        }
        for form in SECTION_12_TERMINATION_FORMS:
            with self.subTest(form=form):
                archived = {
                    "form": [form],
                    "filingDate": ["2025-04-10"],
                }
                self.assertTrue(
                    archived_gate.has_prior_reporting_history(
                        submissions,
                        "2026-09-01",
                        archive_loader=lambda _name, archived=archived: archived,
                    )
                )

    def test_archived_section15d_form15_does_not_invent_prior_public_status(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["S-1"],
                    "filingDate": ["2026-09-01"],
                },
                "files": [
                    {
                        "name": "CIK0000000001-submissions-001.json",
                        "filingFrom": "2020-01-01",
                        "filingTo": "2025-12-31",
                    }
                ],
            }
        }
        for form in SECTION_15D_SUSPENSION_FORMS:
            with self.subTest(form=form):
                archived = {
                    "form": [form],
                    "filingDate": ["2025-04-10"],
                }
                self.assertFalse(
                    archived_gate.has_prior_reporting_history(
                        submissions,
                        "2026-09-01",
                        archive_loader=lambda _name, archived=archived: archived,
                    )
                )

    def test_same_day_section12_form15_does_not_guess_order_without_acceptance_times(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["15-12G", "424B4"],
                    "filingDate": ["2026-08-07", "2026-08-07"],
                }
            }
        }
        self.assertFalse(
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-08-07",
            )
        )


if __name__ == "__main__":
    unittest.main()
