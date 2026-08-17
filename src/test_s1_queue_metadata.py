import unittest

import s1_monitor


class S1QueueMetadataTests(unittest.TestCase):
    def test_queue_record_preserves_stage_and_preliminary_price_range(self):
        filing = s1_monitor._queue_record({
            "id": "0001234567-26-000001",
            "company": "Acme Robotics, Inc.",
            "cik": "1234567",
            "accession_no": "0001234567-26-000001",
            "form": "S-1/A",
            "filed": "2026-08-17",
            "stage": "Pre-pricing",
            "price_range": "$18.00–$20.00",
            "priority": "High",
            "signals": ["Preliminary offering range disclosed at $18.00–$20.00"],
            "sec_url": "https://www.sec.gov/test",
        })

        self.assertEqual(filing["stage"], "Pre-pricing")
        self.assertEqual(filing["price_range"], "$18.00–$20.00")

    def test_queue_record_defaults_stage_for_legacy_prepricing_record(self):
        filing = s1_monitor._queue_record({
            "company": "Legacy Co",
            "cik": "7654321",
            "form": "S-1",
        })

        self.assertEqual(filing["stage"], "Pre-pricing")
        self.assertIsNone(filing["price_range"])


if __name__ == "__main__":
    unittest.main()
