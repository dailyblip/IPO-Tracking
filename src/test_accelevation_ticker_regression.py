import unittest

import ticker_listing_reconciler as reconciler


class AccelevationTickerRegressionTests(unittest.TestCase):
    def test_intend_to_apply_listing_language_is_authoritative(self):
        text = (
            "We intend to apply to list our Class A common stock on The Nasdaq Global "
            "Select Market, or Nasdaq, under the symbol “ACCV.” However, no assurance "
            "can be given that our listing application will be approved."
        )
        self.assertEqual(reconciler.extract_current_listing_tickers(text), {"ACCV"})

    def test_later_amendment_can_carry_forward_intend_to_apply_symbol(self):
        payload = {
            "filings": [
                {
                    "id": "amendment",
                    "accession_no": "0001628280-26-061542",
                    "company": "Accelevation Holdings Corp.",
                    "cik": "0002141406",
                    "ticker": "",
                    "form": "S-1/A",
                    "filed": "2026-09-11",
                    "sec_url": "https://www.sec.gov/amendment-index.htm",
                },
                {
                    "id": "initial",
                    "accession_no": "0001628280-26-060083",
                    "company": "Accelevation Holdings Corp.",
                    "cik": "0002141406",
                    "ticker": "",
                    "form": "S-1",
                    "filed": "2026-09-02",
                    "sec_url": "https://www.sec.gov/initial-index.htm",
                },
            ]
        }
        texts = {
            "amendment": "This amendment updates financial statements and risk factors.",
            "initial": (
                "We intend to apply to list our Class A common stock on The Nasdaq "
                "Global Select Market under the symbol “ACCV.”"
            ),
        }

        updated, conflicts = reconciler.reconcile_payload(
            payload, fetch_text=lambda record: texts[record["id"]]
        )

        self.assertEqual((updated, conflicts), (2, 0))
        self.assertEqual(payload["filings"][0]["ticker"], "ACCV")
        self.assertEqual(payload["filings"][1]["ticker"], "ACCV")


if __name__ == "__main__":
    unittest.main()
