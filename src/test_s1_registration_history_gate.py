import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import s1_registration_history_gate as gate


class _Soup:
    def __init__(self, text):
        self.text = text

    def get_text(self, *_args, **_kwargs):
        return self.text


class RegistrationHistoryGateTests(unittest.TestCase):
    def test_only_same_file_number_predecessors_are_returned(self):
        payload = {
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0001493152-26-040434",
                        "0001493152-26-035201",
                        "0001493152-26-030000",
                    ],
                    "form": ["S-1/A", "S-1/A", "S-1"],
                    "fileNumber": ["333-296437", "333-296437", "333-999999"],
                    "filingDate": ["2026-08-27", "2026-07-29", "2026-07-01"],
                    "primaryDocument": ["current.htm", "prior.htm", "other.htm"],
                }
            }
        }
        with patch.object(gate.edgar_client, "_request_json", return_value=payload), patch.object(
            gate.edgar_client, "_get_headers", return_value={"User-Agent": "test"}
        ):
            rows = gate._same_registration_predecessors(
                "2076148", "0001493152-26-040434"
            )

        self.assertEqual(1, len(rows))
        self.assertEqual("0001493152-26-035201", rows[0]["accession_no"])
        self.assertEqual("333-296437", rows[0]["file_number"])

    def test_prior_same_registration_resale_excludes_ambiguous_amendment(self):
        record = {
            "company": "FullPAC, Inc.",
            "cik": "0002076148",
            "accession_no": "0001493152-26-040434",
            "form": "S-1/A",
            "stage": "Pre-pricing",
            "primary_offering_shares": None,
            "offering_size_source": None,
            "offering_size_confidence": None,
        }
        predecessors = [{
            "accession_no": "0001493152-26-035201",
            "primary_document": "forms-1a.htm",
            "file_number": "333-296437",
            "filing_date": "2026-07-29",
            "form": "S-1/A",
        }]
        prior_text = (
            "This prospectus relates to the offer and sale, from time to time, "
            "by the selling securityholders named in this prospectus."
        )
        with patch.object(gate, "_same_registration_predecessors", return_value=predecessors), patch.object(
            gate.filing_parser, "fetch_document", return_value=_Soup(prior_text)
        ):
            self.assertTrue(gate.amendment_inherits_resale_exclusion(record))

    def test_authoritative_current_primary_offering_overrides_history(self):
        record = {
            "company": "Real IPO, Inc.",
            "cik": "0002000001",
            "accession_no": "0000000000-26-000002",
            "form": "S-1/A",
            "stage": "Pre-pricing",
            "primary_offering_shares": 10_000_000,
            "offering_size_source": "primary offering; SEC cover share count",
            "offering_size_confidence": "High",
        }
        with patch.object(gate, "_same_registration_predecessors") as history:
            self.assertFalse(gate.amendment_inherits_resale_exclusion(record))
            history.assert_not_called()

    def test_history_fetch_failure_does_not_invent_exclusion(self):
        record = {
            "company": "Ambiguous Issuer",
            "cik": "0002000002",
            "accession_no": "0000000000-26-000003",
            "form": "S-1/A",
            "stage": "Pre-pricing",
        }
        with patch.object(
            gate, "_same_registration_predecessors", side_effect=RuntimeError("SEC unavailable")
        ):
            self.assertFalse(gate.amendment_inherits_resale_exclusion(record))

    def test_apply_gate_removes_only_prepricing_rows_for_excluded_cik(self):
        watch = {
            "filings": [
                {"company": "FullPAC, Inc.", "cik": "0002076148", "form": "S-1/A", "stage": "Pre-pricing"},
                {"company": "Little West Holdings Inc.", "cik": "0002065821", "form": "S-1/A", "stage": "Pre-pricing", "ipo_size": 18_750_000},
            ]
        }
        queue = {
            "filings": [
                {"id": "s1:0002076148", "company": "FullPAC, Inc.", "cik": "0002076148", "form": "S-1/A", "stage": "Pre-pricing"},
                {"id": "priced:0002076148", "company": "Future Priced Record", "cik": "0002076148", "form": "424B4", "stage": "Priced"},
                {"id": "s1:0002065821", "company": "Little West Holdings Inc.", "cik": "0002065821", "form": "S-1/A", "stage": "Pre-pricing", "value": 18_750_000},
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            watch_path = Path(temp_dir) / "s1_watch.json"
            queue_path = Path(temp_dir) / "filings.json"
            watch_path.write_text(json.dumps(watch), encoding="utf-8")
            queue_path.write_text(json.dumps(queue), encoding="utf-8")

            with patch.object(
                gate,
                "amendment_inherits_resale_exclusion",
                side_effect=lambda row: row.get("company") == "FullPAC, Inc.",
            ), patch.object(gate, "write_dashboard_csv"):
                excluded = gate.apply_gate(watch_path, queue_path)

            filtered_watch = json.loads(watch_path.read_text(encoding="utf-8"))["filings"]
            filtered_queue = json.loads(queue_path.read_text(encoding="utf-8"))["filings"]

        self.assertEqual({"0002076148"}, excluded)
        self.assertEqual(["Little West Holdings Inc."], [row["company"] for row in filtered_watch])
        self.assertEqual(
            ["Future Priced Record", "Little West Holdings Inc."],
            [row["company"] for row in filtered_queue],
        )

    def test_apply_gate_checks_queue_only_prepricing_candidate(self):
        watch = {"filings": []}
        queue = {
            "filings": [
                {
                    "id": "s1:0002000100",
                    "company": "Already Public Co",
                    "cik": "0002000100",
                    "accession_no": "0000000000-26-000100",
                    "form": "S-1",
                    "stage": "Pre-pricing",
                    "filed": "2026-09-01",
                },
                {
                    "id": "priced:0002000100",
                    "company": "Already Public Co",
                    "cik": "0002000100",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-08-01",
                },
                {
                    "id": "s1:0002000200",
                    "company": "First-Time IPO Co",
                    "cik": "0002000200",
                    "accession_no": "0000000000-26-000200",
                    "form": "S-1/A",
                    "stage": "Pre-pricing",
                    "filed": "2026-09-01",
                },
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            watch_path = Path(temp_dir) / "s1_watch.json"
            queue_path = Path(temp_dir) / "filings.json"
            watch_path.write_text(json.dumps(watch), encoding="utf-8")
            queue_path.write_text(json.dumps(queue), encoding="utf-8")

            with patch.object(
                gate,
                "already_reporting_before_registration",
                side_effect=lambda row: row.get("company") == "Already Public Co",
            ), patch.object(
                gate, "amendment_inherits_resale_exclusion", return_value=False
            ), patch.object(gate, "write_dashboard_csv"):
                excluded = gate.apply_gate(watch_path, queue_path)

            filtered_queue = json.loads(queue_path.read_text(encoding="utf-8"))["filings"]

        self.assertEqual({"0002000100"}, excluded)
        self.assertEqual(
            ["priced:0002000100", "s1:0002000200"],
            [row["id"] for row in filtered_queue],
        )


if __name__ == "__main__":
    unittest.main()
