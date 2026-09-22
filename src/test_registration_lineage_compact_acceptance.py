from datetime import datetime

import registration_lineage


def _resolver(s1_acceptance, final_acceptance):
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
            "filing_date": "2026-09-10",
            "acceptance_datetime": final_acceptance,
        },
    ]
    return registration_lineage.build_registration_lineage_resolver(
        lambda cik, required_accessions: rows
    )


def _prepricing():
    return {
        "cik": "1234567",
        "accession_no": "0001234567-26-000010",
        "filed": "2026-09-10",
    }


def _final():
    return {
        "cik": "0001234567",
        "accession_no": "0001234567-26-000020",
        "filing_date": "2026-09-10",
    }


def test_compact_edgar_acceptance_is_normalized_from_eastern_to_utc():
    assert registration_lineage._canonical_acceptance_datetime(
        "20260910160000"
    ) == datetime(2026, 9, 10, 20, 0, 0)


def test_mixed_compact_and_iso_rejects_false_same_day_order():
    resolver = _resolver(
        "20260910160000",  # 16:00 ET = 20:00 UTC
        "2026-09-10T19:45:00Z",
    )
    assert resolver(_prepricing(), _final()) is False


def test_mixed_compact_and_iso_accepts_proven_same_day_order():
    resolver = _resolver(
        "20260910150000",  # 15:00 ET = 19:00 UTC
        "2026-09-10T19:45:00Z",
    )
    assert resolver(_prepricing(), _final()) is True


def test_naive_iso_acceptance_fails_closed():
    resolver = _resolver(
        "2026-09-10T19:00:00",
        "2026-09-10T19:45:00Z",
    )
    assert resolver(_prepricing(), _final()) is False
