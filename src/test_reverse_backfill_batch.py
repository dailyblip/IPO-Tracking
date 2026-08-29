from __future__ import annotations

import unittest
from datetime import date

from reverse_backfill_batch import oldest_priced_date, select_candidates


class ReverseBackfillBatchTests(unittest.TestCase):
    def test_oldest_priced_date_ignores_prepricing_rows(self):
        payload = {
            "filings": [
                {"form": "S-1", "stage": "Pre-pricing", "filed": "2026-05-01"},
                {"form": "424B4", "stage": "Priced", "pricing_date": "2026-06-05"},
                {"form": "424B4", "stage": "Priced", "filed": "2026-06-04"},
            ]
        }
        self.assertEqual(date(2026, 6, 4), oldest_priced_date(payload))

    def test_select_candidates_is_strictly_older_new_and_reverse_chronological(self):
        filings = [
            {"accession_no": "old-1", "filing_date": "2026-06-03"},
            {"accession_no": "existing", "filing_date": "2026-06-02"},
            {"accession_no": "cutoff", "filing_date": "2026-06-04"},
            {"accession_no": "old-2", "filing_date": "2026-06-01"},
        ]
        selected = select_candidates(filings, date(2026, 6, 4), {"existing"})
        self.assertEqual(["old-1", "old-2"], [row["accession_no"] for row in selected])


if __name__ == "__main__":
    unittest.main()
