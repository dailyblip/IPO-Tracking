import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import build_sec_index_intake as m


SOURCE = "https://www.sec.gov/Archives/edgar/full-index/2026/QTR1/master.idx"
COMMIT = "a" * 40
STAMP = "2026-09-26T23:11:56+00:00"
RAW = b"""Description: Master Index of EDGAR Dissemination Feed\n\nCIK|Company Name|Form Type|Date Filed|Filename\n123|Example Operating, Inc.|424B4|2026-01-08|edgar/data/123/0001493152-26-001005.txt\n456|Not Selected Corp.|S-1|2026-01-09|edgar/data/456/0001493152-26-001006.txt\n"""


class SecIndexIntakeTests(unittest.TestCase):
    def test_exact_row_build_is_deterministic_and_quarantine_only(self):
        args = (RAW, SOURCE, ["0001493152-26-001005"], STAMP, COMMIT)
        payload = m.build(*args)
        self.assertEqual(payload, m.build(*args))
        self.assertEqual(payload["records"][0]["values"]["cik"], "0000000123")
        self.assertFalse(payload["published"])
        self.assertEqual(payload["eligibility"], "unreviewed")
        self.assertEqual(payload["run_id"], m.uid("sec-index-run", COMMIT, m.sha(RAW)))
        sql = m.export_sql(payload)
        self.assertIn("ops.intake_records", sql)
        self.assertIn("on conflict (source_commit,input_sha256) do nothing", sql)
        self.assertIn("SEC index run identity conflict", sql)
        self.assertIn("Immutable SEC index batch conflict", sql)
        self.assertNotIn("research.", sql)
        self.assertNotIn("app.", sql)
        self.assertNotIn("evidence.", sql)

    def test_missing_duplicate_or_malformed_selection_fails(self):
        with self.assertRaises(ValueError):
            m.build(RAW, SOURCE, ["0001493152-26-999999"], STAMP, COMMIT)
        with self.assertRaises(ValueError):
            m.build(RAW, SOURCE, ["0001493152-26-001005"] * 2, STAMP, COMMIT)
        duplicate = RAW + RAW.splitlines()[-2] + b"\n"
        with self.assertRaises(ValueError):
            m.build(duplicate, SOURCE, ["0001493152-26-001005"], STAMP, COMMIT)
        with self.assertRaises(ValueError):
            m.build(RAW, SOURCE.replace("www.sec.gov", "example.com"), ["0001493152-26-001005"], STAMP, COMMIT)

    def test_replay_identity_changes_when_source_or_selection_changes(self):
        first = m.build(RAW, SOURCE, ["0001493152-26-001005"], STAMP, COMMIT)
        changed = m.build(RAW + b"\n", SOURCE, ["0001493152-26-001005"], STAMP, COMMIT)
        self.assertNotEqual(first["id"], changed["id"])
        self.assertNotEqual(first["payload_sha256"], changed["payload_sha256"])


if __name__ == "__main__":
    unittest.main()
