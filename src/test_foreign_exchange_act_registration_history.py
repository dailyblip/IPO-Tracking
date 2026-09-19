import unittest

import archived_reporting_history_gate as archived_gate
import followon_sanitizer


FOREIGN_EXCHANGE_ACT_REGISTRATION_FORMS = (
    "20FR12B",
    "20FR12B/A",
    "20FR12G",
    "20FR12G/A",
    "40FR12B",
    "40FR12B/A",
    "40FR12G",
    "40FR12G/A",
)


class ForeignExchangeActRegistrationHistoryTests(unittest.TestCase):
    def test_prior_foreign_exchange_act_registration_is_reporting_history(self):
        for form in FOREIGN_EXCHANGE_ACT_REGISTRATION_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form],
                            "filingDate": ["2026-06-01"],
                        }
                    }
                }
                self.assertTrue(
                    followon_sanitizer.has_prior_periodic_report(
                        submissions, "2026-07-01"
                    )
                )

    def test_same_day_foreign_registration_does_not_infer_event_order(self):
        for form in FOREIGN_EXCHANGE_ACT_REGISTRATION_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form],
                            "filingDate": ["2026-07-01"],
                        }
                    }
                }
                self.assertFalse(
                    followon_sanitizer.has_prior_periodic_report(
                        submissions, "2026-07-01"
                    )
                )

    def test_final_424b4_is_removed_after_prior_foreign_registration(self):
        final = {
            "company": "Already Reporting Foreign Issuer",
            "cik": "7654321",
            "accession_no": "0007654321-26-000002",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-07-02",
            "pricing_date": "2026-07-01",
            "offering_price": 12.0,
        }

        updated, removed = followon_sanitizer.sanitize_payload(
            {"filings": [final]},
            submissions_loader=lambda cik: {
                "filings": {
                    "recent": {
                        "form": ["20FR12B"],
                        "filingDate": ["2026-05-15"],
                    }
                }
            },
        )

        self.assertEqual(updated["filings"], [])
        self.assertEqual(removed, [final])

    def test_archived_foreign_registration_is_not_missed(self):
        for form in FOREIGN_EXCHANGE_ACT_REGISTRATION_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {"form": [], "filingDate": []},
                        "files": [
                            {
                                "name": "CIK0007654321-submissions-001.json",
                                "filingFrom": "2024-01-01",
                            }
                        ],
                    }
                }

                def archive_loader(name):
                    self.assertEqual(name, "CIK0007654321-submissions-001.json")
                    return {
                        "form": [form],
                        "filingDate": ["2025-11-15"],
                    }

                self.assertTrue(
                    archived_gate.has_prior_reporting_history(
                        submissions,
                        "2026-07-01",
                        archive_loader=archive_loader,
                    )
                )

    def test_archived_gate_removes_prepricing_and_final_rows_after_prior_foreign_registration(self):
        prepricing = {
            "company": "Already Reporting Foreign Prepricing Co",
            "cik": "1234567",
            "accession_no": "0001234567-26-000001",
            "form": "S-1",
            "stage": "Pre-pricing",
            "filed": "2026-07-01",
        }
        final = {
            "company": "Already Reporting Foreign Final Co",
            "cik": "7654321",
            "accession_no": "0007654321-26-000002",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-07-02",
            "pricing_date": "2026-07-01",
            "offering_price": 12.0,
        }

        def submissions_loader(cik):
            form = "20FR12B" if cik.endswith("1234567") else "40FR12G/A"
            return {
                "filings": {
                    "recent": {
                        "form": [form],
                        "filingDate": ["2026-05-15"],
                    },
                    "files": [],
                }
            }

        watch, queue, excluded_prepricing, excluded_final = archived_gate.sanitize_payloads(
            {"filings": [prepricing]},
            {"filings": [final]},
            submissions_loader=submissions_loader,
            archive_loader=lambda name: self.fail(f"unexpected archive load: {name}"),
        )

        self.assertEqual(watch["filings"], [])
        self.assertEqual(queue["filings"], [])
        self.assertEqual(excluded_prepricing, {"0001234567"})
        self.assertEqual(len(excluded_final), 1)


if __name__ == "__main__":
    unittest.main()
