import unittest

from edgar_client import check_investment_product_indicators


class InvestmentProductExclusionTests(unittest.TestCase):
    def test_explicit_non_operating_investment_products_are_excluded(self):
        cases = [
            "We are an exchange-traded fund.",
            "We are an exchange-traded note.",
            "We are a closed-end management investment company.",
            "We are an open-end management investment company.",
            "We are a unit investment trust.",
            "We are an interval fund.",
            "We are a mutual fund.",
            "We are a business development company.",
            "The trust is a grantor trust.",
            "The fund is a commodity pool.",
            "The fund is a pooled investment vehicle.",
            "We are a registered closed-end investment company under the Investment Company Act of 1940.",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertTrue(check_investment_product_indicators(text, company_name="Example Issuer"))

    def test_operating_company_risk_factor_mentions_do_not_trigger_exclusion(self):
        text = (
            "We are an operating biotechnology company. Our investors may include mutual fund "
            "managers, exchange-traded fund sponsors, and other institutional investors."
        )
        self.assertFalse(check_investment_product_indicators(text, company_name="Acme Biotherapeutics, Inc."))

    def test_explicit_etf_or_etn_issuer_name_is_excluded_without_filing_text(self):
        for company in ("Example ETF Trust", "Example ETN Notes", "Example Exchange-Traded Fund"):
            with self.subTest(company=company):
                self.assertTrue(check_investment_product_indicators("", company_name=company))


if __name__ == "__main__":
    unittest.main()
