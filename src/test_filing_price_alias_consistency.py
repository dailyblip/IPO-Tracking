import unittest

import filing_price_history


class FilingPriceAliasConsistencyTests(unittest.TestCase):
    def _row(self, **overrides):
        row = {
            "id": "priced-1",
            "company": "Example Corp.",
            "ticker": "EXM",
            "cik": "1234567",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-08-20",
            "filing_date": "2026-08-01",
            "pricing_date": "2026-08-20",
            "offering_price": 17.0,
            "filing_price": None,
        }
        row.update(overrides)
        return row

    def _history(self):
        return [
            {
                "form_type": "S-1/A",
                "accession_no": "0001193125-26-123456",
                "filing_date": "2026-08-18",
                "file_number": "333-300001",
            },
            {
                "form_type": "S-1",
                "accession_no": "0001193125-26-100001",
                "filing_date": "2026-08-01",
                "file_number": "333-300001",
            },
        ]

    def _source(self):
        return {
            "source": "SEC EDGAR",
            "form": "S-1/A",
            "filing_date": "2026-08-18",
            "accession_no": "0001193125-26-123456",
            "sec_url": "https://www.sec.gov/amend",
        }

    def test_recovered_history_replaces_stale_price_range_alias(self):
        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {
                "filings": [
                    self._row(
                        filing_price="18-20",
                        price_range="18-20",
                    )
                ]
            },
            history_loader=lambda cik, pricing_date: self._history(),
            registration_loader=lambda cik, metadata: (
                {"price_range": {"range_low": 14, "range_high": 16}},
                "https://www.sec.gov/amend",
            ),
        )

        filing = payload["filings"][0]
        self.assertEqual(filing["filing_price"], "14-16")
        self.assertEqual(filing["price_range"], "14-16")
        self.assertEqual(filing["filing_price_source"]["accession_no"], "0001193125-26-123456")
        self.assertEqual((recovered, checked), (1, 1))

    def test_verified_filing_price_overrides_stale_price_range_without_reparse(self):
        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {
                "filings": [
                    self._row(
                        filing_price="14-16",
                        price_range="18-20",
                        filing_price_source=self._source(),
                    )
                ]
            },
            history_loader=lambda cik, pricing_date: self._history(),
            registration_loader=lambda *args: (_ for _ in ()).throw(
                AssertionError("matching authoritative source should not be reparsed")
            ),
        )

        filing = payload["filings"][0]
        self.assertEqual(filing["filing_price"], "14-16")
        self.assertEqual(filing["price_range"], "14-16")
        self.assertEqual((recovered, checked), (0, 0))

    def test_verified_price_range_alias_backfills_canonical_filing_price(self):
        payload, recovered, checked = filing_price_history.recover_payload_filing_prices(
            {
                "filings": [
                    self._row(
                        filing_price=None,
                        price_range="14-16",
                        filing_price_source=self._source(),
                    )
                ]
            },
            history_loader=lambda cik, pricing_date: self._history(),
            registration_loader=lambda *args: (_ for _ in ()).throw(
                AssertionError("matching authoritative source should not be reparsed")
            ),
        )

        filing = payload["filings"][0]
        self.assertEqual(filing["filing_price"], "14-16")
        self.assertEqual(filing["price_range"], "14-16")
        self.assertEqual((recovered, checked), (0, 0))


if __name__ == "__main__":
    unittest.main()
