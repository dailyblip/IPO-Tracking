import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import historical_backfill_policy


class HistoricalBackfillPolicyTests(unittest.TestCase):
    def _apply(self, rows):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "filings.json"
            path.write_text(
                json.dumps({"filings": rows}, indent=2) + "\n",
                encoding="utf-8",
            )
            with patch.object(historical_backfill_policy, "write_dashboard_csv"):
                payload, removed = historical_backfill_policy.apply_historical_minimum(
                    path,
                    start=date(2026, 4, 1),
                    end=date(2026, 4, 30),
                )
            return payload["filings"], removed

    def test_target_month_uses_historical_100m_publication_threshold(self):
        kept, removed = self._apply(
            [
                {"company": "Below", "filed": "2026-04-10", "value": 99_999_999},
                {"company": "Unknown", "filed": "2026-04-11", "value": None},
                {"company": "At Threshold", "filed": "2026-04-12", "value": 100_000_000},
                {"company": "Above", "filed": "2026-04-13", "value": 250_000_000},
            ]
        )
        self.assertEqual(
            [row["company"] for row in kept],
            ["At Threshold", "Above"],
        )
        self.assertEqual(removed, ["Below", "Unknown"])

    def test_rows_outside_replayed_month_are_not_retroactively_size_filtered(self):
        kept, removed = self._apply(
            [
                {"company": "March Small", "filed": "2026-03-31", "value": 10_000_000},
                {"company": "May Small", "filed": "2026-05-01", "value": 20_000_000},
            ]
        )
        self.assertEqual(
            [row["company"] for row in kept],
            ["March Small", "May Small"],
        )
        self.assertEqual(removed, [])

    def test_month_scope_uses_canonical_filed_date_not_initial_filing_date(self):
        kept, removed = self._apply(
            [
                {
                    "company": "Filed In May",
                    "filed": "2026-05-02",
                    "filing_date": "2026-04-15",
                    "value": 25_000_000,
                },
                {
                    "company": "Filed In April",
                    "filed": "2026-04-20",
                    "filing_date": "2026-03-01",
                    "value": 25_000_000,
                },
            ]
        )
        self.assertEqual([row["company"] for row in kept], ["Filed In May"])
        self.assertEqual(removed, ["Filed In April"])


if __name__ == "__main__":
    unittest.main()
