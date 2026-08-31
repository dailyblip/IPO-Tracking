import unittest

from resale_registration_sanitizer import looks_like_resale_only_cover, sanitize_payload


class ResaleRegistrationSanitizerTests(unittest.TestCase):
    def test_fullpac_style_resale_cover_with_long_ixbrl_insert_is_excluded(self):
        filing_text = (
            "SUBJECT TO COMPLETION. This prospectus relates to the offer and sale "
            + ("tagged resale share category " * 250)
            + "from time to time, by the Selling Securityholders named in this "
            "prospectus or their permitted transferees of 3,915,995 Resale Shares."
        )
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
