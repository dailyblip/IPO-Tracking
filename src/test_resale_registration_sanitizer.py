import unittest

from bs4 import BeautifulSoup

from resale_registration_sanitizer import (
    _visible_filing_text,
    looks_like_resale_only_cover,
    sanitize_payload,
)


class ResaleRegistrationSanitizerTests(unittest.TestCase):
    def test_fullpac_style_resale_cover_with_long_ixbrl_insert_is_excluded(self):
        filing_text = (
            "SUBJECT TO COMPLETION. This prospectus relates to the offer and sale "
            + ("tagged resale share category " * 250)
            + "from time to time, by the Selling Securityholders named in this "
            "prospectus or their permitted transferees of 3,915,995 Resale Shares."
        )
        self.assertTrue(looks_like_resale_only_cover(filing_text))

    def test_hidden_ixbrl_metadata_does_not_separate_resale_cover_language(self):
        hidden_noise = "hidden tagged fact " * 3000
        soup = BeautifulSoup(
            "<html><body>"
            "<p>This prospectus relates to the proposed offer and resale or other disposition</p>"
            f"<ix:header><ix:hidden>{hidden_noise}</ix:hidden></ix:header>"
            "<p>from time to time by the selling stockholders identified in this prospectus.</p>"
            "</body></html>",
            "lxml",
        )
        filing_text = _visible_filing_text(soup)
        self.assertNotIn("hidden tagged fact", filing_text)
        self.assertTrue(looks_like_resale_only_cover(filing_text))

    def test_singular_selling_stockholder_resale_is_excluded(self):
        filing_text = """
        Preliminary Prospectus. This prospectus relates to the offer and sale from
        time to time by Streeterville Capital, LLC, a Utah limited liability company
        (the Selling Stockholder), of up to an aggregate of 22,222,200 shares of
        Common Stock issuable upon conversion of preferred stock.
        """
        self.assertTrue(looks_like_resale_only_cover(filing_text))

    def test_post_listing_selling_holder_resale_is_excluded(self):
        filing_text = """
        Our common stock began trading on the Nasdaq Capital Market under the
        symbol OBX on August 4, 2026. Common stock Offered by the Selling
        Stockholders: 29,164,045 shares of common stock. We will not receive any
        proceeds from the sale of the shares of common stock covered by this
        prospectus.
        """
        self.assertTrue(looks_like_resale_only_cover(filing_text))

    def test_obsidian_pursuant_to_prospectus_resale_wording_is_excluded(self):
        filing_text = """
        Our common stock began trading on the Nasdaq Capital Market under the
        symbol OBX on August 4, 2026. This prospectus relates to the proposed offer
        and resale or other disposition by the selling stockholders of shares of
        our common stock. We will not receive any proceeds from any sale of common
        stock by the selling stockholders pursuant to this prospectus.
        """
        self.assertTrue(looks_like_resale_only_cover(filing_text))

    def test_normal_ipo_with_secondary_shares_is_not_excluded(self):
        filing_text = """
        We are offering 10,000,000 shares of common stock and the selling
        stockholders are offering 2,000,000 shares. We will receive the proceeds
        from shares sold by us. We will not receive proceeds from shares sold by
        the selling stockholders. The shares are being offered through the
        underwriters named in this prospectus.
        """
        self.assertFalse(looks_like_resale_only_cover(filing_text))

    def test_expected_future_trading_does_not_trigger_post_listing_resale(self):
        filing_text = """
        This is our initial public offering. We expect our common stock to begin
        trading on Nasdaq after pricing. The selling stockholders are offering
        1,000,000 shares and we will not receive proceeds from shares sold by the
        selling stockholders.
        """
        self.assertFalse(looks_like_resale_only_cover(filing_text))

    def test_unrelated_late_resale_discussion_is_not_combined_with_cover_anchor(self):
        filing_text = (
            "This prospectus relates to our initial public offering of common stock. "
            + ("ordinary operating company disclosure " * 700)
            + "Selling stockholders may resell shares from time to time under a "
            "separate registration statement."
        )
        self.assertFalse(looks_like_resale_only_cover(filing_text))

    def test_sanitize_payload_removes_only_confirmed_accessions(self):
        payload = {
            "filings": [
                {"id": "resale", "accession_no": "0001", "form": "S-1/A"},
                {"id": "ipo", "accession_no": "0002", "form": "S-1"},
            ]
        }
        sanitized = sanitize_payload(payload, {"0001"})
        self.assertEqual([row["accession_no"] for row in sanitized["filings"]], ["0002"])


if __name__ == "__main__":
    unittest.main()
