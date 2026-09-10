"""Regression coverage for concurrent S-1 registrations under one SEC CIK.

An issuer can have an older completed IPO registration and a separate newer S-1
registration at the same time. Lifecycle reconciliation must never let the newer
registration redirect or delete the older final record merely because the CIK is
shared.
"""

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
    return old_final, new_prepricing, old_final_meta, new_final_meta


def _new_registration_only(prepricing, candidate):
    return (
        prepricing.get("accession_no") == "0001234567-26-000200"
        and candidate.get("accession_no") == "0001234567-26-000300"
    )


def _no_document_fetch(_meta):
    raise AssertionError("release-grade existing final should not require document fetch")


def test_concurrent_new_registration_does_not_redirect_or_delete_existing_final():
    old_final, new_prepricing, old_meta, new_meta = _fixture()
    payload = {"filings": [old_final, new_prepricing]}

    reconciled, repaired, removed = lr.reconcile_payload(
        payload,
        [old_meta, new_meta],
        _no_document_fetch,
        lineage_resolver=_new_registration_only,
    )

    assert repaired == 0
    assert removed == 0
    assert reconciled["filings"] == [old_final, new_prepricing]


def test_missing_existing_final_accession_does_not_fall_forward_to_new_registration():
    old_final, new_prepricing, _old_meta, new_meta = _fixture()
    payload = {"filings": [old_final, new_prepricing]}

    reconciled, repaired, removed = lr.reconcile_payload(
        payload,
        [new_meta],
        _no_document_fetch,
        lineage_resolver=_new_registration_only,
    )

    assert repaired == 0
    assert removed == 0
    assert reconciled["filings"] == [old_final, new_prepricing]
