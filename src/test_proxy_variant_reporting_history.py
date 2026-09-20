import unittest

import archived_reporting_history_gate
import followon_sanitizer


REGISTRANT_PROXY_REPORTING_FORMS = (
    "DEFA14A",
    "DEFA14C",
    "DEFM14A",
    "DEFM14C",
    "DEFR14A",
    "DEFR14C",
    "PREM14A",
    "PREM14C",
    "PRER14A",
    "PRER14C",
)


class ProxyVariantReportingHistoryTests(unittest.TestCase):
    def test_live_followon_gate_treats_registrant_proxy_variants_as_prior_reporting(self):
        for form in REGISTRANT_PROXY_REPORTING_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form, "424B4"],
                            "filingDate": ["2025-06-01", "2026-09-18"],
                        }
                    }
                }
                self.assertTrue(
                    followon_sanitizer.has_prior_periodic_report(
                        submissions,
                        "2026-09-18",
                    )
                )

    def test_archived_gate_treats_same_proxy_variants_as_prior_reporting(self):
        for form in REGISTRANT_PROXY_REPORTING_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": ["S-1"],
                            "filingDate": ["2026-09-01"],
                        },
                        "files": [
                            {
                                "name": "CIK0001234567-submissions-001.json",
                                "filingFrom": "2024-01-01",
                            }
                        ],
                    }
                }
                archived = {
                    "form": [form],
                    "filingDate": ["2025-06-01"],
                }

                self.assertTrue(
                    archived_reporting_history_gate.has_prior_reporting_history(
                        submissions,
                        "2026-09-18",
                        archive_loader=lambda name: archived,
                    )
                )

    def test_live_and_archived_proxy_reporting_policy_stays_aligned(self):
        expected = set(REGISTRANT_PROXY_REPORTING_FORMS)
        self.assertTrue(expected.issubset(followon_sanitizer.REPORTING_FORMS))
        self.assertTrue(
            expected.issubset(archived_reporting_history_gate.REPORTING_FORMS)
        )

    def test_same_day_proxy_variant_without_ordering_evidence_does_not_guess(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["DEFM14A", "424B4"],
                    "filingDate": ["2026-09-18", "2026-09-18"],
                }
            }
        }
        self.assertFalse(
            followon_sanitizer.has_prior_periodic_report(
                submissions,
                "2026-09-18",
            )
        )


if __name__ == "__main__":
    unittest.main()
