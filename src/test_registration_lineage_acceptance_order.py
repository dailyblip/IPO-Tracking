import registration_lineage


def _resolver(s1_acceptance=None, final_acceptance=None, *, final_date="2026-09-10"):
    rows = [
        {
            "accession_no": "0001234567-26-000010",
            "form": "S-1/A",
            "file_number": "333-300001",
            "filing_date": "2026-09-10",
            "acceptance_datetime": s1_acceptance,
        },
        {
            "accession_no": "0001234567-26-000020",
            "form": "424B4",
            "file_number": "333-300001",
            "filing_date": final_date,
            "acceptance_datetime": final_acceptance,
        },
    ]

    def load(cik, required_accessions):
        assert cik == "0001234567"
        assert set(required_accessions)
        return rows

    return registration_lineage.build_registration_lineage_resolver(load)


def _prepricing():
    return {
        "cik": "1234567",
        "accession_no": "0001234567-26-000010",
        "form": "S-1/A",
        "filed": "2026-09-10",
    }


def _final(filing_date="2026-09-10"):
    return {
        "cik": "0001234567",
        "accession_no": "0001234567-26-000020",
        "filing_date": filing_date,
    }


def test_same_day_lineage_rejects_registration_accepted_after_final_prospectus():
    resolver = _resolver(
        "2026-09-10T20:30:00.000Z",
        "2026-09-10T19:45:00.000Z",
    )

    assert resolver(_prepricing(), _final()) is False


def test_same_day_lineage_accepts_proven_registration_before_final_prospectus():
    resolver = _resolver(
        "2026-09-10T19:45:00.000Z",
        "2026-09-10T20:30:00.000Z",
    )

    assert resolver(_prepricing(), _final()) is True


def test_same_day_lineage_fails_closed_without_acceptance_order():
    resolver = _resolver(None, None)

    assert resolver(_prepricing(), _final()) is False


def test_different_day_lineage_does_not_require_acceptance_timestamp():
    resolver = _resolver(None, None, final_date="2026-09-11")

    assert resolver(_prepricing(), _final("2026-09-11")) is True


def test_rows_from_block_preserves_aligned_acceptance_timestamp():
    rows = registration_lineage._rows_from_block(
        {
            "accessionNumber": ["0001234567-26-000010"],
            "form": ["S-1/A"],
            "fileNumber": ["333-300001"],
            "filingDate": ["2026-09-10"],
            "acceptanceDateTime": ["2026-09-10T19:45:00.000Z"],
        }
    )

    assert rows[0]["acceptance_datetime"] == "2026-09-10T19:45:00.000Z"


def test_rows_from_block_rejects_misaligned_acceptance_timestamp_array():
    try:
        registration_lineage._rows_from_block(
            {
                "accessionNumber": ["0001234567-26-000010"],
                "form": ["S-1/A"],
                "fileNumber": ["333-300001"],
                "filingDate": ["2026-09-10"],
                "acceptanceDateTime": [],
            }
        )
    except ValueError as error:
        assert "acceptance-time array is not aligned" in str(error)
    else:
        raise AssertionError("Misaligned SEC acceptance timestamps must fail closed")
