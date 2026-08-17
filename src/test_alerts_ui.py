from pathlib import Path


def test_alerts_page_has_core_controls():
    html = Path("docs/alerts.html").read_text(encoding="utf-8")
    assert "Research alerts" in html
    assert 'id="typeFilter"' in html
    assert 'data/alerts.json' in html
    assert "price_range_update" in html
    assert "priority_escalation" in html
    assert "ipo_priced" in html


def test_alerts_page_only_links_to_sec_hosts():
    html = Path("docs/alerts.html").read_text(encoding="utf-8")
    assert '["www.sec.gov","sec.gov"].includes(u.hostname)' in html
    assert 'rel="noopener noreferrer"' in html
