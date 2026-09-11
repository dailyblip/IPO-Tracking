"""Regression coverage for parallel pre-pricing registrations under one SEC CIK.

When one S-1/S-1A lineage reaches a final 424B4 while another registration remains
pre-pricing under the same issuer CIK, lifecycle promotion must remove only the
registration that actually belongs to the final prospectus.
"""

import lifecycle_reconciler as lr


def _scenario():
    matched = {
        "cik": "0001234567",
        "company": "Acme Holdings",
        "form": "S-1/A",
        "stage": "Pre-pricing",
        "filed": "2026-08-01",
        "accession_no": "0001234567-26-000100",
        "ticker": "ACME",
    }
    separate = {
        "cik": "0001234567",
        "company": "Acme Holdings",
        "form": "S-1/A",
        "stage": "Pre-pricing",
        "filed": "2026-09-01",
        "accession_no": "0001234567-26-000200",
        "ticker": "ACME",
    }
    final_meta = {
        "cik": "0001234567",
        "form": "424B4",
        "filing_date": "2026-08-15",
        "accession_no": "0001234567-26-000300",
        "primary_document": "acme-final.htm",
        "ticker": "ACME",
    }
    promoted = {
        **matched,
        "form": "424B4",
        "stage": "Priced",
        "filed": "2026-08-15",
        "accession_no": "0001234567-26-000300",
    }
    return matched, separate, final_meta, promoted


def _reconcile(monkeypatch, filings):
    matched, _separate, final_meta, promoted = _scenario()
    monkeypatch.setattr(
        lr,
        "_promote_prepricing_record",
        lambda _record, _meta, _soup: promoted,
    )
    return lr.reconcile_payload(
        {"filings": filings},
        [final_meta],
        lambda _meta: object(),
        lineage_resolver=lambda prepricing, _final: (
            prepricing.get("accession_no") == matched["accession_no"]
        ),
    )


def test_promotion_keeps_unrelated_prepricing_registration_under_same_cik(monkeypatch):
    matched, separate, _final_meta, promoted = _scenario()

    reconciled, repaired, removed = _reconcile(monkeypatch, [matched, separate])

    assert repaired == 1
    assert removed == 1
    assert reconciled["filings"] == [promoted, separate]


def test_promotion_is_not_blocked_when_unrelated_registration_appears_first(monkeypatch):
    matched, separate, _final_meta, promoted = _scenario()

    reconciled, repaired, removed = _reconcile(monkeypatch, [separate, matched])

    assert repaired == 1
    assert removed == 1
    assert reconciled["filings"] == [separate, promoted]
