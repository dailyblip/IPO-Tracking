import unittest

from s1_preliminary_price_gate import (
    _extract_fee_table_equity_terms,
    review_watch_payload,
)


LA_BEAUTE_COVER = (
    "PRELIMINARY PROSPECTUS SUBJECT TO COMPLETION. "
    "We are offering 10,000,000 ordinary shares of the Company pursuant to this Offering. "
    "This is the initial public offering of ordinary shares of La Beaute Inc. "
    "The offering price per share of our ordinary shares in this offering is to be fixed "
    "at $5.00 per share."
)

LA_BEAUTE_FEE_HTML = """
<table>
  <tr>
    <th></th><th></th><th>Security Type</th><th>Security Class Title</th>
    <th>Fee Calculation or Carry Forward Rule</th><th>Amount Registered</th>
    <th>Proposed Maximum Offering Price Per Unit</th>
    <th>Maximum Aggregate Offering Price</th><th>Fee Rate</th>
    <th>Amount of Registration Fee</th>
  </tr>
  <tr>
    <td>Fees to be Paid</td><td></td><td>Equity</td><td>Ordinary</td>
    <td>457(a)</td><td>100,000</td><td>$ 5.00</td><td>$ 500,000.00</td>
    <td>0.0001381</td><td>$ 69.05</td>
  </tr>
</table>
"""


def _row(source="SEC preliminary prospectus cover: primary offering; issuer-only; verified point price"):
    return {
        "id": "s1:0002151905",
        "company": "La Beaute Inc.",
        "cik": "0002151905",
        "accession_no": "0002151905-26-000001",
        "form": "S-1",
        "stage": "Pre-pricing",
        "priority": "High",
        "price_range": None,
        "filing_price": "$5.00",
        "value": 50_000_000,
        "value_label": "$50,000,000",
        "offering_size_source": source,
        "offering_size_confidence": "High",
        "primary_offering_shares": 10_000_000,
        "secondary_offering_shares": None,
        "signals": [
            "Fixed offering price disclosed at $5.00 per share",
            "IPO size disclosed or derived at approximately $50,000,000",
        ],
        "sec_url": "https://www.sec.gov/test",
    }


class FeeTableConflictTests(unittest.TestCase):
    def test_extracts_single_equity_fee_row(self):
        self.assertEqual(
            _extract_fee_table_equity_terms(LA_BEAUTE_FEE_HTML),
            {"shares": 100_000, "price": 5.0, "aggregate": 500_000.0},
        )

    def test_material_same_price_fee_conflict_clears_size_but_preserves_filing_price(self):
        terms = _extract_fee_table_equity_terms(LA_BEAUTE_FEE_HTML)
        updated, invalid, checked = review_watch_payload(
            {"filings": [_row()]},
            text_loader=lambda _: LA_BEAUTE_COVER,
            fee_terms_loader=lambda _: terms,
        )
        result = updated["filings"][0]
        self.assertEqual(invalid, {})
        self.assertEqual(checked, 0)
        self.assertEqual(result["filing_price"], "$5.00")
        self.assertIsNone(result["value"])
        self.assertEqual(result["value_label"], "—")
        self.assertIsNone(result["primary_offering_shares"])
        self.assertIsNone(result["offering_size_source"])
        self.assertIsNone(result["offering_size_confidence"])
        self.assertFalse(any("IPO size disclosed" in signal for signal in result["signals"]))

    def test_normal_registration_headroom_does_not_clear_size(self):
        fee_terms = {"shares": 11_500_000, "price": 5.0, "aggregate": 57_500_000.0}
        updated, invalid, checked = review_watch_payload(
            {"filings": [_row()]},
            text_loader=lambda _: LA_BEAUTE_COVER,
            fee_terms_loader=lambda _: fee_terms,
        )
        result = updated["filings"][0]
        self.assertEqual(invalid, {})
        self.assertEqual(checked, 1)
        self.assertEqual(result["value"], 50_000_000)
        self.assertEqual(result["primary_offering_shares"], 10_000_000)

    def test_midpoint_scenario_is_not_reinterpreted_by_fee_table(self):
        row = _row(
            source="SEC preliminary prospectus: explicit midpoint offering-share scenario; verified point price"
        )
        row["company"] = "Hometown Financial Group, Inc."
        row["filing_price"] = "$10.00"
        row["value"] = 600_000_000
        row["value_label"] = "$600,000,000"
        row["primary_offering_shares"] = None
        updated, _, _ = review_watch_payload(
            {"filings": [row]},
            text_loader=lambda _: (
                "This is the initial public offering. The purchase price of each share of common stock "
                "to be sold in the stock offering is $10.00. The offering range applies to the number of shares."
            ),
            fee_terms_loader=lambda _: (_ for _ in ()).throw(AssertionError("fee loader should not run")),
        )
        self.assertEqual(updated["filings"][0]["value"], 600_000_000)

    def test_different_fee_unit_price_is_not_treated_as_same_term_conflict(self):
        fee_terms = {"shares": 100_000, "price": 4.0, "aggregate": 400_000.0}
        updated, invalid, checked = review_watch_payload(
            {"filings": [_row()]},
            text_loader=lambda _: LA_BEAUTE_COVER,
            fee_terms_loader=lambda _: fee_terms,
        )
        self.assertEqual(invalid, {})
        self.assertEqual(checked, 1)
        self.assertEqual(updated["filings"][0]["value"], 50_000_000)


if __name__ == "__main__":
    unittest.main()
