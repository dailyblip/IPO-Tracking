"""Regression coverage for aged published-final SEC identity recovery."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import lifecycle_convergence
import published_final_history


CIK = "0001234567"
ACCESSION = "0001234567-26-000300"


def _published_final():
    return {
        "id": ACCESSION,
        "accession_no": ACCESSION,
        "cik": CIK,
        "company": "Acme Holdings",
        "form": "424B4",
        "stage": "Priced",
        "filed": "2026-06-15",
        "pricing_date": "2026-06-14",
        "offering_price": 10.0,
        "ticker": "ACME",
    }


def _sec_row(form="424B4", filing_date="2026-06-15"):
    return {
        "accession_no": ACCESSION,
        "form": form,
        "file_number": "333-123456",
        "filing_date": filing_date,
    }


class PublishedFinalHistoryTests(unittest.TestCase):
    def test_adds_exact_aged_final_missing_from_recent_snapshot(self):
        calls = []

        def rows_loader(cik, required_accessions):
            calls.append((cik, tuple(required_accessions)))
            return [_sec_row()]

        augmented = published_final_history.augment_published_final_metadata(
            {"filings": [_published_final()]},
            [],
            rows_loader=rows_loader,
        )

        self.assertEqual(calls, [(CIK, (ACCESSION.replace("-", ""),))])
        self.assertEqual(len(augmented), 1)
        self.assertEqual(augmented[0]["cik"], CIK)
        self.assertEqual(augmented[0]["accession_no"], ACCESSION)
        self.assertEqual(augmented[0]["filing_date"], "2026-06-15")
        self.assertEqual(augmented[0]["form_type"], "424B4")
        self.assertIsNone(augmented[0]["ticker"])

    def test_recent_exact_candidate_does_not_reload_history(self):
        recent = [{
            "cik": CIK,
            "accession_no": ACCESSION,
            "filing_date": "2026-06-15",
            "form_type": "424B4",
            "ticker": "ACME",
        }]

        def unexpected_loader(*_args, **_kwargs):
            raise AssertionError("exact recent candidate should skip SEC history reload")

        augmented = published_final_history.augment_published_final_metadata(
            {"filings": [_published_final()]},
            recent,
            rows_loader=unexpected_loader,
        )
        self.assertEqual(augmented, recent)

    def test_successful_history_lookup_with_wrong_form_blocks_release(self):
        with self.assertRaisesRegex(RuntimeError, "not a 424B4"):
            published_final_history.augment_published_final_metadata(
                {"filings": [_published_final()]},
                [],
                rows_loader=lambda *_args: [_sec_row(form="S-1/A")],
            )

    def test_successful_history_lookup_without_unique_exact_accession_blocks_release(self):
        with self.assertRaisesRegex(RuntimeError, "could not be uniquely confirmed"):
            published_final_history.augment_published_final_metadata(
                {"filings": [_published_final()]},
                [],
                rows_loader=lambda *_args: [],
            )

    def test_transient_history_failure_preserves_current_snapshot(self):
        recent = [{
            "cik": "0007654321",
            "accession_no": "0007654321-26-000999",
            "filing_date": "2026-09-01",
            "form_type": "424B4",
        }]

        def unavailable(*_args):
            raise ConnectionError("temporary SEC failure")

        augmented = published_final_history.augment_published_final_metadata(
            {"filings": [_published_final()]},
            recent,
            rows_loader=unavailable,
        )
        self.assertEqual(augmented, recent)

    def test_convergence_feed_augments_aged_finals_before_reconciliation(self):
        payload = {"filings": [_published_final()]}
        aged_candidate = {
            "cik": CIK,
            "accession_no": ACCESSION,
            "filing_date": "2026-06-15",
            "form_type": "424B4",
            "ticker": None,
        }

        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "filings.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with (
                mock.patch.object(
                    lifecycle_convergence.edgar_client,
                    "find_recent_424b4_filings",
                    return_value=[],
                ),
                mock.patch.object(
                    lifecycle_convergence.published_final_history,
                    "augment_published_final_metadata",
                    return_value=[aged_candidate],
                ) as augment,
                mock.patch.object(
                    lifecycle_convergence.registration_lineage,
                    "build_registration_lineage_resolver",
                    return_value=object(),
                ),
                mock.patch.object(
                    lifecycle_convergence,
                    "reconcile_payload_to_convergence",
                    return_value=(payload, 0, 0, 1),
                ) as converge,
                mock.patch.object(
                    lifecycle_convergence.dashboard_export,
                    "write_dashboard_csv",
                ),
            ):
                lifecycle_convergence.reconcile_feed(path)

        augment.assert_called_once_with(payload, [])
        self.assertEqual(converge.call_args.args[1], [aged_candidate])


if __name__ == "__main__":
    unittest.main()
