import unittest
from unittest.mock import patch

import s1_price_range_history


class _FakeSoup:
    def get_text(self, separator=" ", strip=False):
        return (
            "We expect the initial public offering price per share to be between "
            "$40.00 and $44.00."
        )


class S1HistoryLoaderOfferingTermsTests(unittest.TestCase):
    def test_loader_retains_authoritative_range_and_base_share_terms(self):
        metadata = {"accession_no": "0001193125-26-396051"}
        offering_terms = {
            "total_shares": 50_000_000,
            "primary_shares": 13_500_000,
            "secondary_shares": 36_500_000,
            "source": "THE OFFERING primary + secondary rows",
            "confidence": "High",
            "conflict": False,
        }

        with (
            patch.object(
                s1_price_range_history.edgar_client,
                "build_filing_index_url",
                return_value="https://www.sec.gov/Archives/edgar/data/2133022/index.htm",
            ),
            patch.object(
                s1_price_range_history.filing_parser,
                "find_primary_document_url",
                return_value="https://www.sec.gov/Archives/edgar/data/2133022/d119865ds1a.htm",
            ),
            patch.object(
                s1_price_range_history.filing_parser,
                "fetch_document",
                return_value=_FakeSoup(),
            ),
            patch.object(
                s1_price_range_history.filing_parser,
                "extract_price_range",
                return_value={"range_low": 40.0, "range_high": 44.0},
            ),
            patch.object(
                s1_price_range_history.filing_parser,
                "extract_offering_terms",
                return_value=offering_terms,
            ),
        ):
            parsed, index_url = (
                s1_price_range_history._parse_s1_history_entry_with_offering_terms(
                    "0002133022", metadata
                )
            )

        self.assertEqual(
            parsed["price_range"], {"range_low": 40.0, "range_high": 44.0}
        )
        self.assertEqual(index_url, "https://www.sec.gov/Archives/edgar/data/2133022/index.htm")
        self.assertEqual(parsed["cover_page"]["offering_size_shares"], 50_000_000)
        self.assertEqual(parsed["cover_page"]["primary_offering_shares"], 13_500_000)
        self.assertEqual(parsed["cover_page"]["secondary_offering_shares"], 36_500_000)
        self.assertEqual(
            parsed["cover_page"]["offering_size_source"],
            "THE OFFERING primary + secondary rows",
        )
        self.assertEqual(parsed["cover_page"]["offering_size_confidence"], "High")
        self.assertFalse(parsed["cover_page"]["offering_size_conflict"])


if __name__ == "__main__":
    unittest.main()
