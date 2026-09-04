import unittest

from bs4 import BeautifulSoup

from lifecycle_reconciler import _promote_prepricing_record


def _soup(body: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><body>{body}</body></html>", "html.parser")


def _record(**overrides):
    record = {
        "id": "s1:0002132582",
        "company": "Lyntris Inc.",
        "ticker": "LYNX",
        "cik": "0002132582",
        "accession_no": "0001193125-26-346328",
        "form": "S-1/A",
        "filed": "2026-08-12",
        "filing_date": "2026-07-01",
        "stage": "Pre-pricing",
        "filing_price": "16-18",
        "price_range": "16-18",
        "filing_price_source": {
            "form": "S-1/A",
            "filing_date": "2026-08-12",
            "accession_no": "0001193125-26-346328",
            "sec_url": "https://www.sec.gov/Archives/edgar/data/2132582/000119312526346328/",
        },
        "signals": ["Registration statement amended — IPO remains pre-pricing"],
    }
    record.update(overrides)
    return record


def _meta():
    return {
        "company_name": "Lyntris Inc.",
        "ticker": "LYNX",
        "cik": "0002132582",
        "accession_no": "0001193125-26-356916",
        "form_type": "424B4",
        "filing_date": "2026-08-19",
    }


def _final_soup():
    return _soup(
        "symbol: LYNX. The initial public offering price is $17.50 per share. "
        "THE OFFERING Common stock offered by us 5,714,286 shares. "
        "Common stock offered by the selling stockholders 11,285,714 shares."
    )


class LifecycleHandoffContractTests(unittest.TestCase):
    def test_promotion_preserves_authoritative_preliminary_price_and_provenance(self):
        promoted = _promote_prepricing_record(_record(), _meta(), _final_soup())

        self.assertIsNotNone(promoted)
        self.assertEqual(promoted["form"], "424B4")
        self.assertEqual(promoted["stage"], "Priced")
        self.assertEqual(promoted["filing_price"], "16-18")
        self.assertEqual(promoted["price_range"], "16-18")
        self.assertEqual(
            promoted["filing_price_source"],
            _record()["filing_price_source"],
        )

    def test_same_ticker_promotion_still_clears_prepricing_quote_and_market_signal(self):
        record = _record(
            current_price=42.0,
            price_updated="2026-08-18T15:00:00+00:00",
            signals=[
                "Current market value reflects a pre-pricing quote",
                "Registration statement amended — IPO remains pre-pricing",
            ],
        )

        promoted = _promote_prepricing_record(record, _meta(), _final_soup())

        self.assertIsNotNone(promoted)
        self.assertEqual(promoted["ticker"], "LYNX")
        self.assertNotIn("current_price", promoted)
        self.assertNotIn("price_updated", promoted)
        self.assertNotIn("current market value", " ".join(promoted["signals"]).casefold())
        self.assertNotIn("remains pre-pricing", " ".join(promoted["signals"]).casefold())


if __name__ == "__main__":
    unittest.main()
