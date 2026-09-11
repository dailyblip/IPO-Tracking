"""Regression coverage for concurrent S-1 registrations under one SEC CIK.

An issuer can have an older completed IPO registration and a separate newer S-1
registration at the same time. Lifecycle reconciliation must preserve the older
final record while independently promoting the newer registration only when exact
SEC registration lineage proves its own 424B4 final.
"""

import unittest
from unittest import mock

import lifecycle_reconciler as lr


def _fixture():
    old_final = {
        "cik": "0001234567",
        "company": "Acme Corp.",
        "accession_no": "0001234567-26-000100",
        "form": "424B4",
        "stage": "Priced",
        "filed": "2026-06-11",
        "pricing_date": "2026-06-10",
        "ticker": "ACME",
        "offering_price": 10.0,
        "value": 200_000_000.0,
        "value_label": "$200M",
        "primary_offering_shares": 20_000_000,
        "secondary_offering_shares": None,
        "offering_size_source": "final 424B4 explicit issuer-only THE OFFERING row",
        "offering_size_confidence": "High",
        "sec_url": "https://www.sec.gov/Archives/edgar/data/1234567/000123456726000100/0001234567-26-000100-index.htm",
    }
    new_prepricing = {
        "cik": "0001234567",
        "company": "Acme Corp.",
        "accession_no": "0001234567-26-000200",
        "form": "S-1/A",
        "stage": "Pre-pricing",
        "filed": "2026-09-01",
        "ticker": "ACME",
    }
    old_final_meta = {
        "cik": "0001234567",
        "accession_no": "0001234567-26-000100",
        "form": "424B4",
        "filing_date": "2026-06-11",
        "primary_document": "old.htm",
        "ticker": "ACME",
    }
    new_final_meta = {
        "cik": "0001234567",
        "accession_no": "0001234567-26-000300",
        "form": "424B4",
        "filing_date": "2026-09-10",
        "primary_document": "new.htm",
        "ticker": "ACME",
    }
    promoted = {
        **new_prepricing,
        "id": new_final_meta["accession_no"],
        "accession_no": new_final_meta["accession_no"],
        "form": "424B4",
        "stage": "Priced",
        "filed": new_final_meta["filing_date"],
        "pricing_date": None,
        "offering_price": 12.0,
    }
    return old_final, new_prepricing, old_final_meta, new_final_meta, promoted


def _new_registration_only(prepricing, candidate):
    return (
        prepricing.get("accession_no") == "0001234567-26-000200"
        and candidate.get("accession_no") == "0001234567-26-000300"
    )


class ConcurrentRegistrationLifecycleTest(unittest.TestCase):
    def test_confirmed_new_registration_promotes_without_redirecting_existing_final(self):
        old_final, new_prepricing, old_meta, new_meta, promoted = _fixture()
        payload = {"filings": [old_final, new_prepricing]}

        with mock.patch.object(lr, "_promote_prepricing_record", return_value=promoted):
            reconciled, repaired, removed = lr.reconcile_payload(
                payload,
                [old_meta, new_meta],
                lambda _meta: object(),
                lineage_resolver=_new_registration_only,
            )

        self.assertEqual(1, repaired)
        self.assertEqual(1, removed)
        self.assertEqual([old_final, promoted], reconciled["filings"])

    def test_missing_old_final_metadata_still_allows_independent_new_promotion(self):
        old_final, new_prepricing, _old_meta, new_meta, promoted = _fixture()
        payload = {"filings": [old_final, new_prepricing]}

        with mock.patch.object(lr, "_promote_prepricing_record", return_value=promoted):
            reconciled, repaired, removed = lr.reconcile_payload(
                payload,
                [new_meta],
                lambda _meta: object(),
                lineage_resolver=_new_registration_only,
            )

        self.assertEqual(1, repaired)
        self.assertEqual(1, removed)
        self.assertEqual([old_final, promoted], reconciled["filings"])

    def test_existing_new_final_removes_only_stale_prepricing_without_duplicate(self):
        old_final, new_prepricing, old_meta, new_meta, promoted = _fixture()
        published_new_final = {
            **promoted,
            "pricing_date": "2026-09-09",
        }
        payload = {"filings": [old_final, new_prepricing, published_new_final]}

        with mock.patch.object(
            lr,
            "_promote_prepricing_record",
            side_effect=AssertionError("existing final must not be duplicated"),
        ):
            reconciled, repaired, removed = lr.reconcile_payload(
                payload,
                [old_meta, new_meta],
                lambda _meta: object(),
                lineage_resolver=_new_registration_only,
            )

        self.assertEqual(0, repaired)
        self.assertEqual(1, removed)
        self.assertEqual([old_final, published_new_final], reconciled["filings"])

    def test_unverified_parallel_registration_fails_closed(self):
        old_final, new_prepricing, old_meta, new_meta, _promoted = _fixture()
        payload = {"filings": [old_final, new_prepricing]}

        reconciled, repaired, removed = lr.reconcile_payload(
            payload,
            [old_meta, new_meta],
            lambda _meta: object(),
            lineage_resolver=lambda _prepricing, _candidate: False,
        )

        self.assertEqual(0, repaired)
        self.assertEqual(0, removed)
        self.assertEqual([old_final, new_prepricing], reconciled["filings"])


if __name__ == "__main__":
    unittest.main()
