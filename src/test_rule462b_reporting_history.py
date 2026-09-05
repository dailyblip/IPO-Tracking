import unittest

import archived_reporting_history_gate as archived_gate
import followon_sanitizer


RULE_462B_SHORT_FORMS = ("S-3MEF", "F-3MEF")


class Rule462BReportingHistoryTests(unittest.TestCase):
    def _final_payload(self):
        return {
            "filings": [
                {
                    "company": "Already Public Co.",
                    "cik": "1234567",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-08-02",
                    "pricing_date": "2026-08-02",
                }
            ]
        }

    def test_inline_gate_removes_prior_s3_f3_mef_issuers(self):
        for form in RULE_462B_SHORT_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form],
                            "filingDate": ["2026-08-01"],
                        }
                    }
                }
                updated, removed = followon_sanitizer.sanitize_payload(
                    self._final_payload(),
                    submissions_loader=lambda _cik, value=submissions: value,
                )
                self.assertEqual(updated["filings"], [])
                self.assertEqual(len(removed), 1)

    def test_inline_gate_does_not_infer_same_day_order(self):
        for form in RULE_462B_SHORT_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {
                            "form": [form],
                            "filingDate": ["2026-08-02"],
                        }
                    }
                }
                updated, removed = followon_sanitizer.sanitize_payload(
                    self._final_payload(),
                    submissions_loader=lambda _cik, value=submissions: value,
                )
                self.assertEqual(len(updated["filings"]), 1)
                self.assertEqual(removed, [])

    def test_archived_gate_detects_prior_s3_f3_mef(self):
        for form in RULE_462B_SHORT_FORMS:
            with self.subTest(form=form):
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
                archived = {"form": [form], "filingDate": ["2025-04-10"]}
                self.assertTrue(
                    archived_gate.has_prior_reporting_history(
                        submissions,
                        "2026-09-01",
                        archive_loader=lambda _name, value=archived: value,
                    )
                )

    def test_archived_gate_does_not_infer_same_day_order(self):
        for form in RULE_462B_SHORT_FORMS:
            with self.subTest(form=form):
                submissions = {
                    "filings": {
                        "recent": {"form": ["S-1"], "filingDate": ["2026-09-01"]},
                        "files": [
                            {
                                "name": "CIK0000000001-submissions-001.json",
                                "filingFrom": "2020-01-01",
                                "filingTo": "2026-09-01",
                            }
                        ],
                    }
                }
                archived = {"form": [form], "filingDate": ["2026-09-01"]}
                self.assertFalse(
                    archived_gate.has_prior_reporting_history(
                        submissions,
                        "2026-09-01",
                        archive_loader=lambda _name, value=archived: value,
                    )
                )


if __name__ == "__main__":
    unittest.main()
