import unittest

import archived_reporting_history_gate as gate


class ExchangeActRegistrationHistoryGateTests(unittest.TestCase):
    def test_prior_form_10_registration_is_reporting_history(self):
        for form in ("10-12B", "10-12B/A", "10-12G", "10-12G/A"):
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form],
                            "filingDate": ["2026-06-01"],
                        },
                        "files": [],
                    }
                }
                self.assertTrue(
                    gate.has_prior_reporting_history(submissions, "2026-07-01")
                )

    def test_same_day_form_10_registration_does_not_infer_event_order(self):
        submissions = {
            "filings": {
                "recent": {
                    "form": ["10-12B"],
                    "filingDate": ["2026-07-01"],
                },
                "files": [],
            }
        }
        self.assertFalse(
            gate.has_prior_reporting_history(submissions, "2026-07-01")
        )

    def test_archived_form_10_registration_is_not_missed(self):
        submissions = {
            "filings": {
                "recent": {"form": [], "filingDate": []},
                "files": [
                    {
                        "name": "CIK0001234567-submissions-001.json",
                        "filingFrom": "2024-01-01",
                    }
                ],
            }
        }

        def archive_loader(name):
            self.assertEqual(name, "CIK0001234567-submissions-001.json")
            return {
                "form": ["10-12G"],
                "filingDate": ["2025-11-15"],
            }

        self.assertTrue(
            gate.has_prior_reporting_history(
                submissions,
                "2026-07-01",
                archive_loader=archive_loader,
            )
        )

    def test_release_gate_removes_prepricing_and_final_rows_after_prior_form_10(self):
        prepricing = {
            "company": "Already Reporting Prepricing Co",
            "cik": "1234567",
            "accession_no": "0001234567-26-000001",
            "form": "S-1",
            "stage": "Pre-pricing",
            "filed": "2026-07-01",
        }
        final = {
            "company": "Already Reporting Final Co",
            "cik": "7654321",
            "accession_no": "0007654321-26-000002",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-07-02",
            "pricing_date": "2026-07-01",
            "offering_price": 12.0,
        }

        def submissions_loader(cik):
            form = "10-12B" if cik.endswith("1234567") else "10-12G/A"
            return {
                "filings": {
                    "recent": {
                        "form": [form],
                        "filingDate": ["2026-05-15"],
                    },
                    "files": [],
                }
            }

        watch, queue, excluded_prepricing, excluded_final = gate.sanitize_payloads(
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
