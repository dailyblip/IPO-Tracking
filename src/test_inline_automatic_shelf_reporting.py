import unittest

import followon_sanitizer


AUTOMATIC_SHELF_REPORTING_FORMS = (
    "S-3ASR",
    "S-3ASR/A",
    "F-3ASR",
    "F-3ASR/A",
)


class InlineAutomaticShelfReportingTests(unittest.TestCase):
    def _payload(self):
        return {
            "filings": [
                {
                    "company": "Already Public Co.",
                    "cik": "1234567",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-08-02",
                    "pricing_date": "2026-08-02",
                }
            ]
        }

    def test_followon_gate_removes_prior_automatic_shelf_issuers(self):
        for form in AUTOMATIC_SHELF_REPORTING_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form],
                            "filingDate": ["2026-08-01"],
                        }
                    }
                }
                updated, removed = followon_sanitizer.sanitize_payload(
                    self._payload(),
                    submissions_loader=lambda _cik, value=submissions: value,
                )
                self.assertEqual(updated["filings"], [])
                self.assertEqual(len(removed), 1)

    def test_followon_gate_does_not_infer_same_day_order(self):
        for form in AUTOMATIC_SHELF_REPORTING_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form],
                            "filingDate": ["2026-08-02"],
                        }
                    }
                }
                updated, removed = followon_sanitizer.sanitize_payload(
                    self._payload(),
                    submissions_loader=lambda _cik, value=submissions: value,
                )
                self.assertEqual(len(updated["filings"]), 1)
                self.assertEqual(removed, [])


if __name__ == "__main__":
    unittest.main()
