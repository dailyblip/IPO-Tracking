import registration_lineage


def _rows_loader(rows):
    def load(cik, required_accessions):
        assert cik == "0001234567"
        assert set(required_accessions)
        return rows

    return load


def _resolver():
    return registration_lineage.build_registration_lineage_resolver(
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


def _final_meta():
    return {
        "cik": "0001234567",
        "accession_no": "0001234567-26-000020",
        "filing_date": "2026-08-20",
    }


def test_registration_lineage_rejects_stale_prepricing_filing_date():
    resolver = _resolver()

    assert resolver(
        {
            "cik": "1234567",
            "accession_no": "0001234567-26-000010",
            "form": "S-1/A",
            "filed": "2026-08-11",
        },
        _final_meta(),
    ) is False


def test_registration_lineage_requires_prepricing_chronology_evidence():
    resolver = _resolver()

    assert resolver(
        {
            "cik": "1234567",
            "accession_no": "0001234567-26-000010",
            "form": "S-1/A",
        },
        _final_meta(),
    ) is False


def test_registration_lineage_accepts_matching_filing_date_alias():
    resolver = _resolver()

    assert resolver(
        {
            "cik": "1234567",
            "accession_no": "0001234567-26-000010",
            "form": "S-1/A",
            "filing_date": "2026-08-10",
        },
        _final_meta(),
    ) is True
