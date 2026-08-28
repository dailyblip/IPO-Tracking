import json
import unittest
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILINGS_PATH = ROOT / "docs" / "data" / "filings.json"

# These fields describe the IPO/filing itself, not an individual beneficial owner.
# The public feed can contain multiple rows for one filing (one per holder), but
# issuer-level facts must not drift between those rows during enrichment or
# lifecycle reconciliation.
ISSUER_LEVEL_FIELDS = (
    "company",
    "cik",
    "ticker",
    "filed",
    "form",
    "accession",
    "stage",
    "location",
    "offering_value",
    "offering_size_usd",
    "size_source",
    "size_source_url",
    "size_conflict",
    "filing_price",
    "current_price",
    "price_date",
    "price_updated",
    "pricing_date",
    "offering_price",
    "offering_price_source",
    "offer_status",
    "lockup_status",
    "lockup_end_date",
    "lockup_waiver",
    "lockup_source",
)


def _stable(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if value is None:
        return ""
    return str(value).strip()


class TestIssuerRowConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(FILINGS_PATH.read_text(encoding="utf-8"))

    def test_duplicate_holder_rows_preserve_identical_issuer_facts(self):
        groups = defaultdict(list)
        for row in self.rows:
            cik = str(row.get("cik") or "").strip()
            accession = str(row.get("accession") or "").strip()
            filing_url = str(row.get("filing_url") or "").strip()
            if cik and accession:
                key = (cik, accession)
            elif filing_url:
                key = ("url", filing_url)
            else:
                continue
            groups[key].append(row)

        conflicts = []
        for key, rows in groups.items():
            if len(rows) < 2:
                continue
            for field in ISSUER_LEVEL_FIELDS:
                values = {_stable(row.get(field)) for row in rows}
                if len(values) > 1:
                    sample = sorted(values)[:4]
                    conflicts.append(f"{key} {field}: {sample}")

        self.assertFalse(
            conflicts,
            "Issuer-level facts drifted across beneficial-owner rows for the same filing:\n"
            + "\n".join(conflicts[:30]),
        )


if __name__ == "__main__":
    unittest.main()
