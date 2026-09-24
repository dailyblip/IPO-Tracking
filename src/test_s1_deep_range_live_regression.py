from bs4 import BeautifulSoup

import filing_parser
import s1_monitor


def _soup(text: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><body><p>{text}</p></body></html>", "lxml")


def test_explicit_ipo_range_after_100k_still_drives_authoritative_midpoint_value():
    """Oura-style long S-1/A covers must not lose pricing before size derivation."""
    soup = _soup(
        ("Long SEC disclosure spacer. " * 5000)
        + "It is currently estimated that the initial public offering price per share of our common stock "
        "to the public will be between $40.00 and $44.00. "
        "Common stock offered by us 13,500,000 shares. "
        "Common stock offered by the selling stockholders 36,500,000 shares."
    )

    price_range = filing_parser.extract_price_range(soup)
    terms = filing_parser.extract_offering_terms(soup)

    assert price_range == {"range_low": 40.0, "range_high": 44.0}
    assert terms["primary_shares"] == 13_500_000
    assert terms["secondary_shares"] == 36_500_000
    assert terms["total_shares"] == 50_000_000
    assert terms["confidence"] == "High"
    assert terms["conflict"] is False

    parsed = {
        "cover_page": {
            "offering_size_shares": terms["total_shares"],
            "primary_offering_shares": terms["primary_shares"],
            "secondary_offering_shares": terms["secondary_shares"],
            "offering_size_source": terms["source"],
            "offering_size_confidence": terms["confidence"],
            "offering_size_conflict": terms["conflict"],
        }
    }
    assert s1_monitor._extract_ipo_size("", parsed, price_range) == 2_100_000_000
