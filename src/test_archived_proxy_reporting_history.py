import unittest

import archived_reporting_history_gate as gate


class ArchivedProxyReportingHistoryTests(unittest.TestCase):
    def test_archived_proxy_forms_prove_prior_reporting(self):
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

        for form in ("PRE 14A", "DEF 14A", "PRE 14C", "DEF 14C"):
            with self.subTest(form=form):
                archived = {"form": [form], "filingDate": ["2025-04-10"]}
                self.assertTrue(
                    gate.has_prior_reporting_history(
                        submissions,
                        "2026-09-01",
                        archive_loader=lambda _name, archived=archived: archived,
                    )
                )


if __name__ == "__main__":
    unittest.main()
