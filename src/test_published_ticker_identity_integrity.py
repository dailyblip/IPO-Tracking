import json
import re
import unittest
from collections import defaultdict
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
MONITOR_START = "2026-06-01"


def _canonical_cik(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return str(int(digits)) if digits else ""


class PublishedTickerIdentityIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else payload

    def test_june_present_ticker_and_issuer_identity_is_one_to_one(self):
        """Block stale ticker/entity collisions in the published Research Monitor feed.

        A ticker may be blank before the issuer discloses one, but once both ticker and
        issuer CIK are published, the June-present canonical feed must not map one
        ticker to multiple SEC issuers or one SEC issuer to multiple live tickers.
        Lifecycle reconciliation should promote ticker changes into the canonical row
        rather than leave conflicting issuer/ticker records visible side by side.
        """
        ciks_by_ticker = defaultdict(set)
        tickers_by_cik = defaultdict(set)
        labels_by_pair = defaultdict(set)

        for filing in self.filings:
            filed = str(filing.get("filed") or "").strip()
            if filed and filed < MONITOR_START:
                continue

            ticker = str(filing.get("ticker") or "").strip().upper()
            cik = _canonical_cik(filing.get("cik"))
            if not ticker or not cik:
                continue

            label = str(filing.get("company") or filing.get("id") or "unknown filing").strip()
            ciks_by_ticker[ticker].add(cik)
            tickers_by_cik[cik].add(ticker)
            labels_by_pair[(ticker, cik)].add(label)

        failures = []
        for ticker, ciks in sorted(ciks_by_ticker.items()):
            if len(ciks) > 1:
                details = []
                for cik in sorted(ciks):
                    companies = ", ".join(sorted(labels_by_pair[(ticker, cik)]))
                    details.append(f"CIK {cik} ({companies})")
                failures.append(
                    f"ticker {ticker} maps to multiple issuers: " + "; ".join(details)
                )

        for cik, tickers in sorted(tickers_by_cik.items()):
            if len(tickers) > 1:
                details = []
                for ticker in sorted(tickers):
                    companies = ", ".join(sorted(labels_by_pair[(ticker, cik)]))
                    details.append(f"{ticker} ({companies})")
                failures.append(
                    f"CIK {cik} maps to multiple published tickers: " + "; ".join(details)
                )

        self.assertGreater(
            len(ciks_by_ticker),
            0,
            "No June-present ticker/CIK pairs were available to validate",
        )
        self.assertEqual(
            failures,
            [],
            "Published ticker/entity identity collisions: " + "; ".join(failures[:10]),
        )


if __name__ == "__main__":
    unittest.main()
