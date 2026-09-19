import unittest

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


if __name__ == "__main__":
    unittest.main()
