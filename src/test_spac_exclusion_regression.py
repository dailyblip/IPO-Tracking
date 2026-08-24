import edgar_client


def test_known_spac_franchise_names_are_excluded():
    # These names appeared in the generated S-1 feed despite the product rule
    # that SPACs must never be shown in Research Monitor.
    assert edgar_client.check_spac_indicators("", company_name="Gores Holdings XII, Inc.")
    assert edgar_client.check_spac_indicators("", company_name="GigCapital10 Corp.")


def test_operating_company_holdings_name_is_not_blanket_excluded():
    # Do not over-broaden the name heuristic: ordinary operating-company
    # 'Holdings' names are common and are not, by themselves, SPAC evidence.
    assert not edgar_client.check_spac_indicators("", company_name="Little West Holdings Inc.")
