import unittest

from dashboard_export import _public_only


class FilingPriceProvenancePublicAllowlistTests(unittest.TestCase):
    def test_preserves_authoritative_filing_price_provenance(self):
        provenance = {
            "source": "SEC EDGAR",
            "form": "S-1/A",
            "filing_date": "2026-08-12",
            "accession_no": "0001234567-26-000001",
            "sec_url": "https://www.sec.gov/Archives/edgar/data/1234567/example-index.htm",
        }
        filing = {
            "id": "0001234567-26-000002",
            "filing_price": "19-22",
            "filing_price_source": provenance,
            "people": [],
            "internal_note": "must not publish",
        }

        public = _public_only(filing)

        self.assertEqual(public["filing_price_source"], provenance)
        self.assertNotIn("internal_note", public)


if __name__ == "__main__":
    unittest.main()
