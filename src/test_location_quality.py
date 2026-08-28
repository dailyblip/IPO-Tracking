import json
import tempfile
import unittest
from pathlib import Path

import location_quality


class LocationQualityTests(unittest.TestCase):
    def test_preserves_valid_city_state_without_fallback_lookup(self):
        calls = []
        payload = {
            "filings": [
                {
                    "company": "Valid Co",
                    "cik": "1",
                    "location": "Falls Church, VA",
                    "location_source": "S-1 principal executive office",
                }
            ]
        }

        repaired, changes = location_quality.repair_payload(
            payload, resolve_location=lambda cik: calls.append(cik)
        )

        self.assertEqual(repaired["filings"][0]["location"], "Falls Church, VA")
        self.assertEqual(repaired["filings"][0]["location_source"], "S-1 principal executive office")
        self.assertEqual(changes, [])
        self.assertEqual(calls, [])

    def test_replaces_address_unit_contamination_only_with_sec_fallback(self):
        payload = {
            "filings": [
                {
                    "company": "Example Co",
                    "cik": "12345",
                    "location": "th Floor Cambridge, MA",
                    "location_source": "S-1 principal executive office",
                }
            ]
        }

        repaired, changes = location_quality.repair_payload(
            payload, resolve_location=lambda cik: "Cambridge, MA"
        )

        filing = repaired["filings"][0]
        self.assertEqual(filing["location"], "Cambridge, MA")
        self.assertEqual(filing["location_source"], "SEC submissions metadata")
        self.assertEqual(len(changes), 1)

    def test_replaces_sec_header_contamination_with_authoritative_fallback(self):
        payload = {
            "filings": [
                {
                    "company": "Example Co",
                    "cik": "12345",
                    "location": "SECURITIES AND EXCHANGE COMMISSION WASHINGTON, DC",
                    "location_source": "S-1 principal executive office",
                }
            ]
        }

        repaired, changes = location_quality.repair_payload(
            payload, resolve_location=lambda cik: "Hawthorne, CA"
        )

        filing = repaired["filings"][0]
        self.assertEqual(filing["location"], "Hawthorne, CA")
        self.assertEqual(filing["location_source"], "SEC submissions metadata")
        self.assertEqual(len(changes), 1)

    def test_replaces_street_address_contamination_with_authoritative_fallback(self):
        payload = {
            "filings": [
                {
                    "company": "Example Co",
                    "cik": "12345",
                    "location": "S Technology Court Broomfield, CO",
                    "location_source": "S-1 principal executive office",
                }
            ]
        }

        repaired, changes = location_quality.repair_payload(
            payload, resolve_location=lambda cik: "Broomfield, CO"
        )

        filing = repaired["filings"][0]
        self.assertEqual(filing["location"], "Broomfield, CO")
        self.assertEqual(filing["location_source"], "SEC submissions metadata")
        self.assertEqual(len(changes), 1)

    def test_replaces_flattened_street_suffix_prefix_when_sec_location_differs(self):
        payload = {
            "filings": [
                {
                    "company": "Reformation Inc.",
                    "cik": "1787117",
                    "location": "St. Vernon, CA",
                    "location_source": "S-1 principal executive office",
                }
            ]
        }

        repaired, changes = location_quality.repair_payload(
            payload, resolve_location=lambda cik: "Vernon, CA"
        )

        filing = repaired["filings"][0]
        self.assertEqual(filing["location"], "Vernon, CA")
        self.assertEqual(filing["location_source"], "SEC submissions metadata")
        self.assertEqual(changes, [("Reformation Inc.", "St. Vernon, CA", "Vernon, CA")])

    def test_preserves_legitimate_st_city_after_authoritative_cross_check(self):
        payload = {
            "filings": [
                {
                    "company": "St Louis Example",
                    "cik": "98765",
                    "location": "St. Louis, MO",
                    "location_source": "S-1 principal executive office",
                }
            ]
        }

        repaired, changes = location_quality.repair_payload(
            payload, resolve_location=lambda cik: "St. Louis, MO"
        )

        filing = repaired["filings"][0]
        self.assertEqual(filing["location"], "St. Louis, MO")
        self.assertEqual(filing["location_source"], "S-1 principal executive office")
        self.assertEqual(changes, [])

    def test_preserves_ambiguous_st_city_when_authoritative_lookup_is_unavailable(self):
        payload = {
            "filings": [
                {
                    "company": "St Louis Example",
                    "cik": "98765",
                    "location": "St. Louis, MO",
                    "location_source": "S-1 principal executive office",
                }
            ]
        }

        repaired, changes = location_quality.repair_payload(
            payload, resolve_location=lambda cik: None
        )

        filing = repaired["filings"][0]
        self.assertEqual(filing["location"], "St. Louis, MO")
        self.assertEqual(changes, [])

    def test_clears_malformed_location_when_authoritative_fallback_is_unavailable(self):
        payload = {
            "filings": [
                {
                    "company": "Example Co",
                    "cik": "12345",
                    "location": "Suite 400 Boston, MA",
                    "location_source": "424B4 principal executive office",
                }
            ]
        }

        repaired, changes = location_quality.repair_payload(
            payload, resolve_location=lambda cik: None
        )

        filing = repaired["filings"][0]
        self.assertNotIn("location", filing)
        self.assertNotIn("location_source", filing)
        self.assertEqual(len(changes), 1)

    def test_rejects_non_city_state_shapes_and_numeric_city_fragments(self):
        self.assertIsNone(location_quality.normalize_location("100 Main St Boston, MA"))
        self.assertIsNone(location_quality.normalize_location("Boston, MA 02110"))
        self.assertIsNone(location_quality.normalize_location("Boston, Massachusetts"))
        self.assertEqual(location_quality.normalize_location("Boston, ma"), "Boston, MA")
        self.assertEqual(location_quality.normalize_location("St. Louis, MO"), "St. Louis, MO")

    def test_repair_feed_persists_json_without_inventing_location(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "filings.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "filings": [
                            {
                                "company": "Example Co",
                                "cik": "",
                                "location": "12th Floor Cambridge, MA",
                                "location_source": "S-1 principal executive office",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            changed = location_quality.repair_feed(path)
            result = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(changed, 1)
            self.assertNotIn("location", result["filings"][0])
            self.assertNotIn("location_source", result["filings"][0])


if __name__ == "__main__":
    unittest.main()
