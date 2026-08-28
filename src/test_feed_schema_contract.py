from __future__ import annotations

import json
import unittest
from pathlib import Path

from dashboard_export import PUBLIC_FILING_FIELDS, PUBLIC_PERSON_FIELDS, SCHEMA_VERSION
from feed_schema_contract import load_schema, validate_file, validate_payload

ROOT = Path(__file__).resolve().parents[1]


class FeedSchemaContractTests(unittest.TestCase):
    def test_checked_in_feed_matches_registered_schema(self):
        failures = validate_file(ROOT / "docs" / "data" / "filings.json")
        self.assertEqual([], failures, "\n".join(failures))

    def test_v1_schema_matches_public_export_allowlists(self):
        schema = load_schema(SCHEMA_VERSION)
        filing_fields = set(schema["$defs"]["filing"]["properties"])
        person_fields = set(schema["$defs"]["person"]["properties"])
        self.assertEqual(PUBLIC_FILING_FIELDS, filing_fields)
        self.assertEqual(PUBLIC_PERSON_FIELDS, person_fields)
        self.assertEqual(SCHEMA_VERSION, schema["properties"]["schema_version"]["const"])

    def test_unknown_top_level_field_is_rejected(self):
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "2026-08-28T00:00:00+00:00",
            "source": "SEC EDGAR",
            "filings": [],
            "unexpected": True,
        }
        self.assertTrue(validate_payload(payload))

    def test_unregistered_schema_version_is_rejected(self):
        payload = {
            "schema_version": 999,
            "generated_at": "2026-08-28T00:00:00+00:00",
            "source": "SEC EDGAR",
            "filings": [],
        }
        failures = validate_payload(payload)
        self.assertTrue(any("No public-feed schema is registered" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
