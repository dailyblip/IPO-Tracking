import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "Research Monitor test@example.com")

import s1_preliminary_price_gate as gate


LA_BEAUTE_COVER = (
    "PRELIMINARY PROSPECTUS SUBJECT TO COMPLETION. "
    "We are offering 10,000,000 ordinary shares of the Company pursuant to this Offering. "
    "This is the initial public offering of ordinary shares of La Beaute Inc. "
    "The offering price per share of our ordinary shares in this offering is to be fixed "
    "at $5.00 per share. Prior to this offering, there has been no public market for our "
    "ordinary shares."
)


def _row(*, queue=False):
    row = {
        "id": "s1:0002151905" if queue else "0002151905-26-000001",
        "company": "La Beaute Inc.",
        "cik": "0002151905",
        "accession_no": "0002151905-26-000001",
        "form": "S-1",
        "stage": "Pre-pricing",
        "priority": "High",
        "price_range": None,
        "filing_price": "$5.00",
        "offering_size_source": None,
        "offering_size_confidence": None,
        "primary_offering_shares": None,
        "secondary_offering_shares": None,
        "signals": ["Fixed offering price disclosed at $5.00 per share"],
        "sec_url": "https://www.sec.gov/test",
    }
    if queue:
        row["value"] = None
        row["value_label"] = "—"
    else:
        row["ipo_size"] = None
    return row


class VerifiedFixedPriceSizeRecoveryTests(unittest.TestCase):
    def test_existing_verified_point_price_recovers_missing_size(self):
        updated, invalid, checked = gate.review_watch_payload(
            {"filings": [_row(queue=True)]},
            text_loader=lambda _: LA_BEAUTE_COVER,
        )
        result = updated["filings"][0]

        self.assertEqual(checked, 1)
        self.assertEqual(invalid, {})
        self.assertEqual(result["filing_price"], "$5.00")
        self.assertEqual(result["primary_offering_shares"], 10_000_000)
        self.assertEqual(result["value"], 50_000_000)
        self.assertEqual(result["value_label"], "$50,000,000")
        self.assertEqual(result["offering_size_confidence"], "High")
        self.assertIn("issuer-only", result["offering_size_source"])

    def test_exact_watch_queue_duplicate_reuses_sec_text_and_fills_both_shapes(self):
        calls = []

        def loader(filing):
            calls.append(filing["accession_no"])
            return LA_BEAUTE_COVER

        with tempfile.TemporaryDirectory() as temp_dir:
            watch_path = Path(temp_dir) / "s1_watch.json"
            queue_path = Path(temp_dir) / "filings.json"
            watch_path.write_text(json.dumps({"filings": [_row(queue=False)]}), encoding="utf-8")
            queue_path.write_text(json.dumps({"filings": [_row(queue=True)]}), encoding="utf-8")

            watch, queue, invalid, checked = gate.enforce_preliminary_fixed_prices(
                watch_path,
                queue_path,
                text_loader=loader,
            )

        self.assertEqual(invalid, {})
        self.assertEqual(calls, ["0002151905-26-000001"])
        self.assertEqual(checked, 2)
        self.assertEqual(watch["filings"][0]["ipo_size"], 50_000_000)
        self.assertEqual(queue["filings"][0]["value"], 50_000_000)
        self.assertEqual(queue["filings"][0]["value_label"], "$50,000,000")

    def test_selling_stockholders_still_block_issuer_only_size_inference(self):
        mixed_cover = LA_BEAUTE_COVER + " Selling stockholders are also offering 1,000,000 shares."
        updated, invalid, checked = gate.review_watch_payload(
            {"filings": [_row(queue=True)]},
            text_loader=lambda _: mixed_cover,
        )
        result = updated["filings"][0]

        self.assertEqual(checked, 1)
        self.assertEqual(invalid, {})
        self.assertEqual(result["filing_price"], "$5.00")
        self.assertIsNone(result["primary_offering_shares"])
        self.assertIsNone(result["value"])
        self.assertIsNone(result["secondary_offering_shares"])


if __name__ == "__main__":
    unittest.main()