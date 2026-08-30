import json
import unittest
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILINGS_PATH = ROOT / "docs" / "data" / "filings.json"


class TestIssuerLifecycleUniqueness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(FILINGS_PATH.read_text(encoding="utf-8"))
        cls.rows = payload.get("filings", [])

    def test_public_feed_has_single_active_lifecycle_record_per_cik(self):
        """A priced promotion must not leave a stale pre-pricing row behind."""
        by_cik = defaultdict(list)
        for row in self.rows:
            cik = str(row.get("cik") or "").strip()
            if cik:
                by_cik[cik].append(row)

        duplicates = []
        for cik, rows in by_cik.items():
            if len(rows) <= 1:
                continue
            duplicates.append(
                {
                    "cik": cik,
                    "companies": sorted({str(row.get("company") or "").strip() for row in rows}),
                    "stages": sorted({str(row.get("stage") or "").strip() for row in rows}),
                    "accessions": sorted({str(row.get("accession_no") or "").strip() for row in rows}),
                }
            )

        self.assertFalse(
            duplicates,
            "Public feed contains multiple active lifecycle records for one issuer: "
            + json.dumps(duplicates[:20], sort_keys=True),
        )

    def test_public_feed_accessions_are_unique(self):
        """The same SEC filing must not be published as duplicate issuer records."""
        by_accession = defaultdict(list)
        for row in self.rows:
            accession = str(row.get("accession_no") or "").strip()
            if accession:
                by_accession[accession].append(row)

        duplicates = {
            accession: [str(row.get("company") or "").strip() for row in rows]
            for accession, rows in by_accession.items()
            if len(rows) > 1
        }
        self.assertFalse(
            duplicates,
            "Public feed contains duplicate SEC accession records: "
            + json.dumps(dict(list(duplicates.items())[:20]), sort_keys=True),
        )

    def test_public_feed_tickers_do_not_map_to_multiple_ciks(self):
        """A live feed ticker must not resolve to more than one SEC issuer identity."""
        by_ticker = defaultdict(list)
        for row in self.rows:
            ticker = str(row.get("ticker") or "").strip().upper()
            if ticker:
                by_ticker[ticker].append(row)

        collisions = []
        for ticker, rows in by_ticker.items():
            ciks = sorted(
                {
                    str(row.get("cik") or "").strip()
                    for row in rows
                    if str(row.get("cik") or "").strip()
                }
            )
            if len(ciks) <= 1:
                continue
            collisions.append(
                {
                    "ticker": ticker,
                    "ciks": ciks,
                    "companies": sorted({str(row.get("company") or "").strip() for row in rows}),
                }
            )

        self.assertFalse(
            collisions,
            "Public feed contains ticker-to-issuer collisions: "
            + json.dumps(collisions[:20], sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
