import json

from bs4 import BeautifulSoup

import s1_registration_history_gate as gate


def _veri_record():
    return {
        "id": "s1:0002078149",
        "company": "Veri MedTech Holdings, Inc.",
        "ticker": "VRHI",
        "cik": "0002078149",
        "accession_no": "0001096906-26-001366",
        "form": "S-1/A",
        "stage": "Pre-pricing",
        "filed": "2026-09-14",
        "primary_offering_shares": 3_750_000,
        "offering_size_source": "primary offering; explicit issuer-only cover statement",
        "offering_size_confidence": "High",
    }


def _install_current_filing(monkeypatch, record, text):
    monkeypatch.setattr(
        gate,
        "_recent_submission_rows",
        lambda cik: [
            {
                "accession_no": record["accession_no"],
                "form": "S-1/A",
                "file_number": "333-291560",
                "filing_date": record["filed"],
                "primary_document": "vrhi_s1a.htm",
            }
        ],
    )
    monkeypatch.setattr(
        gate.filing_parser,
        "fetch_document",
        lambda url: BeautifulSoup(text, "html.parser"),
    )


def test_current_registration_excludes_explicit_preexisting_otc_market(monkeypatch):
    record = _veri_record()
    filing_text = """
        There is a limited public trading market for our Common Stock. Our Common
        Stock is quoted on the OTCID Market under the ticker symbol VRHI. As of
        September 12, 2026, the last reported price of our Common Stock was $1.36
        per share at market close. We intend to apply to list our Common Stock on
        the Nasdaq Capital Market under the symbol VRHI.
    """
    _install_current_filing(monkeypatch, record, filing_text)

    assert (
        gate.current_registration_exclusion_reason(record)
        == gate.EXISTING_PUBLIC_MARKET_EXCLUSION_REASON
    )


def test_otc_reference_without_preoffering_market_price_does_not_exclude(monkeypatch):
    record = _veri_record()
    record["company"] = "Example Operating Co."
    filing_text = """
        This is our initial public offering of common stock. Our industry includes
        companies whose securities may trade in OTC markets. We are offering
        4,000,000 shares through the underwriters and have applied to list our
        common stock on the Nasdaq Capital Market.
    """
    _install_current_filing(monkeypatch, record, filing_text)

    assert gate.current_registration_exclusion_reason(record) is None


def test_gate_removes_existing_otc_issuer_even_with_primary_offering(tmp_path, monkeypatch):
    record = _veri_record()
    watch_path = tmp_path / "s1_watch.json"
    queue_path = tmp_path / "filings.json"
    watch_path.write_text(json.dumps({"filings": [record]}), encoding="utf-8")
    queue_path.write_text(json.dumps({"filings": [record]}), encoding="utf-8")

    monkeypatch.setattr(gate, "already_reporting_before_registration", lambda row: False)
    monkeypatch.setattr(
        gate,
        "current_registration_exclusion_reason",
        lambda row: gate.EXISTING_PUBLIC_MARKET_EXCLUSION_REASON,
    )

    def _unexpected_resale_check(row):
        raise AssertionError("existing-public-market exclusion should short-circuit resale history")

    monkeypatch.setattr(gate, "amendment_inherits_resale_exclusion", _unexpected_resale_check)

    excluded = gate.apply_gate(watch_path, queue_path)

    assert excluded == {"0002078149"}
    assert json.loads(watch_path.read_text(encoding="utf-8"))["filings"] == []
    assert json.loads(queue_path.read_text(encoding="utf-8"))["filings"] == []
