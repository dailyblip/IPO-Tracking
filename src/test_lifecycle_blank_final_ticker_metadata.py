import unittest

from bs4 import BeautifulSoup

from lifecycle_reconciler import reconcile_payload


def _soup(body: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><body>{body}</body></html>", "html.parser")


def _release_grade_final(**overrides):
    record = {
        "id": "0001193125-26-356916",
        "company": "Lyntris Inc.",
        "ticker": "LYNX",
        "cik": "0002132582",
        "accession_no": "0001193125-26-356916",
        "sec_url": (
            "https://www.sec.gov/Archives/edgar/data/2132582/000119312526356916/"
            "0001193125-26-356916-index.htm"
        ),
        "form": "424B4",
        "filed": "2026-08-19",
        "filing_date": "2026-07-01",
        "stage": "Priced",
        "pricing_date": "2026-08-18",
        "offering_price": 10.0,
        "value": 50_000_000.0,
        "value_label": "$50M",
        "primary_offering_shares": 5_000_000,
        "secondary_offering_shares": None,
        "offering_size_source": "final 424B4 explicit issuer-only THE OFFERING row",
        "offering_size_confidence": "High",
        "current_price": 22.0,
        "price_updated": "2026-08-19T15:00:00+00:00",
        "people": [{
            "name": "Final Holder",
            "shares_after": 750_000,
            "cash_value": 1_000_000,
            "liquid_value": 500_000,
            "locked_value": 500_000,
            "valuation_as_of": "2026-08-19",
        }],
        "people_count": 1,
        "signals": [
            "Offering priced at $10.00 per share",
            "Current market value approximately $16.5M",
        ],
    }
    record.update(overrides)
    return record


def _final_meta(**overrides):
    meta = {
        "company_name": "Lyntris Inc.",
        "ticker": None,
        "cik": "0002132582",
        "accession_no": "0001193125-26-356916",
        "form_type": "424B4",
        "filing_date": "2026-08-19",
    }
    meta.update(overrides)
    return meta


class BlankFinalTickerMetadataTests(unittest.TestCase):
    def test_blank_discovery_ticker_forces_final_document_recheck(self):
        final = _release_grade_final()
        calls = []
        soup = _soup(
            "NASDAQ Global Market under the symbol: LYNX. "
            "The initial public offering price is $10.00 per share. "
            "THE OFFERING Common stock offered by us 5,000,000 shares."
        )

        payload, repaired, removed = reconcile_payload(
            {"filings": [final]},
            [_final_meta()],
            lambda meta: calls.append(meta) or soup,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(removed, 0)
        result = payload["filings"][0]
        self.assertEqual(result["ticker"], "LYNX")
        self.assertEqual(result["current_price"], 22.0)
        self.assertIn(repaired, (0, 1))

    def test_final_document_silence_clears_unverified_ticker_and_quote_derivatives(self):
        final = _release_grade_final()
        soup = _soup(
            "The initial public offering price is $10.00 per share. "
            "THE OFFERING Common stock offered by us 5,000,000 shares."
        )

        payload, repaired, removed = reconcile_payload(
            {"filings": [final]},
            [_final_meta()],
            lambda _: soup,
        )

        self.assertEqual(repaired, 1)
        self.assertEqual(removed, 0)
        result = payload["filings"][0]
        self.assertEqual(result["ticker"], "")
        self.assertNotIn("current_price", result)
        self.assertNotIn("price_updated", result)
        self.assertEqual(result["people"][0]["shares_after"], 750_000)
        for field in ("cash_value", "liquid_value", "locked_value", "valuation_as_of"):
            self.assertNotIn(field, result["people"][0])
        self.assertNotIn("current market value", " ".join(result["signals"]).casefold())

    def test_final_document_failure_keeps_priced_facts_but_drops_unverified_ticker(self):
        final = _release_grade_final()

        def fail_loader(_):
            raise RuntimeError("temporary SEC document failure")

        payload, repaired, removed = reconcile_payload(
            {"filings": [final]},
            [_final_meta()],
            fail_loader,
        )

        self.assertEqual(repaired, 1)
        self.assertEqual(removed, 0)
        result = payload["filings"][0]
        self.assertEqual(result["ticker"], "")
        self.assertEqual(result["offering_price"], 10.0)
        self.assertEqual(result["pricing_date"], "2026-08-18")
        self.assertEqual(result["value"], 50_000_000.0)
        self.assertNotIn("current_price", result)
        self.assertNotIn("price_updated", result)
        self.assertNotIn("current market value", " ".join(result["signals"]).casefold())


if __name__ == "__main__":
    unittest.main()
