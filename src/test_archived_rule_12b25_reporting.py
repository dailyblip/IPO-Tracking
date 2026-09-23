import unittest

import archived_reporting_history_gate as gate


class ArchivedRule12b25ReportingTests(unittest.TestCase):
    def _submissions(self):
        return {
            "filings": {
                "recent": {
                    "form": ["S-1"],
                    "filingDate": ["2026-09-01"],
                },
                "files": [
                    {
                        "name": "CIK0000000001-submissions-001.json",
                        "filingFrom": "2020-01-01",
                        "filingTo": "2025-12-31",
                    }
                ],
            }
        }

    def test_archived_rule_12b25_notices_prove_prior_reporting(self):
        forms = (
            "NT 10-Q",
            "NT 10-Q/A",
            "NT 10-K",
            "NT 10-K/A",
            "NT 20-F",
            "NT 20-F/A",
        )
        for form in forms:
            with self.subTest(form=form):
                archived = {"form": [form], "filingDate": ["2025-04-10"]}
                self.assertTrue(
                    gate.has_prior_reporting_history(
                        self._submissions(),
                        "2026-09-01",
                        archive_loader=lambda _name, archived=archived: archived,
                    )
                )

    def test_same_day_archived_rule_12b25_notice_does_not_guess_order(self):
        archived = {"form": ["NT 10-Q"], "filingDate": ["2026-09-01"]}
        self.assertFalse(
            gate.has_prior_reporting_history(
                self._submissions(),
                "2026-09-01",
                archive_loader=lambda _name: archived,
            )
        )


if __name__ == "__main__":
    unittest.main()
