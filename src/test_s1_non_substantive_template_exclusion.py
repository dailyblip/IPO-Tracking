import json

from bs4 import BeautifulSoup

import s1_registration_history_gate as gate


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
    }


def test_non_substantive_sec_form_template_is_not_released_as_ipo(tmp_path, monkeypatch):
    """A bare SEC Form S-1 template is not affirmative evidence of an operating-company IPO."""
    record = _xiasan_record()
    watch_path = tmp_path / "s1_watch.json"
    queue_path = tmp_path / "filings.json"
    watch_path.write_text(json.dumps({"filings": [record]}), encoding="utf-8")
    queue_path.write_text(json.dumps({"filings": [record]}), encoding="utf-8")

    monkeypatch.setattr(
        gate,
        "_recent_submission_rows",
        lambda cik: [
            {
                "accession_no": record["accession_no"],
                "form": "S-1",
                "file_number": "333-298647",
                "filing_date": record["filed"],
                "primary_document": "forms1new2.txt",
            }
        ],
    )
    filing_text = """
        FORM S-1
        REGISTRATION STATEMENT UNDER THE SECURITIES ACT OF 1933
        XIASAN DYNASTY COMPANY
        Calculation of Filing Fee Tables
        Fees to Be Paid X X X X X X X X
        Carry Forward Securities X X X X X X X X
        SIGNATURES
        Instructions.
    """
    monkeypatch.setattr(
        gate.filing_parser,
        "fetch_document",
        lambda url: BeautifulSoup(filing_text, "html.parser"),
    )

    excluded = gate.apply_gate(watch_path, queue_path)

    assert excluded == {"0002149773"}
    assert json.loads(watch_path.read_text(encoding="utf-8"))["filings"] == []
    assert json.loads(queue_path.read_text(encoding="utf-8"))["filings"] == []
