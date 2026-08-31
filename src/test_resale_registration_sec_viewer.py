import unittest
from unittest import mock

from bs4 import BeautifulSoup

import resale_registration_sanitizer as sanitizer


class ResaleRegistrationSecViewerTests(unittest.TestCase):
    def test_unwraps_current_sec_ix_viewer_url(self):
        viewer = (
            "https://www.sec.gov/ix?doc=%2FArchives%2Fedgar%2Fdata%2F2111846%2F"
            "000121390026092695%2Fea0302929-s1_game.htm"
        )
        self.assertEqual(
            sanitizer._raw_sec_document_url(viewer),
            "https://www.sec.gov/Archives/edgar/data/2111846/"
            "000121390026092695/ea0302929-s1_game.htm",
        )

    def test_unwraps_legacy_sec_ixviewer_url(self):
        viewer = (
            "https://www.sec.gov/ixviewer/doc/action?doc=/Archives/edgar/data/2111846/"
            "000121390026092695/ea0302929-s1_game.htm"
        )
        self.assertEqual(
            sanitizer._raw_sec_document_url(viewer),
            "https://www.sec.gov/Archives/edgar/data/2111846/"
            "000121390026092695/ea0302929-s1_game.htm",
        )

    def test_does_not_rewrite_non_sec_or_non_archive_targets(self):
        raw = "https://www.sec.gov/Archives/edgar/data/1/doc.htm"
        self.assertEqual(sanitizer._raw_sec_document_url(raw), raw)
        foreign = "https://example.com/ix?doc=/Archives/edgar/data/1/doc.htm"
        self.assertEqual(sanitizer._raw_sec_document_url(foreign), foreign)
        unsafe = "https://www.sec.gov/ix?doc=https://example.com/doc.htm"
        self.assertEqual(sanitizer._raw_sec_document_url(unsafe), unsafe)

    def test_fetch_filing_text_uses_underlying_document_for_resale_classifier(self):
        index_url = "https://www.sec.gov/Archives/edgar/data/2111846/index.htm"
        viewer_url = (
            "https://www.sec.gov/ix?doc=/Archives/edgar/data/2111846/"
            "000121390026092695/ea0302929-s1_game.htm"
        )
        raw_url = (
            "https://www.sec.gov/Archives/edgar/data/2111846/"
            "000121390026092695/ea0302929-s1_game.htm"
        )
        soup = BeautifulSoup(
            "<html><body>This prospectus relates to the offer and sale from time to time "
            "by Streeterville Capital, LLC, the Selling Stockholder, of shares of Common "
            "Stock.</body></html>",
            "html.parser",
        )
        with (
            mock.patch.object(
                sanitizer.filing_parser,
                "find_primary_document_url",
                return_value=viewer_url,
            ),
            mock.patch.object(
                sanitizer.filing_parser,
                "fetch_document",
                return_value=soup,
            ) as fetch_document,
        ):
            text = sanitizer._fetch_filing_text({"sec_url": index_url})

        fetch_document.assert_called_once_with(raw_url)
        self.assertTrue(sanitizer.looks_like_resale_only_cover(text))


if __name__ == "__main__":
    unittest.main()
