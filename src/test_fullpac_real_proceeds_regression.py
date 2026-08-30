import edgar_client


def test_fullpac_resale_only_proceeds_language_is_excluded():
    filing_text = """
    3,915,995 Resale Shares of Common Stock by Selling Securityholders.
    The Selling Securityholders will receive all of the proceeds from any sales
    of the shares offered hereby. We will not receive any of the proceeds, but
    we have agreed to pay the expenses of registration.
    """

    assert edgar_client.check_direct_listing_indicators(filing_text)


def test_secondary_component_in_real_ipo_is_not_excluded():
    filing_text = """
    We are offering 10,000,000 shares of common stock and the selling stockholders
    are offering 2,000,000 additional shares. We will receive the proceeds from
    the shares sold by us. We will not receive any proceeds from the sale of the
    shares by the selling stockholders.
    """

    assert not edgar_client.check_direct_listing_indicators(filing_text)
