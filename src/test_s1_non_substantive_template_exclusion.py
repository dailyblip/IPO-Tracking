import json

import s1_substantive_registration_gate as gate


def _xiasan_record():
    return {
        "id": "s1:0002149773",
        "company": "Xiasan Dynasty Co",
        "ticker": "",
        "cik": "0002149773",
        "accession_no": "0002149773-26-000008",
        "form": "S-1",
        "stage": "Pre-pricing",
        "filed": "2026-08-31",
        "sec_url": "https://www.sec.gov/Archives/edgar/data/2149773/000214977326000008/0002149773-26-000008-index.htm",
    }


def _template_text():
    return """
        FORM S-1
        REGISTRATION STATEMENT UNDER THE SECURITIES ACT OF 1933
        XIASAN DYNASTY COMPANY
        Calculation of Filing Fee Tables
        Fees to Be Paid X X X X X X X X
        Carry Forward Securities X X X X X X X X
        SIGNATURES
        Instructions.
    """


def test_xiasan_style_bare_sec_form_is_non_substantive():
    assert gate.is_non_substantive_template_text(_template_text()) is True


def test_legitimate_early_ipo_cover_is_not_excluded_even_without_price_or_size():
    filing_text = _template_text() + """
        PROSPECTUS
        This is our initial public offering of common stock. We are offering shares
        through the underwriters. The number of shares and price have not yet been
        determined. See Risk Factors and Use of Proceeds.
    """

    assert gate.is_non_substantive_template_text(filing_text) is False


def test_long_substantive_registration_does_not_trigger_template_gate():
    filing_text = _template_text() + ("Business discussion and operating history. " * 500)

    assert gate.is_non_substantive_template_text(filing_text) is False


def test_non_substantive_sec_form_template_is_not_released_as_ipo(tmp_path, monkeypatch):
    """A bare SEC Form S-1 template is not affirmative evidence of an operating-company IPO."""
    record = _xiasan_record()
    watch_path = tmp_path / "s1_watch.json"
    queue_path = tmp_path / "filings.json"
    watch_path.write_text(json.dumps({"filings": [record]}), encoding="utf-8")
    queue_path.write_text(json.dumps({"filings": [record]}), encoding="utf-8")

    monkeypatch.setattr(gate, "_fetch_current_text", lambda row: _template_text())

    excluded = gate.apply_gate(watch_path, queue_path)

    assert excluded == {"0002149773"}
    assert json.loads(watch_path.read_text(encoding="utf-8"))["filings"] == []
    assert json.loads(queue_path.read_text(encoding="utf-8"))["filings"] == []


def test_fetch_failure_fails_open(monkeypatch):
    record = _xiasan_record()

    def _fail(row):
        raise RuntimeError("SEC unavailable")

    monkeypatch.setattr(gate, "_fetch_current_text", _fail)

    assert gate.current_registration_is_non_substantive_template(record) is False
