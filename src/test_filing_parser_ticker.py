import unittest

from bs4 import BeautifulSoup

from filing_parser import extract_cover_page_data


class FilingParserTickerTest(unittest.TestCase):
    @staticmethod
    def _soup(text):
        return BeautifulSoup(f"<html><body>{text}</body></html>", "html.parser")

    def test_listing_specific_ticker_beats_earlier_unrelated_symbol(self):
        soup = self._soup(
            'The symbol MW is used elsewhere in this prospectus. '
            'We have applied to list our common stock on Nasdaq under the ticker symbol “MENW”.'
        )
        self.assertEqual(extract_cover_page_data(soup)["ticker"], "MENW")

    def test_conflicting_listing_specific_tickers_fail_closed(self):
        soup = self._soup(
            'Our common stock is approved for listing on Nasdaq under the symbol “AAA”. '
            'It is also described as trading on NYSE under the symbol “BBB”.'
        )
        self.assertIsNone(extract_cover_page_data(soup)["ticker"])

    def test_simple_ticker_label_remains_supported_as_fallback(self):
        soup = self._soup('Ticker: ORIN')
        self.assertEqual(extract_cover_page_data(soup)["ticker"], "ORIN")


if __name__ == "__main__":
    unittest.main()
