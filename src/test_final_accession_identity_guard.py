import pytest

import final_accession_identity_guard


def _priced_row(**overrides):
    row = {
        "id": "0001018724-26-000777",
        "accession_no": "0001018724-26-000777",
        "cik": "0001018724",
        "company_name": "Example Co",
        "form_type": "424B4",
        "stage": "Priced",
    }
    row.update(overrides)
    return row


def test_blank_final_accession_is_recovered_from_accession_shaped_id():
    payload = {"filings": [_priced_row(accession_no=None)]}

    updated, repaired = final_accession_identity_guard.repair_or_reject_final_identity(
        payload
    )

    assert repaired == 1
    assert updated["filings"][0]["accession_no"] == "0001018724-26-000777"


def test_undashed_final_accession_is_canonicalized_for_sec_urls():
    payload = {"filings": [_priced_row(accession_no="000101872426000777")]}

    updated, repaired = final_accession_identity_guard.repair_or_reject_final_identity(
        payload
    )

    assert repaired == 1
    assert updated["filings"][0]["accession_no"] == "0001018724-26-000777"


def test_blank_final_accession_recovered_from_undashed_id_is_dashed():
    payload = {
        "filings": [
            _priced_row(
                id="000101872426000777",
                accession_no=None,
            )
        ]
    }

    updated, repaired = final_accession_identity_guard.repair_or_reject_final_identity(
        payload
    )

    assert repaired == 1
    assert updated["filings"][0]["accession_no"] == "0001018724-26-000777"


def test_whitespace_around_final_accession_is_canonicalized():
    payload = {"filings": [_priced_row(accession_no=" 0001018724-26-000777 ")]}

    updated, repaired = final_accession_identity_guard.repair_or_reject_final_identity(
        payload
    )

    assert repaired == 1
    assert updated["filings"][0]["accession_no"] == "0001018724-26-000777"


def test_conflicting_final_accession_blocks_release():
    payload = {
        "filings": [
            _priced_row(
                id="0001018724-26-000777",
                accession_no="0001018724-26-000778",
            )
        ]
    }

    with pytest.raises(RuntimeError, match="conflicting final accession identities"):
        final_accession_identity_guard.repair_or_reject_final_identity(payload)


def test_final_row_without_exact_accession_blocks_release():
    payload = {
        "filings": [
            _priced_row(
                id="0001018724:priced",
                accession_no=None,
            )
        ]
    }

    with pytest.raises(RuntimeError, match="no exact SEC accession identity"):
        final_accession_identity_guard.repair_or_reject_final_identity(payload)


def test_invalid_nonblank_final_accession_blocks_instead_of_overwriting():
    payload = {
        "filings": [
            _priced_row(
                id="0001018724-26-000777",
                accession_no="not-an-accession",
            )
        ]
    }

    with pytest.raises(RuntimeError, match="invalid final accession_no"):
        final_accession_identity_guard.repair_or_reject_final_identity(payload)


def test_prepricing_row_is_not_subject_to_final_accession_gate():
    row = _priced_row(
        id="watch:0001018724:0001018724-26-000123",
        accession_no=None,
        form_type="S-1",
        stage="Pre-pricing",
    )
    payload = {"filings": [row]}

    updated, repaired = final_accession_identity_guard.repair_or_reject_final_identity(
        payload
    )

    assert repaired == 0
    assert updated["filings"][0] == row
