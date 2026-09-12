"""Regression coverage for multiple published final registrations under one CIK."""

import lifecycle_convergence as convergence
import lifecycle_reconciler as lr


def _published_final(accession, filed, price):
    return {
        "cik": "0001234567",
        "company": "Acme Holdings",
        "form": "424B4",
        "stage": "Priced",
        "filed": filed,
        "pricing_date": filed,
        "id": accession,
        "accession_no": accession,
        "ticker": "ACME",
        "offering_price": price,
        "value": 50_000_000.0,
        "value_label": "$50M",
        "offering_size_source": "test final 424B4",
        "offering_size_confidence": "High",
    }


def _final_meta(accession, filed):
    return {
        "cik": "0001234567",
        "form": "424B4",
        "filing_date": filed,
        "accession_no": accession,
        "primary_document": f"{accession}.htm",
        "ticker": "ACME",
    }


def test_each_existing_final_under_same_cik_is_rechecked(monkeypatch):
    first = _published_final("0001234567-26-000300", "2026-08-15", 10.0)
    second = _published_final("0001234567-26-000400", "2026-08-18", 11.0)
    first_meta = _final_meta(first["accession_no"], first["filed"])
    second_meta = _final_meta(second["accession_no"], second["filed"])
    repaired_accessions = []

    monkeypatch.setattr(
        lr,
        "_has_release_grade_final_size",
        lambda record: record.get("offering_price") in {10.0, 22.0},
    )
    monkeypatch.setattr(lr, "_can_preserve_release_grade_final", lambda _record, _meta: True)

    def repair(record, meta, _soup):
        repaired_accessions.append(meta["accession_no"])
        return {**record, "offering_price": 22.0}

    monkeypatch.setattr(lr, "_repair_final_record", repair)

    reconciled, repaired, removed, passes = convergence.reconcile_payload_to_convergence(
        {"filings": [first, second]},
        [first_meta, second_meta],
        lambda _meta: object(),
        lambda _prepricing, _final_meta: False,
    )

    assert repaired == 1
    assert removed == 0
    assert passes == 2
    assert repaired_accessions == [second["accession_no"]]
    assert [record["offering_price"] for record in reconciled["filings"]] == [10.0, 22.0]
