import os
import sys

from bs4 import BeautifulSoup

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "test test@example.com")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import s1_substantive_registration_gate as gate


def _xiasan_record():
    return {
        "company": "Xiasan Dynasty Co",
        "cik": "0002149773",
        "accession_no": "0002149773-26-000008",
        "form": "S-1",
        "stage": "Pre-pricing",
        "sec_url": (
            "https://www.sec.gov/Archives/edgar/data/2149773/"
            "000214977326000008/0002149773-26-000008-index.htm"
        ),
    }


def _template_text():
    return """
        FORM S-1
        REGISTRATION STATEMENT UNDER THE SECURITIES ACT OF 1933
        XIASAN DYNASTY COMPANY
        CALCULATION OF FILING FEE TABLES
        FEES TO BE PAID X X X X X X X X
        SIGNATURES
        Instructions.
    """


def test_release_gate_reads_typed_txt_primary_when_no_html_primary(monkeypatch):
    """SEC Type=S-1 plain-text primaries must not fall through to XBRL metadata HTML."""
    index_html = """
    <html><body>
      <table class="tableFile">
        <tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th></tr>
        <tr><td>1</td><td>FORM S1</td><td><a href="forms1new2.txt">forms1new2.txt</a></td><td>S-1</td></tr>
        <tr><td>2</td><td>FORM S1</td><td><a href="forms1new.pdf">forms1new.pdf</a></td><td>S-1</td></tr>
        <tr><td>5</td><td></td><td><a href="EXFILINGFEES.htm">EXFILINGFEES.htm</a></td><td>EX-FILING FEES</td></tr>
        <tr><td>6</td><td></td><td><a href="R1.htm">R1.htm</a></td><td>XML</td></tr>
      </table>
    </body></html>
    """
    calls = []

    def fake_fetch(url):
        calls.append(url)
        if url.endswith("-index.htm"):
            return BeautifulSoup(index_html, "lxml")
        if url.endswith("forms1new2.txt"):
            return BeautifulSoup(_template_text(), "lxml")
        raise AssertionError(f"Unexpected SEC document fetch: {url}")

    monkeypatch.setattr(gate.filing_parser, "fetch_document", fake_fetch)

    text = gate._fetch_current_text(_xiasan_record())

    assert calls[-1].endswith("forms1new2.txt")
    assert gate.is_non_substantive_template_text(text) is True
