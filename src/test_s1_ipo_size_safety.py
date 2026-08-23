from s1_monitor import _extract_ipo_size


def test_registration_fee_amount_cannot_override_cover_terms():
    filing_text = (
        "Calculation of Filing Fee Table Proposed Maximum Aggregate Offering Price "
        "$11,143.00. This is an initial public offering."
    )
    parsed = {
        "cover_page": {
            "offering_size_shares": 3_000_000,
            "offering_size_confidence": "High",
            "offering_size_conflict": False,
            "offering_price": 5.50,
        }
    }
    price_range = {"range_low": 5.00, "range_high": 6.00}

    assert _extract_ipo_size(filing_text, parsed, price_range) == 16_500_000


def test_unresolved_or_medium_share_count_is_not_published():
    parsed = {
        "cover_page": {
            "offering_size_shares": 3_000_000,
            "offering_size_confidence": "Medium",
            "offering_size_conflict": False,
            "offering_price": 5.50,
        }
    }

    assert _extract_ipo_size("", parsed, {}) is None


def test_conflicting_share_count_is_not_published():
    parsed = {
        "cover_page": {
            "offering_size_shares": 3_000_000,
            "offering_size_confidence": "High",
            "offering_size_conflict": True,
            "offering_price": 5.50,
        }
    }

    assert _extract_ipo_size("", parsed, {}) is None
