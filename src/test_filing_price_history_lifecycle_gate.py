import unittest

import filing_price_history


class PricedHistoryLifecycleGateTests(unittest.TestCase):
    def _row(self, **overrides):
        row = {
            "id": "priced-1",
            "company": "Example Corp.",
            "ticker": "EXM",
            "cik": "1234567",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-20",
            "pricing_date": "2026-08-20",
            "offering_price": None,
            "filing_price": None,
        }
        row.update(overrides)
        return row

    def test_priced_row_missing_final_price_still_runs_filing_price_history_review(self):
        calls = []
        history = [
            {
                "form_type": "S-1/A",
                "accession_no": "amend-1",
                "filing_date": "2026-08-18",
            }
        ]

        def history_loader(cik, pricing_date):
            calls.append((cik, pricing_date))
            return history

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self._row()]},
            history_loader=history_loader,
            registration_loader=lambda cik, metadata: (
                {"price_range": {"range_low": 14, "range_high": 16}},
                "https://www.sec.gov/amend-1",
            ),
        )

        self.assertEqual(calls, [("0001234567", "2026-08-20")])
        self.assertEqual(payload["filings"][0]["filing_price"], "14-16")
        self.assertEqual((recovered, checked), (1, 1))
        self.assertIsNone(payload["filings"][0]["offering_price"])

    def test_priced_row_without_pricing_date_cannot_bypass_history_gate(self):
        called = False

        def history_loader(cik, pricing_date):
            nonlocal called
            called = True
            return []

        with self.assertRaises(filing_price_history.FilingPriceHistoryError):
            filing_price_history.recover_payload_filing_prices(
                {"filings": [self._row(pricing_date=None)]},
                history_loader=history_loader,
                registration_loader=lambda cik, metadata: ({}, ""),
            )

        self.assertFalse(called)

    def test_prepricing_row_remains_outside_final_history_gate(self):
        row = self._row(
            form="S-1/A",
            stage="Pre-pricing",
            pricing_date=None,
            offering_price=None,
            filing_price="14-16",
        )
        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [row]},
            history_loader=lambda *args: (_ for _ in ()).throw(AssertionError("should not run")),
            registration_loader=lambda *args: (_ for _ in ()).throw(AssertionError("should not run")),
        )
        self.assertEqual(payload["filings"][0], row)
        self.assertEqual((recovered, checked), (0, 0))

    def test_recovery_ignores_registration_history_before_current_ipo(self):
        calls = []
        history = [
            {
                "form_type": "S-1",
                "accession_no": "current-initial",
                "filing_date": "2026-08-01",
            },
            {
                "form_type": "S-1/A",
                "accession_no": "stale-prior-registration",
                "filing_date": "2025-11-15",
            },
        ]

        def registration_loader(cik, metadata):
            calls.append(metadata["accession_no"])
            if metadata["accession_no"] == "current-initial":
                return (
                    {"price_range": {"range_low": None, "range_high": None}},
                    "https://www.sec.gov/current-initial",
                )
            return (
                {"price_range": {"range_low": 9, "range_high": 11}},
                "https://www.sec.gov/stale-prior-registration",
            )

        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {"filings": [self._row(filing_date="2026-08-01")]},
            history_loader=lambda cik, pricing_date: history,
            registration_loader=registration_loader,
        )

        self.assertEqual(calls, ["current-initial"])
        self.assertIsNone(payload["filings"][0]["filing_price"])
        self.assertEqual((recovered, checked), (0, 1))


if __name__ == "__main__":
    unittest.main()
