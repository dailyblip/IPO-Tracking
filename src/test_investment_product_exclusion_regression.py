import edgar_client


def test_explicit_etf_and_etn_names_are_excluded():
    assert edgar_client.check_investment_product_indicators(
        "", company_name="Example Bitcoin ETF"
    )
    assert edgar_client.check_investment_product_indicators(
        "", company_name="Example Market ETN"
    )


def test_fund_and_trust_self_descriptions_are_excluded():
    cases = [
        "The Fund is an exchange-traded fund that seeks to track an index.",
        "The Fund is a closed-end management investment company.",
        "The Fund is an interval fund offering shares to investors.",
        "The Trust is a unit investment trust.",
        "The Trust is a grantor trust holding commodity interests.",
        "The Company is a business development company.",
    ]
    for text in cases:
        assert edgar_client.check_investment_product_indicators(text)
        assert edgar_client.check_spac_indicators(text)


def test_generic_operating_company_mentions_do_not_trigger_exclusion():
    text = (
        "Our customers include mutual funds and exchange-traded funds. "
        "We may be subject to regulations that also affect investment companies."
    )
    assert not edgar_client.check_investment_product_indicators(
        text, company_name="Example Technologies Inc."
    )


def test_trust_word_in_operating_company_name_is_not_enough():
    assert not edgar_client.check_investment_product_indicators(
        "We design and sell industrial equipment.",
        company_name="Example Trust Industries Inc.",
    )
