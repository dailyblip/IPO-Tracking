import unittest

from feed_schema_contract import _priced_filing_price_provenance_errors


class FilingPriceSourceUrlContractTests(unittest.TestCase):
    @staticmethod
    def _filing():
        return {
            "cik": "0001234567",
            "form": "424B4",
            "stage": "Priced",
            "pricing_date": "2026-08-20",
            "filing_price": "15-17",
            "price_range": "15-17",
            "filing_price_source": {
                "source": "SEC EDGAR",
                "form": "S-1/A",
                "filing_date": "2026-08-18",
                "accession_no": "0001193125-26-123455",
                "sec_url": (
                    "https://www.sec.gov/Archives/edgar/data/1234567/"
                    "000119312526123455/example-s1a.htm"
                ),
            },
        }

    def test_canonical_same_accession_archive_path_is_accepted(self):
        self.assertEqual(_priced_filing_price_provenance_errors(0, self._filing()), [])

    def test_expected_accession_in_query_cannot_mask_wrong_archive_directory(self):
        filing = self._filing()
        filing["filing_price_source"] = dict(filing["filing_price_source"])
        filing["filing_price_source"]["sec_url"] = (
            "https://www.sec.gov/Archives/edgar/data/1234567/"
            "000119312526999999/example-s1a.htm"
            "?expected=000119312526123455"
        )
        errors = _priced_filing_price_provenance_errors(0, filing)
        self.assertTrue(
            any("canonical SEC Archives filing URL" in error for error in errors),
            errors,
        )

    def test_expected_accession_in_filename_cannot_mask_wrong_archive_directory(self):
        filing = self._filing()
        filing["filing_price_source"] = dict(filing["filing_price_source"])
        filing["filing_price_source"]["sec_url"] = (
            "https://www.sec.gov/Archives/edgar/data/1234567/"
            "000119312526999999/000119312526123455-s1a.htm"
        )
        errors = _priced_filing_price_provenance_errors(0, filing)
        self.assertTrue(
            any("does not match source accession" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
