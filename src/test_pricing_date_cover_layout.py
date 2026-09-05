import unittest

from bs4 import BeautifulSoup

import pricing_date_reconciler


class FinalProspectusCoverPricingDateTests(unittest.TestCase):
    def test_extracts_neutron_style_front_cover_date(self):
        soup = BeautifulSoup(
            """
            <html><body>
            <p>This is the initial public offering of our common stock.</p>
            <p>The initial public offering price is $25.00 per share of common stock.</p>
            <p>The underwriters expect to deliver the shares to purchasers on or about July 2, 2026.</p>
            <p>Goldman Sachs &amp; Co. LLC | J.P. Morgan | Jefferies</p>
            <p>June 30, 2026</p>
            <p>TABLE OF CONTENTS</p>
            </body></html>
            """,
            "html.parser",
        )

        self.assertEqual(
            pricing_date_reconciler.extract_authoritative_pricing_date(
                soup, "2026-07-02"
            ),
            "2026-06-30",
        )

    def test_extracts_scribe_style_front_cover_date(self):
        soup = BeautifulSoup(
            """
            <html><body>
            <p>PROSPECTUS</p>
            <p>This is our initial public offering of shares of common stock.</p>
            <p>The initial public offering price is $15.00 per share.</p>
            <p>The underwriters expect to deliver the shares of common stock to purchasers on or about July 27, 2026.</p>
            <p>Leerink Partners | Goldman Sachs &amp; Co. LLC</p>
            <p>July 23, 2026</p>
            <p>TABLE OF CONTENTS</p>
            </body></html>
            """,
            "html.parser",
        )

        self.assertEqual(
            pricing_date_reconciler.extract_authoritative_pricing_date(
                soup, "2026-07-27"
            ),
            "2026-07-23",
        )

    def test_front_cover_requires_ipo_price_and_delivery_structure(self):
        soup = BeautifulSoup(
            """
            <html><body>
            <p>Risk Factors</p>
            <p>June 30, 2026</p>
            <p>TABLE OF CONTENTS</p>
            </body></html>
            """,
            "html.parser",
        )

        self.assertIsNone(
            pricing_date_reconciler.extract_authoritative_pricing_date(
                soup, "2026-07-02"
            )
        )

    def test_front_cover_multiple_plausible_dates_fail_closed(self):
        soup = BeautifulSoup(
            """
            <html><body>
            <p>The initial public offering price is $25.00 per share.</p>
            <p>The underwriters expect to deliver the shares on or about July 2, 2026.</p>
            <p>June 29, 2026</p>
            <p>June 30, 2026</p>
            <p>TABLE OF CONTENTS</p>
            </body></html>
            """,
            "html.parser",
        )

        self.assertIsNone(
            pricing_date_reconciler.extract_authoritative_pricing_date(
                soup, "2026-07-02"
            )
        )

    def test_reconciler_replaces_sec_filing_date_with_front_cover_date(self):
        payload = {
            "filings": [
                {
                    "id": "neutron-final",
                    "company": "Neutron Holdings, Inc.",
                    "form": "424B4",
                    "stage": "Priced",
                    "filed": "2026-07-02",
                    "pricing_date": "2026-07-02",
                    "offering_price": 25.0,
                    "lockup_duration_value": 160,
                    "lockup_duration_unit": "days",
                    "lockup_end_date": "2026-12-09",
                }
            ]
        }
        soup = BeautifulSoup(
            """
            <html><body>
            <p>The initial public offering price is $25.00 per share.</p>
            <p>The underwriters expect to deliver the shares to purchasers on or about July 2, 2026.</p>
            <p>Goldman Sachs &amp; Co. LLC | J.P. Morgan | Jefferies</p>
            <p>June 30, 2026</p>
            <p>TABLE OF CONTENTS</p>
            </body></html>
            """,
            "html.parser",
        )

        reconciled, changed, checked, failures = pricing_date_reconciler.reconcile_payload(
            payload, soup_loader=lambda filing: soup
        )

        filing = reconciled["filings"][0]
        self.assertEqual(changed, 1)
        self.assertEqual(checked, 1)
        self.assertEqual(failures, [])
        self.assertEqual(filing["pricing_date"], "2026-06-30")
        self.assertEqual(filing["lockup_end_date"], "2026-12-07")
        self.assertIn("generated_at", reconciled)


if __name__ == "__main__":
    unittest.main()
