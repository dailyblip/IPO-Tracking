import unittest
from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "docs" / "index.html").read_text(encoding="utf-8")


class DashboardPaginationTests(unittest.TestCase):
    def test_main_feed_pagination_defaults_to_25_rows(self):
        self.assertIn('id="pagination"', HTML)
        self.assertIn('id="pageSize"', HTML)
        self.assertIn('<option value="25">25</option>', HTML)
        self.assertIn('<option value="50">50</option>', HTML)
        self.assertIn('<option value="100">100</option>', HTML)
        self.assertIn('const DEFAULT_PAGE_SIZE=25', HTML)
        self.assertIn('expandedOwner=null,currentPage=1', HTML)

    def test_pagination_activates_at_feed_growth_milestone(self):
        self.assertIn('PAGINATION_MIN_ROWS=50', HTML)
        self.assertIn('function paginationEnabled(){return filings.length>=PAGINATION_MIN_ROWS}', HTML)
        self.assertIn('$("pagination").classList.toggle("hidden",!paginationEnabled())', HTML)

    def test_pagination_is_applied_after_existing_filters_and_sort(self):
        self.assertIn('const visible=visibleFilings()', HTML)
        self.assertIn('visible.slice(start,start+size)', HTML)
        self.assertIn('for(const filing of page.rows)', HTML)
        self.assertIn('Page ${currentPage} of ${page.pages}', HTML)
        self.assertIn('${page.start+1}–${pageEnd} of ${visible.length} filings', HTML)

    def test_page_controls_preserve_filter_and_sort_state_between_pages(self):
        self.assertIn('$("prevPage").addEventListener("click",()=>{if(currentPage>1){currentPage--;render()}})', HTML)
        self.assertIn('$("nextPage").addEventListener("click",()=>{currentPage++;render()})', HTML)
        self.assertIn('$("pageSize").addEventListener("change",()=>{currentPage=1;render()})', HTML)
        self.assertIn('function resetPageAndRender(){currentPage=1;render()}', HTML)
        self.assertIn('["formFilter","statusFilter","dateFilter","sizeFilter","sortBy"]', HTML)
        self.assertIn('$("search").addEventListener("input",resetPageAndRender)', HTML)

    def test_pagination_clamps_page_when_filtered_results_shrink(self):
        self.assertIn('currentPage=Math.min(Math.max(1,currentPage),pages)', HTML)
        self.assertIn('$("prevPage").disabled=currentPage<=1', HTML)
        self.assertIn('$("nextPage").disabled=currentPage>=page.pages', HTML)

    def test_year_filter_remains_deferred_until_larger_feed_milestone(self):
        self.assertNotIn('id="yearFilter"', HTML)


if __name__ == "__main__":
    unittest.main()
