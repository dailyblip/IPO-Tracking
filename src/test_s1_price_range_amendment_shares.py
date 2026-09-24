import unittest

import s1_price_range_history as history


class S1PriceRangeAmendmentShareTests(unittest.TestCase):
    def _filing(self, *, filed="2026-08-04", source_date="2026-07-29"):
        return {
            "id": "0001193125-26-331510",
            "company": "Attovia Therapeutics, Inc.",
            "cik": "0001981666",
            "accession_no": "0001193125-26-331510",
            "form": "S-1/A",
            "filed": filed,
            "stage": "Pre-pricing",
            "price_range": "$15.00–$17.00",
            "filing_price": "$15.00–$17.00",
            "filing_price_source": {
                "source": "SEC EDGAR",
                "form": "S-1/A",
                "filing_date": source_date,
                "accession_no": "0001193125-26-323618",
                "sec_url": "https://www.sec.gov/Archives/edgar/data/1981666/000119312526323618/d12345ds1a.htm",
            },
            "ipo_size": None,
            "primary_offering_shares": 17_000_000,
        }

    def _historical_range_parse(self):
        return {
            "cover_page": {
                "offering_size_shares": 12_500_000,
                "primary_offering_shares": 12_500_000,
                "secondary_offering_shares": None,
                "offering_size_source": "primary offering shares on SEC cover",
                "offering_size_confidence": "High",
                "offering_size_conflict": False,
            }
        }

    def test_earlier_range_share_count_does_not_override_later_amendment_shares(self):
        filing = self._filing()

        repaired = history._apply_authoritative_offering_terms(
            filing,
            (15.0, 17.0),
            self._historical_range_parse(),
        )

        self.assertEqual(repaired["primary_offering_shares"], 17_000_000)
        self.assertIsNone(repaired["ipo_size"])
        self.assertNotIn("offering_size_source", repaired)
        self.assertNotIn("offering_size_confidence", repaired)

    def test_same_day_share_conflict_still_fails_closed(self):
        filing = self._filing(source_date="2026-08-04")

        with self.assertRaises(history.S1PriceRangeHistoryError):
            history._apply_authoritative_offering_terms(
                filing,
                (15.0, 17.0),
                self._historical_range_parse(),
            )


if __name__ == "__main__":
    unittest.main()
