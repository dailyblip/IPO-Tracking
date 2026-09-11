"""Regression coverage for convergent parallel-registration lifecycle repair."""

import lifecycle_convergence as convergence
import lifecycle_reconciler as lr


def _prepricing(accession, filed):
    return {
        "cik": "0001234567",
        "company": "Acme Holdings",
        "form": "S-1/A",
        "stage": "Pre-pricing",
        "filed": filed,
        "accession_no": accession,
        "ticker": "ACME",
    }


def _final(accession, filed):
    return {
        "cik": "0001234567",
        "form": "424B4",
        "filing_date": filed,
        "accession_no": accession,
        "primary_document": f"{accession}.htm",
        "ticker": "ACME",
    }


def _promoted(record, meta):
    return {
        **record,
        "id": meta["accession_no"],
        "accession_no": meta["accession_no"],
        "form": "424B4",
        "stage": "Priced",
        "filed": meta["filing_date"],
        "pricing_date": meta["filing_date"],
        "offering_price": 10.0,
        "value": 50_000_000.0,
        "value_label": "$50M",
        "offering_size_source": "test final 424B4",
        "offering_size_confidence": "High",
    }


def test_parallel_finalized_registrations_promote_in_one_convergent_run(monkeypatch):
    first = _prepricing("0001234567-26-000100", "2026-08-01")
    second = _prepricing("0001234567-26-000200", "2026-08-05")
    first_final = _final("0001234567-26-000300", "2026-08-15")
    second_final = _final("0001234567-26-000400", "2026-08-18")
    lineage = {
        first["accession_no"]: first_final["accession_no"],
        second["accession_no"]: second_final["accession_no"],
    }

    monkeypatch.setattr(
        lr,
        "_promote_prepricing_record",
        lambda record, meta, _soup: _promoted(record, meta),
    )
    monkeypatch.setattr(lr, "_has_release_grade_final_size", lambda _record: True)
    monkeypatch.setattr(lr, "_can_preserve_release_grade_final", lambda _record, _meta: True)

    reconciled, repaired, removed, passes = convergence.reconcile_payload_to_convergence(
        {"filings": [first, second]},
        [first_final, second_final],
        lambda _meta: object(),
        lambda prepricing, final_meta: (
            lineage.get(prepricing.get("accession_no")) == final_meta.get("accession_no")
        ),
    )

    assert repaired == 2
    assert removed == 2
    assert passes == 3
    assert [record["accession_no"] for record in reconciled["filings"]] == [
        first_final["accession_no"],
        second_final["accession_no"],
    ]
    assert all(record["stage"] == "Priced" for record in reconciled["filings"])


def test_duplicate_prepricing_rows_do_not_emit_duplicate_final(monkeypatch):
    first = _prepricing("0001234567-26-000100", "2026-08-01")
    duplicate = _prepricing("0001234567-26-000101", "2026-08-02")
    final_meta = _final("0001234567-26-000300", "2026-08-15")

    monkeypatch.setattr(
        lr,
        "_promote_prepricing_record",
        lambda record, meta, _soup: _promoted(record, meta),
    )
    monkeypatch.setattr(lr, "_has_release_grade_final_size", lambda _record: True)
    monkeypatch.setattr(lr, "_can_preserve_release_grade_final", lambda _record, _meta: True)

    reconciled, repaired, removed, passes = convergence.reconcile_payload_to_convergence(
        {"filings": [first, duplicate]},
        [final_meta],
        lambda _meta: object(),
        lambda _prepricing, _final_meta: True,
    )

    assert repaired == 1
    assert removed == 2
    assert passes == 2
    assert len(reconciled["filings"]) == 1
    assert reconciled["filings"][0]["accession_no"] == final_meta["accession_no"]


def test_stability_probe_accepts_convergence_at_mutation_pass_boundary(monkeypatch):
    calls = []

    def reconcile_once(current, *_args, **_kwargs):
        calls.append(len(calls) + 1)
        if len(calls) <= 2:
            return current, 1, 1
        return current, 0, 0

    monkeypatch.setattr(lr, "reconcile_payload", reconcile_once)

    reconciled, repaired, removed, passes = convergence.reconcile_payload_to_convergence(
        {"filings": []},
        [],
        lambda _meta: object(),
        lambda _prepricing, _final_meta: False,
        max_passes=2,
    )

    assert reconciled == {"filings": []}
    assert repaired == 2
    assert removed == 2
    assert passes == 3
    assert calls == [1, 2, 3]


def test_stability_probe_does_not_expand_mutation_budget(monkeypatch):
    calls = []

    def never_stable(current, *_args, **_kwargs):
        calls.append(len(calls) + 1)
        return current, 1, 0

    monkeypatch.setattr(lr, "reconcile_payload", never_stable)

    try:
        convergence.reconcile_payload_to_convergence(
            {"filings": []},
            [],
            lambda _meta: object(),
            lambda _prepricing, _final_meta: False,
            max_passes=2,
        )
    except RuntimeError as exc:
        assert "2 mutation pass(es)" in str(exc)
    else:
        raise AssertionError("expected lifecycle convergence boundary to fail closed")

    assert calls == [1, 2, 3]
