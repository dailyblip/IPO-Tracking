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


def _prepricing(filed="2026-08-10"):
    return {
        "cik": "1234567",
        "accession_no": "0001234567-26-000010",
        "form": "S-1/A",
        "filed": filed,
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


def test_registration_lineage_cache_does_not_let_valid_row_bless_stale_duplicate():
    resolver = _resolver()

    assert resolver(_prepricing(), _final_meta()) is True
    assert resolver(_prepricing("2026-08-11"), _final_meta()) is False


def test_registration_lineage_cache_does_not_let_stale_row_poison_valid_duplicate():
    resolver = _resolver()

    assert resolver(_prepricing("2026-08-11"), _final_meta()) is False
    assert resolver(_prepricing(), _final_meta()) is True


def test_registration_lineage_cache_rechecks_candidate_final_date_each_call():
    resolver = _resolver()
    stale_final = dict(_final_meta(), filing_date="2026-08-21")

    assert resolver(_prepricing(), _final_meta()) is True
    assert resolver(_prepricing(), stale_final) is False


def test_registration_lineage_cache_bad_candidate_date_does_not_poison_valid_metadata():
    resolver = _resolver()
    stale_final = dict(_final_meta(), filing_date="2026-08-21")

    assert resolver(_prepricing(), stale_final) is False
    assert resolver(_prepricing(), _final_meta()) is True
