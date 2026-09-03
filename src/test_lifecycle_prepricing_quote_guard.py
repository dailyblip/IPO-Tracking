import unittest

from bs4 import BeautifulSoup

from lifecycle_reconciler import _promote_prepricing_record


def _soup(body: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><body>{body}</body></html>", "html.parser")


class LifecyclePrepricingQuoteGuardTests(unittest.TestCase):
    def test_same_ticker_prepricing_quote_is_not_carried_into_final_promotion(self):
        prepricing = {
            "id": "s1:0002132582",
            "company": "Example Corp.",
            "ticker": "EXMP",
            "cik": "0002132582",
            "accession_no": "0001193125-26-346328",
            "form": "S-1/A",
            "filed": "2026-08-12",
            "stage": "Pre-pricing",
            "current_price": 99.99,
            "price_updated": "2026-08-12T18:00:00+00:00",
            "signals": [
                "Registration statement amended — IPO remains pre-pricing",
                "Largest named holding currently valued at approximately $99M",
            ],
            "people": [{"name": "Preliminary Holder", "shares": 1_000_000}],
            "people_count": 1,
        }
        final_meta = {
            "company_name": "Example Corp.",
            "ticker": "EXMP",
            "cik": "0002132582",
            "accession_no": "0001193125-26-356916",
            "form_type": "424B4",
            "filing_date": "2026-08-19",
        }
        final_soup = _soup(
            "symbol: EXMP. The initial public offering price is $17.50 per share. "
            "THE OFFERING Common stock offered by us 5,000,000 shares."
        )

        promoted = _promote_prepricing_record(prepricing, final_meta, final_soup)

        self.assertIsNotNone(promoted)
        self.assertEqual(promoted["form"], "424B4")
        self.assertEqual(promoted["stage"], "Priced")
        self.assertNotIn("current_price", promoted)
        self.assertNotIn("price_updated", promoted)
        self.assertNotIn(
            "currently valued",
            " ".join(promoted.get("signals") or []).casefold(),
        )
        self.assertEqual(promoted["people"], [])
        self.assertEqual(promoted["people_count"], 0)


if __name__ == "__main__":
    unittest.main()
