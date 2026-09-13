from pathlib import Path


DASHBOARD = (Path(__file__).resolve().parents[1] / "docs" / "index.html").read_text(
    encoding="utf-8"
)


def test_pagination_waits_for_main_feed_milestone():
    assert "PAGINATION_MIN_ROWS=50" in DASHBOARD
    assert (
        "function paginationEnabled(){return filings.length>=PAGINATION_MIN_ROWS}"
        in DASHBOARD
    )
    assert (
        "if(!paginationEnabled()){currentPage=1;return{rows:visible,pages:1,start:0,size:visible.length}}"
        in DASHBOARD
    )
    assert '$("pagination").classList.toggle("hidden",!paginationEnabled())' in DASHBOARD


def test_milestone_pagination_keeps_locked_page_sizes():
    assert '<option value="25">25</option>' in DASHBOARD
    assert '<option value="50">50</option>' in DASHBOARD
    assert '<option value="100">100</option>' in DASHBOARD
