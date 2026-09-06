import unittest
from unittest.mock import patch

import lifecycle_reconciler


class _SoupWithoutExactSize:
    def get_text(self, separator=" ", strip=True):
        return "Final prospectus text without an exact THE OFFERING share-count row."


class LifecycleOfferingSizePreservationTests(unittest.TestCase):
    def _record(self, *, price=20.0, value=180_000_000.0, primary=9_000_000):
        return {
            "id": "0000000000-26-000001",
            "accession_no": "0000000000-26-000001",
            "cik": "1234567",
            "company": "Example Operating Co",
            "ticker": "TEST",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-20",
            "pricing_date": "2026-08-19",
            "offering_price": price,
            "value": value,
            "value_label": "$180M",
            "primary_offering_shares": primary,
            "secondary_offering_shares": None,
            "offering_size_source": "SEC final 424B4 offering terms",
            "offering_size_confidence": "Medium",
            "offering_size_conflict": False,
            "people": [],
            "signals": [],
        }

    def _meta(self):
        return {
            "cik": "1234567",
            "ticker": "TEST",
            "filing_date": "2026-08-20",
            "accession_no": "0000000000-26-000001",
        }

    @patch("lifecycle_reconciler.edgar_client.build_filing_index_url", return_value="https://sec.example/final")
    @patch("lifecycle_reconciler.filing_parser.extract_cover_page_data", return_value={"offering_price": 20.0, "ticker": "TEST"})
    def test_missing_optional_reparse_does_not_erase_supported_size(self, _cover, _url):
        repaired = lifecycle_reconciler._apply_final_terms(
            self._record(), self._meta(), _SoupWithoutExactSize()
        )

        self.assertEqual(repaired["primary_offering_shares"], 9_000_000)
        self.assertIsNone(repaired["secondary_offering_shares"])
        self.assertEqual(repaired["value"], 180_000_000.0)
        self.assertEqual(repaired["value_label"], "$180M")
        self.assertEqual(repaired["offering_size_source"], "SEC final 424B4 offering terms")
        self.assertEqual(repaired["offering_size_confidence"], "Medium")
        self.assertNotIn("offering_size_conflict", repaired)

    @patch("lifecycle_reconciler.edgar_client.build_filing_index_url", return_value="https://sec.example/final")
    @patch("lifecycle_reconciler.filing_parser.extract_cover_page_data", return_value={"offering_price": 20.0, "ticker": "TEST"})
    def test_price_repair_recomputes_supported_size_from_public_share_count(self, _cover, _url):
        repaired = lifecycle_reconciler._apply_final_terms(
            self._record(price=18.0, value=162_000_000.0),
            self._meta(),
            _SoupWithoutExactSize(),
        )

        self.assertEqual(repaired["offering_price"], 20.0)
        self.assertEqual(repaired["primary_offering_shares"], 9_000_000)
        self.assertEqual(repaired["value"], 180_000_000.0)
        self.assertEqual(repaired["value_label"], "$180M")

    @patch("lifecycle_reconciler.edgar_client.build_filing_index_url", return_value="https://sec.example/final")
    @patch("lifecycle_reconciler.filing_parser.extract_cover_page_data", return_value={"offering_price": 20.0, "ticker": "TEST"})
    def test_price_repair_clears_standalone_stale_value_without_share_support(self, _cover, _url):
        record = self._record(price=18.0, value=162_000_000.0, primary=None)
        repaired = lifecycle_reconciler._apply_final_terms(
            record, self._meta(), _SoupWithoutExactSize()
        )

        self.assertEqual(repaired["offering_price"], 20.0)
        self.assertIsNone(repaired["value"])
        self.assertIsNone(repaired["value_label"])
        self.assertIsNone(repaired["offering_size_source"])
        self.assertEqual(repaired["offering_size_confidence"], "Unresolved")


if __name__ == "__main__":
    unittest.main()
