"""Regression coverage for exact final 424B4 accession identity."""

import unittest
from pathlib import Path

import final_accession_identity_guard as guard


def _final(**overrides):
    record = {
        "id": "0001234567-26-000400",
        "company": "Acme Holdings",
        "ticker": "ACME",
        "cik": "0001234567",
        "accession_no": "0001234567-26-000400",
        "form": "424B4",
        "stage": "Priced",
        "filed": "2026-08-18",
        "pricing_date": "2026-08-17",
        "offering_price": 11.0,
    }
    record.update(overrides)
    return record


class FinalAccessionIdentityGuardTests(unittest.TestCase):
    def test_blank_final_accession_is_recovered_only_from_accession_shaped_id(self):
        final = _final(accession_no="")
        payload, repaired = guard.repair_final_accession_identities({"filings": [final]})

        self.assertEqual(repaired, 1)
        self.assertEqual(payload["filings"][0]["accession_no"], final["id"])
        self.assertEqual(payload["filings"][0]["ticker"], "ACME")
        self.assertIn("generated_at", payload)

    def test_final_without_exact_accession_identity_fails_closed(self):
        final = _final(id="acme-final", accession_no="")

        with self.assertRaisesRegex(
            RuntimeError, "lacks an exact SEC accession identity"
        ):
            guard.repair_final_accession_identities({"filings": [final]})

    def test_conflicting_final_accession_identity_fails_closed(self):
        final = _final(
            id="0001234567-26-000400",
            accession_no="0001234567-26-000300",
        )

        with self.assertRaisesRegex(
            RuntimeError, "conflicting SEC accession identities"
        ):
            guard.repair_final_accession_identities({"filings": [final]})

    def test_non_final_records_are_not_rewritten(self):
        prepricing = {
            "id": "s1:0001234567",
            "cik": "0001234567",
            "accession_no": "",
            "form": "S-1",
            "stage": "Pre-pricing",
        }
        payload, repaired = guard.repair_final_accession_identities(
            {"filings": [prepricing]}
        )

        self.assertEqual(repaired, 0)
        self.assertEqual(payload["filings"], [prepricing])

    def test_daily_workflow_guards_final_accession_before_lifecycle_reconciliation(self):
        workflow = (
            Path(__file__).resolve().parents[1] / ".github" / "workflows" / "daily.yml"
        ).read_text(encoding="utf-8")

        guard_step = "python final_accession_identity_guard.py ../docs/data/filings.json"
        lifecycle_step = "python lifecycle_reconciler.py ../docs/data/filings.json"
        self.assertIn(guard_step, workflow)
        self.assertIn(lifecycle_step, workflow)
        self.assertLess(workflow.index(guard_step), workflow.index(lifecycle_step))


if __name__ == "__main__":
    unittest.main()
