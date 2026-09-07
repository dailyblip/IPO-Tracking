import json

from bs4 import BeautifulSoup

import s1_registration_history_gate as gate


def _pbt_record():
    return {
        "id": "s1:0002142855",
        "company": "PBT Land & Minerals, Inc.",
        "ticker": "PBT",
        "cik": "0002142855",
        "accession_no": "0001213900-26-097366",
        "form": "S-1/A",
        "stage": "Pre-pricing",
        "filed": "2026-09-04",
    }


def test_current_registration_identifies_explicit_rights_offering(monkeypatch):
    record = _pbt_record()
    monkeypatch.setattr(
        gate,
        "_recent_submission_rows",
        lambda cik: [
            {
                "accession_no": record["accession_no"],
                "form": "S-1/A",
                "file_number": "333-000000",
                "filing_date": record["filed"],
                "primary_document": "ea0260000-s1a1.htm",
            }
        ],
    )
    filing_text = """
        PROSPECTUS — RIGHTS OFFERING
        PBT Land & Minerals, Inc. is distributing non-transferable subscription
        rights to holders of Permian Basin Royalty Trust units. Each Subscription
        Right permits the holder to purchase shares in the Rights Offering.
    """
    monkeypatch.setattr(
        gate.filing_parser,
        "fetch_document",
        lambda url: BeautifulSoup(filing_text, "html.parser"),
    )

    assert gate.current_registration_is_rights_offering(record) is True


def test_ordinary_ipo_rights_language_does_not_trigger_rights_offering(monkeypatch):
    record = _pbt_record()
    record["company"] = "Example Operating Co."
    monkeypatch.setattr(
        gate,
        "_recent_submission_rows",
        lambda cik: [
            {
                "accession_no": record["accession_no"],
                "form": "S-1/A",
                "file_number": "333-000001",
                "filing_date": record["filed"],
                "primary_document": "s1a.htm",
            }
        ],
    )
    filing_text = """
        This is our initial public offering of common stock. We are offering
        10,000,000 shares through the underwriters. Our charter discusses
        stockholder rights and we may consider other capital raises in the future.
    """
    monkeypatch.setattr(
        gate.filing_parser,
        "fetch_document",
        lambda url: BeautifulSoup(filing_text, "html.parser"),
    )

    assert gate.current_registration_is_rights_offering(record) is False


def test_gate_removes_rights_offering_from_watch_and_public_queue(tmp_path, monkeypatch):
    record = _pbt_record()
    watch_path = tmp_path / "s1_watch.json"
    queue_path = tmp_path / "filings.json"
    watch_path.write_text(json.dumps({"filings": [record]}), encoding="utf-8")
    queue_path.write_text(json.dumps({"filings": [record]}), encoding="utf-8")

    monkeypatch.setattr(gate, "already_reporting_before_registration", lambda row: False)
    monkeypatch.setattr(gate, "current_registration_is_rights_offering", lambda row: True)

    def _unexpected_resale_check(row):
        raise AssertionError("rights-offering exclusion should short-circuit resale history")

    monkeypatch.setattr(gate, "amendment_inherits_resale_exclusion", _unexpected_resale_check)

    excluded = gate.apply_gate(watch_path, queue_path)

    assert excluded == {"0002142855"}
    assert json.loads(watch_path.read_text(encoding="utf-8"))["filings"] == []
    assert json.loads(queue_path.read_text(encoding="utf-8"))["filings"] == []
