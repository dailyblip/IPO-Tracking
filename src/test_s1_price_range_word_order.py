from bs4 import BeautifulSoup

import filing_parser
import s1_monitor


def _soup(text: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><body><p>{text}</p></body></html>", "lxml")


def test_public_offering_price_per_share_between_range_drives_midpoint_size():
    soup = _soup(
        "The initial public offering price per share will be between $20.00 and $24.00. "
        "Common stock offered by us 8,635,165 shares. "
        "Common stock offered by the selling stockholders 21,364,835 shares."
    )

    price_range = filing_parser.extract_price_range(soup)
    terms = filing_parser.extract_offering_terms(soup)

    assert price_range == {"range_low": 20.0, "range_high": 24.0}
    assert terms["primary_shares"] == 8_635_165
    assert terms["secondary_shares"] == 21_364_835
    assert terms["total_shares"] == 30_000_000
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
    assert s1_monitor._extract_ipo_size("", parsed, price_range) == 660_000_000


def test_public_offering_price_between_range_variant_is_supported():
    soup = _soup(
        "We estimate the public offering price per share to be between $40.00 and $44.00."
    )
    assert filing_parser.extract_price_range(soup) == {
        "range_low": 40.0,
        "range_high": 44.0,
    }


def test_explicit_ipo_range_beyond_legacy_cover_window_drives_midpoint_size():
    soup = _soup(
        ("Cover disclosure spacer. " * 1800)
        + "It is currently estimated that the initial public offering price per share of common stock "
        "will be between $40.00 and $44.00. "
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


def test_unrelated_between_per_share_range_stays_blank():
    soup = _soup("The conversion price per share will be between $20.00 and $24.00.")
    assert filing_parser.extract_price_range(soup) == {
        "range_low": None,
        "range_high": None,
    }


def test_legacy_range_word_order_remains_supported():
    soup = _soup("We expect a price range of $14.00 and $16.00 per share.")
    assert filing_parser.extract_price_range(soup) == {
        "range_low": 14.0,
        "range_high": 16.0,
    }
