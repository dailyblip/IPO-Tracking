import json
import statistics
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "docs" / "data" / "filings.json"


class JuneOfferingRepairRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        feed = json.loads(FEED_PATH.read_text(encoding="utf-8"))
        cls.by_ticker = {
            str(row.get("ticker") or "").upper(): row
            for row in feed.get("filings", [])
        }

    def test_greenshoe_counts_do_not_survive_as_base_ipo_values(self):
        expected = {
            "QNT": (1_680_000_000, 28_000_000),
            "LFTO": (437_000_000, 19_000_000),
            "AADX": (650_000_000, 32_500_000),
        }
        for ticker, (value, primary_shares) in expected.items():
            with self.subTest(ticker=ticker):
                row = self.by_ticker[ticker]
                self.assertAlmostEqual(float(row["value"]), value, delta=1)
                self.assertAlmostEqual(
                    float(row.get("primary_offering_shares") or 0),
                    primary_shares,
                    delta=1,
                )
                self.assertFalse(float(row.get("secondary_offering_shares") or 0))
                self.assertEqual(row.get("offering_size_confidence"), "High")

    def test_known_june_pricing_values_reconcile_to_expected_month_metrics(self):
        exact_expected = {
            "FCBM": 68_750_000,
            "FRBT": 142_200_000,
            "PBLS": 670_000_000,
            "SSMR": 270_000_000,
            "SPCX": 74_999_999_925,
            "WHK": 200_200_000,
            "QNT": 1_680_000_000,
            "LFTO": 437_000_000,
            "AADX": 650_000_000,
            "KARD": 400_000_000,
        }
        values = []
        for ticker, expected_value in exact_expected.items():
            row = self.by_ticker[ticker]
            actual = float(row["value"])
            self.assertAlmostEqual(actual, expected_value, delta=1)
            values.append(actual)

        # ERock currently reconciles to a half-dollar arithmetic result; a separate
        # regression permits the authoritative SEC-rounded aggregate to replace it.
        erock = float(self.by_ticker["EROC"]["value"])
        self.assertAlmostEqual(erock, 600_000_006, delta=1)
        values.append(erock)

        self.assertEqual(int(sum(values) + 0.5), 80_118_149_931)
        self.assertEqual(statistics.median(values), 437_000_000)


if __name__ == "__main__":
    unittest.main()
