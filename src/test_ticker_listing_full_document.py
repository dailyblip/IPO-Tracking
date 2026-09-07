import unittest
from unittest.mock import patch

import ticker_listing_reconciler as reconciler


class _FakeSoup:
    def __init__(self, text):
        self.text = text

    def get_text(self, separator=" ", strip=False):
        return self.text


class TickerListingFullDocumentTests(unittest.TestCase):
    def test_fetch_filing_text_does_not_truncate_late_listing_statement(self):
        prefix = "x" * 100500
        late_listing = (
            " We have applied to list our common stock on Nasdaq under the symbol LATE."
        )
        full_text = prefix + late_listing
        record = {
            "form": "S-1/A",
            "sec_url": "https://www.sec.gov/example-index.htm",
        }

        with patch.object(
            reconciler.filing_parser,
            "find_primary_document_url",
            return_value="https://www.sec.gov/example.htm",
        ), patch.object(
            reconciler.filing_parser,
            "fetch_document",
            return_value=_FakeSoup(full_text),
        ):
            text = reconciler._fetch_filing_text(record)

        self.assertEqual(text, full_text)
        self.assertEqual(reconciler.extract_current_listing_tickers(text), {"LATE"})


if __name__ == "__main__":
    unittest.main()
