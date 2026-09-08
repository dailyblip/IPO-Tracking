from bs4 import BeautifulSoup

from pricing_date_reconciler import extract_authoritative_pricing_date


def _soup(html):
    return BeautifulSoup(html, "html.parser")


def test_rejects_conflicting_explicit_prospectus_dates():
    soup = _soup(
        """
        <html><body>
          <p>The date of this prospectus is August 18, 2026.</p>
          <p>This prospectus dated August 17, 2026 is final.</p>
        </body></html>
        """
    )

    assert extract_authoritative_pricing_date(soup, "2026-08-19") is None


def test_accepts_repeated_matching_explicit_prospectus_date():
    soup = _soup(
        """
        <html><body>
          <p>The date of this prospectus is August 18, 2026.</p>
          <p>This prospectus dated August 18, 2026 is final.</p>
        </body></html>
        """
    )

    assert extract_authoritative_pricing_date(soup, "2026-08-19") == "2026-08-18"
