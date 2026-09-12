"""Regression coverage for exact final 424B4 accession identity."""

import json
from pathlib import Path

import pytest

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


def test_blank_final_accession_is_recovered_only_from_accession_shaped_id():
    final = _final(accession_no="")
    payload, repaired = guard.repair_final_accession_identities({"filings": [final]})

    assert repaired == 1
    assert payload["filings"][0]["accession_no"] == final["id"]
    assert payload["filings"][0]["ticker"] == "ACME"
    assert "generated_at" in payload


def test_final_without_exact_accession_identity_fails_closed():
    final = _final(id="acme-final", accession_no="")

    with pytest.raises(RuntimeError, match="lacks an exact SEC accession identity"):
        guard.repair_final_accession_identities({"filings": [final]})


def test_conflicting_final_accession_identity_fails_closed():
    final = _final(
        id="0001234567-26-000400",
        accession_no="0001234567-26-000300",
    )

    with pytest.raises(RuntimeError, match="conflicting SEC accession identities"):
        guard.repair_final_accession_identities({"filings": [final]})


def test_non_final_records_are_not_rewritten():
    prepricing = {
        "id": "s1:0001234567",
        "cik": "0001234567",
        "accession_no": "",
        "form": "S-1",
        "stage": "Pre-pricing",
    }
    payload, repaired = guard.repair_final_accession_identities({"filings": [prepricing]})

    assert repaired == 0
    assert payload["filings"] == [prepricing]


def test_daily_workflow_guards_final_accession_before_lifecycle_reconciliation():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "daily.yml"
    ).read_text(encoding="utf-8")

    guard_step = "python final_accession_identity_guard.py ../docs/data/filings.json"
    lifecycle_step = "python lifecycle_reconciler.py ../docs/data/filings.json"
    assert guard_step in workflow
    assert lifecycle_step in workflow
    assert workflow.index(guard_step) < workflow.index(lifecycle_step)
