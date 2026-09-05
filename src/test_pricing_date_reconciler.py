import unittest

from bs4 import BeautifulSoup

import pricing_date_reconciler


class PricingDateReconcilerTests(unittest.TestCase):
    def test_extracts_explicit_final_prospectus_date_before_sec_filing(self):
        soup = BeautifulSoup(
            "<html><body>Prospectus dated August 18, 2026</body></html>",
            "html.parser",
        )
        self.assertEqual(
            pricing_date_reconciler.extract_authoritative_pricing_date(
                soup, "2026-08-19"
            ),
            "2026-08-18",
        )

    def test_extracts_standalone_date_from_labeled_back_cover(self):
        filler = "<p>" + ("x" * 125000) + "</p>"
        soup = BeautifulSoup(
            "<html><body>"
            + filler
            + "<div>PROSPECTUS</div><div>August 18, 2026</div>"
            + "</body></html>",
            "html.parser",
        )
        self.assertEqual(
            pricing_date_reconciler.extract_authoritative_pricing_date(
                soup, "2026-08-19"
            ),
            "2026-08-18",
        )

    def test_rejects_unlabeled_standalone_date(self):
        soup = BeautifulSoup(
            "<html><body><div>August 18, 2026</div></body></html>",
            "html.parser",
        )
        self.assertIsNone(
            pricing_date_reconciler.extract_authoritative_pricing_date(
                soup, "2026-08-19"
            )
        )

    def test_rejects_stale_back_cover_date(self):
        soup = BeautifulSoup(
            "<html><body><div>PROSPECTUS</div><div>July 1, 2026</div></body></html>",
            "html.parser",
        )
        self.assertIsNone(
            pricing_date_reconciler.extract_authoritative_pricing_date(
                soup, "2026-08-19"
            )
        )

    def test_reconciles_priced_424b4_to_explicit_prospectus_date(self):
        payload = {
            "filings": [
                {
                    "id": "lyntris-final",
                    "company": "Lyntris Inc.",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-08-19",
                    "pricing_date": "2026-08-19",
                    "offering_price": 17.5,
                }
            ]
        }
        soup = BeautifulSoup(
            "<html><body>The date of this prospectus is August 18, 2026.</body></html>",
            "html.parser",
        )

        reconciled, changed, checked, failures = pricing_date_reconciler.reconcile_payload(
            payload, soup_loader=lambda filing: soup
        )

        self.assertEqual(changed, 1)
        self.assertEqual(checked, 1)
        self.assertEqual(failures, [])
        self.assertEqual(reconciled["filings"][0]["pricing_date"], "2026-08-18")
        self.assertIn("generated_at", reconciled)

    def test_clears_unverified_sec_filing_date_fallback(self):
        payload = {
            "filings": [
                {
                    "id": "no-explicit-date-final",
                    "company": "Example Inc.",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-08-19",
                    "pricing_date": "2026-08-19",
                    "offering_price": 17.5,
                }
            ]
        }
        soup = BeautifulSoup(
            "<html><body>Final prospectus with no explicit prospectus date.</body></html>",
            "html.parser",
        )

        reconciled, changed, checked, failures = pricing_date_reconciler.reconcile_payload(
            payload, soup_loader=lambda filing: soup
        )

        self.assertEqual(changed, 1)
        self.assertEqual(checked, 1)
        self.assertEqual(failures, [])
        self.assertIsNone(reconciled["filings"][0]["pricing_date"])
        self.assertIn("generated_at", reconciled)

    def test_preserves_distinct_existing_pricing_date_when_prospectus_date_unresolved(self):
        payload = {
            "filings": [
                {
                    "id": "external-date-final",
                    "company": "Example Inc.",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-08-19",
                    "pricing_date": "2026-08-18",
                    "offering_price": 17.5,
                }
            ]
        }
        soup = BeautifulSoup(
            "<html><body>Final prospectus with no explicit prospectus date.</body></html>",
            "html.parser",
        )

        reconciled, changed, checked, failures = pricing_date_reconciler.reconcile_payload(
            payload, soup_loader=lambda filing: soup
        )

        self.assertEqual(changed, 0)
        self.assertEqual(checked, 1)
        self.assertEqual(failures, [])
        self.assertEqual(reconciled["filings"][0]["pricing_date"], "2026-08-18")
        self.assertNotIn("generated_at", reconciled)

    def test_retimes_lockup_dates_when_pricing_date_is_reconciled(self):
        payload = {
            "filings": [
                {
                    "id": "lyntris-final",
                    "company": "Lyntris Inc.",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-08-19",
                    "pricing_date": "2026-08-18",
                    "offering_price": 17.5,
                    "lockup_duration_value": 180,
                    "lockup_duration_unit": "days",
                    "lockup_end_date": "2027-02-15",
                    "lockup_terms": [
                        {
                            "duration_value": 180,
                            "duration_unit": "days",
                            "end_date": "2027-02-15",
                        }
                    ],
                    "people": [
                        {
                            "name": "Example Holder",
                            "lockup_duration_value": 180,
                            "lockup_duration_unit": "days",
                            "lockup_end_date": "2027-02-15",
                            "lockup_schedule": [
                                {
                                    "duration_value": 180,
                                    "duration_unit": "days",
                                    "end_date": "2027-02-15",
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        soup = BeautifulSoup(
            "<html><body>The date of this prospectus is August 18, 2026.</body></html>",
            "html.parser",
        )

        reconciled, changed, checked, failures = pricing_date_reconciler.reconcile_payload(
            payload, soup_loader=lambda filing: soup
        )

        filing = reconciled["filings"][0]
        self.assertEqual(changed, 1)
        self.assertEqual(checked, 1)
        self.assertEqual(failures, [])
        self.assertEqual(filing["pricing_date"], "2026-08-18")
        self.assertEqual(filing["lockup_end_date"], "2027-02-14")
        self.assertEqual(filing["lockup_terms"][0]["end_date"], "2027-02-14")
        self.assertEqual(filing["people"][0]["lockup_end_date"], "2027-02-14")
        self.assertEqual(
            filing["people"][0]["lockup_schedule"][0]["end_date"], "2027-02-14"
        )

    def test_rejects_prospectus_date_after_sec_filing(self):
        soup = BeautifulSoup(
            "<html><body>Prospectus dated August 20, 2026</body></html>",
            "html.parser",
        )
        self.assertIsNone(
            pricing_date_reconciler.extract_authoritative_pricing_date(
                soup, "2026-08-19"
            )
        )

    def test_rejects_stale_historical_prospectus_reference(self):
        soup = BeautifulSoup(
            "<html><body>Final prospectus dated July 1, 2026</body></html>",
            "html.parser",
        )
        self.assertIsNone(
            pricing_date_reconciler.extract_authoritative_pricing_date(
                soup, "2026-08-19"
            )
        )

    def test_non_priced_rows_are_not_loaded_or_changed(self):
        payload = {
            "filings": [
                {
                    "id": "prepricing",
                    "company": "Example Inc.",
                    "form": "S-1/A",
                    "stage": "Pre-pricing",
                    "filed": "2026-08-18",
                    "pricing_date": None,
                    "offering_price": None,
                }
            ]
        }

        def forbidden_loader(_filing):
            raise AssertionError("pre-pricing rows must not trigger final-prospectus lookup")

        reconciled, changed, checked, failures = pricing_date_reconciler.reconcile_payload(
            payload, soup_loader=forbidden_loader
        )

        self.assertEqual(changed, 0)
        self.assertEqual(checked, 0)
        self.assertEqual(failures, [])
        self.assertIsNone(reconciled["filings"][0]["pricing_date"])


if __name__ == "__main__":
    unittest.main()
