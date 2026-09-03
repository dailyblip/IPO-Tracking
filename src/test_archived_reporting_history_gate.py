import unittest

import archived_reporting_history_gate as gate


class ArchivedReportingHistoryGateTests(unittest.TestCase):
    def test_prior_report_in_sec_archive_is_detected(self):
        submissions = {
            "filings": {
                "recent": {"form": ["S-1"], "filingDate": ["2026-09-01"]},
                "files": [
                    {
                        "name": "CIK0000000001-submissions-001.json",
                        "filingFrom": "2020-01-01",
                        "filingTo": "2025-12-31",
                    }
                ],
            }
        }
        archived = {
            "form": ["8-K", "S-1"],
            "filingDate": ["2025-04-10", "2025-05-01"],
        }
        self.assertTrue(
            gate.has_prior_reporting_history(
                submissions,
                "2026-09-01",
                archive_loader=lambda _name: archived,
            )
        )

    def test_same_day_archived_report_does_not_guess_event_order(self):
        submissions = {
            "filings": {
                "recent": {"form": ["424B4"], "filingDate": ["2026-09-01"]},
                "files": [{"name": "CIK0000000001-submissions-001.json"}],
            }
        }
        archived = {"form": ["8-K"], "filingDate": ["2026-09-01"]}
        self.assertFalse(
            gate.has_prior_reporting_history(
                submissions,
                "2026-09-01",
                archive_loader=lambda _name: archived,
            )
        )

    def test_recent_prior_report_short_circuits_archive_fetch(self):
        submissions = {
            "filings": {
                "recent": {"form": ["10-Q"], "filingDate": ["2026-05-01"]},
                "files": [{"name": "CIK0000000001-submissions-001.json"}],
            }
        }
        self.assertTrue(
            gate.has_prior_reporting_history(
                submissions,
                "2026-09-01",
                archive_loader=lambda _name: self.fail("archive should not be fetched"),
            )
        )

    def test_archive_wholly_after_candidate_is_not_fetched(self):
        submissions = {
            "filings": {
                "recent": {"form": ["S-1"], "filingDate": ["2026-09-01"]},
                "files": [
                    {
                        "name": "CIK0000000001-submissions-001.json",
                        "filingFrom": "2026-09-01",
                        "filingTo": "2026-12-31",
                    }
                ],
            }
        }
        self.assertFalse(
            gate.has_prior_reporting_history(
                submissions,
                "2026-09-01",
                archive_loader=lambda _name: self.fail("irrelevant archive should not be fetched"),
            )
        )

    def test_payload_removes_archived_s1_and_424b4_followon(self):
        watch = {
            "filings": [
                {
                    "id": "s1-old-public",
                    "company": "Old Public S1 Co",
                    "cik": "1",
                    "form": "S-1",
                    "stage": "Pre-pricing",
                    "filed": "2026-09-01",
                },
                {
                    "id": "s1-new",
                    "company": "New S1 Co",
                    "cik": "2",
                    "form": "S-1/A",
                    "stage": "Pre-pricing",
                    "filed": "2026-09-01",
                },
            ]
        }
        queue = {
            "filings": watch["filings"]
            + [
                {
                    "id": "final-old-public",
                    "company": "Old Public Final Co",
                    "cik": "3",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-09-02",
                    "pricing_date": "2026-09-01",
                },
                {
                    "id": "final-new",
                    "company": "New Final Co",
                    "cik": "4",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-09-02",
                    "pricing_date": "2026-09-01",
                },
            ]
        }
        main = {}
        archives = {}
        for cik in ("0000000001", "0000000002", "0000000003", "0000000004"):
            name = f"CIK{cik}-submissions-001.json"
            main[cik] = {
                "filings": {
                    "recent": {"form": ["S-1"], "filingDate": ["2026-09-01"]},
                    "files": [{"name": name, "filingFrom": "2020-01-01"}],
                }
            }
            archives[name] = {"form": ["S-1"], "filingDate": ["2025-01-01"]}
        archives["CIK0000000001-submissions-001.json"] = {
            "form": ["8-K"], "filingDate": ["2025-01-01"]
        }
        archives["CIK0000000003-submissions-001.json"] = {
            "form": ["10-Q"], "filingDate": ["2025-01-01"]
        }

        updated_watch, updated_queue, excluded_s1, excluded_final = gate.sanitize_payloads(
            watch,
            queue,
            submissions_loader=lambda cik: main[cik],
            archive_loader=lambda name: archives[name],
        )

        self.assertEqual({"0000000001"}, excluded_s1)
        self.assertEqual(1, len(excluded_final))
        self.assertEqual(["s1-new"], [row["id"] for row in updated_watch["filings"]])
        self.assertEqual(
            ["s1-new", "final-new"],
            [row["id"] for row in updated_queue["filings"]],
        )

    def test_prepricing_archive_failure_does_not_invent_exclusion(self):
        watch = {
            "filings": [
                {
                    "id": "s1",
                    "company": "Ambiguous S1 Co",
                    "cik": "1",
                    "form": "S-1",
                    "stage": "Pre-pricing",
                    "filed": "2026-09-01",
                }
            ]
        }
        queue = {"filings": list(watch["filings"])}
        submissions = {
            "filings": {
                "recent": {"form": ["S-1"], "filingDate": ["2026-09-01"]},
                "files": [{"name": "CIK0000000001-submissions-001.json"}],
            }
        }
        updated_watch, updated_queue, excluded_s1, excluded_final = gate.sanitize_payloads(
            watch,
            queue,
            submissions_loader=lambda _cik: submissions,
            archive_loader=lambda _name: (_ for _ in ()).throw(RuntimeError("SEC unavailable")),
        )
        self.assertEqual(set(), excluded_s1)
        self.assertEqual(set(), excluded_final)
        self.assertEqual(watch["filings"], updated_watch["filings"])
        self.assertEqual(queue["filings"], updated_queue["filings"])

    def test_final_archive_failure_blocks_release(self):
        queue = {
            "filings": [
                {
                    "id": "final",
                    "company": "Ambiguous Final Co",
                    "cik": "1",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-09-02",
                    "pricing_date": "2026-09-01",
                }
            ]
        }
        submissions = {
            "filings": {
                "recent": {"form": ["424B4"], "filingDate": ["2026-09-02"]},
                "files": [{"name": "CIK0000000001-submissions-001.json"}],
            }
        }
        with self.assertRaises(gate.ArchivedReportingHistoryError):
            gate.sanitize_payloads(
                {"filings": []},
                queue,
                submissions_loader=lambda _cik: submissions,
                archive_loader=lambda _name: (_ for _ in ()).throw(RuntimeError("SEC unavailable")),
            )


if __name__ == "__main__":
    unittest.main()
