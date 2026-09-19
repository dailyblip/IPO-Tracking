import json
import tempfile
import unittest
from pathlib import Path

from offering_value_label_normalizer import normalize_file, normalize_payload


class OfferingValueLabelNormalizerTests(unittest.TestCase):
    def test_writer_labels_converge_without_changing_raw_offering_values(self):
        payload = {
            "filings": [
                {"company": "Large Co", "value": 825_000_000, "value_label": "$825,000,000"},
                {"company": "Fractional Co", "value": 18_750_000, "value_label": "$18.75M"},
                {"company": "Small Co", "value": 750_000, "value_label": "$750,000"},
                {"company": "Unknown Co", "value": None, "value_label": "$100M"},
            ]
        }

        normalized, changed = normalize_payload(payload)

        self.assertEqual(changed, 4)
        self.assertEqual(
            [filing["value_label"] for filing in normalized["filings"]],
            ["$825M", "$19M", "$750K", "—"],
        )
        self.assertEqual(
            [filing["value"] for filing in normalized["filings"]],
            [825_000_000, 18_750_000, 750_000, None],
        )

    def test_normalization_is_idempotent(self):
        payload = {
            "filings": [
                {"company": "Canonical Co", "value": 33_250_000, "value_label": "$33M"},
                {"company": "Unknown Co", "value": None, "value_label": "—"},
            ]
        }

        normalized, changed = normalize_payload(payload)

        self.assertEqual(changed, 0)
        self.assertEqual(normalized, payload)

    def test_file_normalization_preserves_unknown_or_invalid_raw_size(self):
        payload = {
            "schema_version": 1,
            "filings": [
                {"company": "Unknown Co", "value": "unknown", "value_label": "$100M"},
                {"company": "Negative Co", "value": -5, "value_label": "$5M"},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filings.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            changed = normalize_file(path)
            persisted = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(changed, 2)
        self.assertEqual(persisted["filings"][0]["value"], "unknown")
        self.assertEqual(persisted["filings"][1]["value"], -5)
        self.assertEqual(persisted["filings"][0]["value_label"], "—")
        self.assertEqual(persisted["filings"][1]["value_label"], "—")

    def test_file_normalization_also_enforces_public_currency_precision(self):
        payload = {
            "schema_version": 1,
            "filings": [{
                "id": "priced-writer-output",
                "company": "Example Issuer",
                "ticker": "EXM",
                "form": "424B4",
                "stage": "Priced",
                "filed": "2026-08-27",
                "pricing_date": "2026-08-26",
                "value": 18_750_000,
                "value_label": "$19M",
                "offering_price": 17.5,
                "current_price": 13.6917,
                "price_updated": "2026-08-27T20:05:29+00:00",
                "people": [{
                    "name": "Example Holder",
                    "shares": 1_260_126,
                    "cash_value": 17_251_124.939999998,
                    "ipo_value": 22_052_205.000000004,
                }],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filings.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            changed = normalize_file(path)
            persisted = json.loads(path.read_text(encoding="utf-8"))["filings"][0]

        self.assertEqual(changed, 0)
        self.assertEqual(persisted["current_price"], 13.6917)
        self.assertEqual(persisted["people"][0]["cash_value"], 17_251_124.94)
        self.assertEqual(persisted["people"][0]["ipo_value"], 22_052_205.0)


if __name__ == "__main__":
    unittest.main()
