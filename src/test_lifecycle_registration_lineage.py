import lifecycle_reconciler
import registration_lineage


def _rows_loader(rows):
    def load(cik, required_accessions):
        assert cik == "0001234567"
        assert set(required_accessions)
        return rows

    return load


def test_registration_lineage_requires_exact_sec_file_number():
    resolver = registration_lineage.build_registration_lineage_resolver(
        _rows_loader([
            {
                "accession_no": "0001234567-26-000010",
                "form": "S-1/A",
                "file_number": "333-300001",
                "filing_date": "2026-08-10",
            },
            {
                "accession_no": "0001234567-26-000020",
                "form": "424B4",
                "file_number": "333-300001",
                "filing_date": "2026-08-20",
            },
        ])
    )
    prepricing = {
        "cik": "1234567",
        "accession_no": "0001234567-26-000010",
        "form": "S-1/A",
        "filed": "2026-08-10",
    }
    final_meta = {
        "cik": "0001234567",
        "accession_no": "0001234567-26-000020",
        "filing_date": "2026-08-20",
    }

    assert resolver(prepricing, final_meta) is True


def test_registration_lineage_rejects_same_cik_different_registration():
    resolver = registration_lineage.build_registration_lineage_resolver(
        _rows_loader([
            {
                "accession_no": "0001234567-26-000010",
                "form": "S-1",
                "file_number": "333-300001",
                "filing_date": "2026-08-10",
            },
            {
                "accession_no": "0001234567-26-000020",
                "form": "424B4",
                "file_number": "333-299999",
                "filing_date": "2026-08-20",
            },
        ])
    )

    assert resolver(
        {
            "cik": "1234567",
            "accession_no": "0001234567-26-000010",
        },
        {
            "cik": "1234567",
            "accession_no": "0001234567-26-000020",
            "filing_date": "2026-08-20",
        },
    ) is False


def test_select_final_meta_uses_confirmed_registration_not_earliest_same_cik():
    prepricing = {
        "cik": "1234567",
        "accession_no": "0001234567-26-000010",
        "form": "S-1/A",
        "filed": "2026-08-10",
    }
    wrong_follow_on = {
        "cik": "1234567",
        "accession_no": "0001234567-26-000015",
        "filing_date": "2026-08-15",
    }
    correct_ipo_final = {
        "cik": "1234567",
        "accession_no": "0001234567-26-000020",
        "filing_date": "2026-08-20",
    }

    selected = lifecycle_reconciler._select_final_meta(
        [wrong_follow_on, correct_ipo_final],
        prepricing=prepricing,
        lineage_resolver=lambda _prepricing, candidate: (
            candidate["accession_no"] == correct_ipo_final["accession_no"]
        ),
    )

    assert selected == correct_ipo_final


def test_reconcile_payload_keeps_prepricing_when_lineage_cannot_be_confirmed():
    prepricing = {
        "id": "0001234567-26-000010",
        "accession_no": "0001234567-26-000010",
        "cik": "1234567",
        "company_name": "Example Operating Co",
        "ticker": "EXM",
        "form": "S-1/A",
        "stage": "Pre-pricing",
        "filed": "2026-08-10",
    }
    candidate = {
        "cik": "1234567",
        "accession_no": "0001234567-26-000020",
        "filing_date": "2026-08-20",
    }
    payload = {"filings": [prepricing]}

    def should_not_fetch(_meta):
        raise AssertionError("Unconfirmed registration lineage must not fetch/promote the final")

    reconciled, repaired, removed = lifecycle_reconciler.reconcile_payload(
        payload,
        [candidate],
        should_not_fetch,
        lineage_resolver=lambda _prepricing, _candidate: False,
    )

    assert reconciled["filings"] == [prepricing]
    assert repaired == 0
    assert removed == 0
