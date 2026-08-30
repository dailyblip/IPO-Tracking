from unittest.mock import Mock

import edgar_client
import main


def _submissions_response(forms, accessions, filing_dates):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "filings": {
            "recent": {
                "form": forms,
                "accessionNumber": accessions,
                "filingDate": filing_dates,
            }
        }
    }
    return response


def test_find_matching_s1_ignores_post_pricing_registration(monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "Research Monitor test@example.com")
    monkeypatch.setattr(edgar_client.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        edgar_client.requests,
        "get",
        lambda *_args, **_kwargs: _submissions_response(
            ["S-1", "424B4", "S-1/A", "S-1"],
            [
                "0000000000-26-000400",
                "0000000000-26-000300",
                "0000000000-26-000200",
                "0000000000-26-000100",
            ],
            ["2026-06-01", "2026-04-20", "2026-04-15", "2026-03-23"],
        ),
    )

    result = edgar_client.find_matching_s1("1234567", before_date="2026-04-20")

    assert result == {
        "form_type": "S-1/A",
        "accession_no": "0000000000-26-000200",
        "filing_date": "2026-04-15",
    }


def test_find_matching_s1_returns_blank_when_only_registration_is_later(monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "Research Monitor test@example.com")
    monkeypatch.setattr(edgar_client.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        edgar_client.requests,
        "get",
        lambda *_args, **_kwargs: _submissions_response(
            ["S-1", "424B4"],
            ["0000000000-26-000400", "0000000000-26-000300"],
            ["2026-06-01", "2026-04-20"],
        ),
    )

    assert edgar_client.find_matching_s1("1234567", before_date="2026-04-20") == {}


def test_process_filing_passes_424b4_date_to_s1_matcher(monkeypatch):
    seen = {}
    monkeypatch.setattr(main.edgar_client, "is_us_based", lambda _cik: True)
    monkeypatch.setattr(main.edgar_client, "is_first_time_registrant", lambda _cik: True)

    def fake_find_matching_s1(cik, before_date=None):
        seen["cik"] = cik
        seen["before_date"] = before_date
        return {}

    monkeypatch.setattr(main.edgar_client, "find_matching_s1", fake_find_matching_s1)

    rows = main.process_filing(
        {
            "company_name": "AEVEX Aerospace",
            "cik": "1234567",
            "accession_no": "0000000000-26-000300",
            "filing_date": "2026-04-20",
            "form_type": "424B4",
        }
    )

    assert rows == []
    assert seen == {"cik": "1234567", "before_date": "2026-04-20"}
