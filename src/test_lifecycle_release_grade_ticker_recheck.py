import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

import lifecycle_reconciler
from lifecycle_reconciler import reconcile_payload


def _soup(body: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><body>{body}</body></html>", "html.parser")


def _release_grade_final(**overrides):
    record = {
        "id": "0001193125-26-356916",
        "company": "Lyntris Inc.",
        "ticker": "OLD",
        "cik": "0002132582",
        "accession_no": "0001193125-26-356916",
        "form": "424B4",
        "filed": "2026-08-19",
        "filing_date": "2026-07-01",
        "stage": "Priced",
        "pricing_date": "2026-08-18",
        "offering_price": 10.0,
        "value": 50_000_000.0,
        "value_label": "$50M",
        "primary_offering_shares": 5_000_000,
        "secondary_offering_shares": None,
        "offering_size_source": "final 424B4 explicit issuer-only THE OFFERING row",
        "offering_size_confidence": "High",
        "current_price": 22.0,
        "price_updated": "2026-08-19T15:00:00+00:00",
        "people": [{
            "name": "Final Holder",
            "shares_after": 750_000,
            "cash_value": 1_000_000,
            "liquid_value": 500_000,
            "locked_value": 500_000,
            "valuation_as_of": "2026-08-19",
        }],
        "people_count": 1,
        "signals": [
            "Offering priced at $10.00 per share",
            "Current market value approximately $16.5M",
        ],
    }
    record.update(overrides)
    return record


def _final_meta(**overrides):
    meta = {
        "company_name": "Lyntris Inc.",
        "ticker": "LYNX",
        "cik": "0002132582",
        "accession_no": "0001193125-26-356916",
        "form_type": "424B4",
        "filing_date": "2026-08-19",
    }
    meta.update(overrides)
    return meta


class ReleaseGradeFinalTickerRecheckTests(unittest.TestCase):
    def test_sec_metadata_ticker_mismatch_forces_authoritative_final_repair(self):
        final = _release_grade_final()
        soup = _soup(
            "NASDAQ Global Market under the symbol: LYNX. "
            "The initial public offering price is $10.00 per share. "
            "THE OFFERING Common stock offered by us 5,000,000 shares."
        )

        payload, repaired, removed = reconcile_payload(
            {"filings": [final]},
            [_final_meta()],
            lambda _: soup,
        )

        self.assertEqual(repaired, 1)
        self.assertEqual(removed, 0)
        result = payload["filings"][0]
        self.assertEqual(result["ticker"], "LYNX")
        self.assertNotIn("current_price", result)
        self.assertNotIn("price_updated", result)
        self.assertEqual(result["people"][0]["shares_after"], 750_000)
        for field in ("cash_value", "liquid_value", "locked_value", "valuation_as_of"):
            self.assertNotIn(field, result["people"][0])
        self.assertNotIn("current market value", " ".join(result["signals"]).casefold())

    def test_release_grade_final_still_runs_cheap_sec_metadata_identity_check(self):
        payload = {"filings": [_release_grade_final(ticker="LYNX")]}
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "filings.json"
            output.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(
                lifecycle_reconciler.edgar_client,
                "find_recent_424b4_filings",
                return_value=[],
            ) as find_finals, patch.object(
                lifecycle_reconciler.dashboard_export,
                "write_dashboard_csv",
            ):
                lifecycle_reconciler.reconcile_feed(output, days_back=60)

        find_finals.assert_called_once_with(days_back=60)

    def test_matching_sec_metadata_keeps_release_grade_no_refetch_fast_path(self):
        final = _release_grade_final(ticker="LYNX")
        payload, repaired, removed = reconcile_payload(
            {"filings": [final]},
            [_final_meta(ticker="LYNX")],
            lambda _: self.fail("matching release-grade final should not be refetched"),
        )

        self.assertEqual(repaired, 0)
        self.assertEqual(removed, 0)
        self.assertEqual(payload["filings"], [final])


if __name__ == "__main__":
    unittest.main()
