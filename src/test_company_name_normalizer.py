import csv
import json
import tempfile
import unittest
from pathlib import Path

from company_name_normalizer import normalize_company_name, normalize_csv, normalize_json


class CompanyNameNormalizerTests(unittest.TestCase):
    def test_normalizes_all_caps_without_touching_correct_mixed_case(self):
        self.assertEqual(
            normalize_company_name("ACME BIOTHERAPEUTICS, INC."),
            "Acme Biotherapeutics, Inc.",
        )
        self.assertEqual(
            normalize_company_name("McKesson Corporation"),
            "McKesson Corporation",
        )

    def test_preserves_known_acronyms_brands_and_roman_numerals(self):
        self.assertEqual(normalize_company_name("FIGURE AI, INC."), "Figure AI, Inc.")
        self.assertEqual(normalize_company_name("SPACEX"), "SpaceX")
        self.assertEqual(
            normalize_company_name("ACME HOLDINGS III, LLC"),
            "Acme Holdings III, LLC",
        )

    def test_json_and_csv_normalization_remain_in_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "filings.json"
            csv_path = json_path.with_suffix(".csv")
            json_path.write_text(
                json.dumps(
                    {
                        "filings": [
                            {"company": "FIGURE AI, INC.", "ticker": "FIG"},
                            {"company": "McKesson Corporation", "ticker": "MCK"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["company", "ticker"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"company": "FIGURE AI, INC.", "ticker": "FIG"},
                        {"company": "McKesson Corporation", "ticker": "MCK"},
                    ]
                )

            self.assertTrue(normalize_json(json_path))
            self.assertTrue(normalize_csv(csv_path))

            json_names = [
                row["company"]
                for row in json.loads(json_path.read_text(encoding="utf-8"))["filings"]
            ]
            with csv_path.open(newline="", encoding="utf-8") as handle:
                csv_names = [row["company"] for row in csv.DictReader(handle)]
            self.assertEqual(json_names, ["Figure AI, Inc.", "McKesson Corporation"])
            self.assertEqual(csv_names, json_names)


if __name__ == "__main__":
    unittest.main()
