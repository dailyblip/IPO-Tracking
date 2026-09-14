import unittest

from public_feed_policy import qualifies_for_public_feed


class S1MidpointPublicationPolicyTests(unittest.TestCase):
    def _hometown(self, **overrides):
        filing = {
            "company": "Hometown Financial Group, Inc.",
            "form": "S-1",
            "stage": "Pre-pricing",
            "value": 600_000_000,
            "filing_price": "$10.00",
            "price_range": None,
            "primary_offering_shares": None,
            "secondary_offering_shares": None,
            "offering_size_source": (
                "SEC preliminary prospectus: explicit midpoint offering-share scenario; "
                "proposed point price"
            ),
            "offering_size_confidence": "High",
        }
        filing.update(overrides)
        return filing

    def test_verified_explicit_midpoint_total_can_publish_without_primary_share_claim(self):
        filing = self._hometown()
        self.assertTrue(qualifies_for_public_feed(filing))
        self.assertIsNone(filing["primary_offering_shares"])

    def test_midpoint_total_still_fails_closed_without_full_release_grade_provenance(self):
        self.assertFalse(
            qualifies_for_public_feed(
                self._hometown(offering_size_confidence="Medium")
            )
        )
        self.assertFalse(
            qualifies_for_public_feed(
                self._hometown(filing_price=None)
            )
        )
        self.assertFalse(
            qualifies_for_public_feed(
                self._hometown(
                    offering_size_source="explicit midpoint offering-share scenario"
                )
            )
        )
        self.assertFalse(
            qualifies_for_public_feed(
                self._hometown(
                    offering_size_source=(
                        "SEC preliminary prospectus: explicit midpoint offering-share scenario; "
                        "proposed point price; selling stockholder resale"
                    )
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
