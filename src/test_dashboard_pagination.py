from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "docs" / "index.html").read_text(encoding="utf-8")


def test_main_feed_pagination_defaults_to_25_rows():
    assert 'id="pagination"' in HTML
    assert 'id="pageSize"' in HTML
    assert '<option value="25">25</option>' in HTML
    assert '<option value="50">50</option>' in HTML
    assert '<option value="100">100</option>' in HTML
    assert 'const DEFAULT_PAGE_SIZE=25' in HTML
    assert 'let currentPage=1' in HTML


def test_pagination_is_applied_after_existing_filters_and_sort():
    assert 'const visible=visibleFilings()' in HTML
    assert 'visible.slice(start,start+size)' in HTML
    assert 'for(const filing of page.rows)' in HTML
    assert 'Page ${currentPage} of ${page.pages}' in HTML
    assert '${page.start+1}–${pageEnd} of ${visible.length} filings' in HTML


def test_page_controls_preserve_filter_and_sort_state_between_pages():
    assert '$("prevPage").addEventListener("click",()=>{if(currentPage>1){currentPage--;render()}})' in HTML
    assert '$("nextPage").addEventListener("click",()=>{currentPage++;render()})' in HTML
    assert '$("pageSize").addEventListener("change",()=>{currentPage=1;render()})' in HTML
    assert 'function resetPageAndRender(){currentPage=1;render()}' in HTML
    assert '["formFilter","statusFilter","dateFilter","sizeFilter","sortBy"]' in HTML
    assert '$("search").addEventListener("input",resetPageAndRender)' in HTML


def test_year_filter_remains_deferred_until_larger_feed_milestone():
    assert 'id="yearFilter"' not in HTML
