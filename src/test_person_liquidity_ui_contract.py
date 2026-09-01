import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "index.html"


class PersonLiquidityUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")

    def test_person_accordion_suppresses_unknown_liquidity_labels(self):
        """Do not render repetitive Unknown liquidity status/confidence text."""
        self.assertIn("function buildPersonAccordion(person,filing)", self.html)
        self.assertIn(
            'function supportedLiquidityStatus(value){const status=String(value||"").trim();return status&&!(["unknown","unclassified"].includes(status.toLowerCase()))?status:null}',
            self.html,
        )
        self.assertIn(
            'Number.isFinite(shares)&&shares>0?(supportedLiquidityStatus(person.liquidity_status)||"Holding details"):"Company affiliation"',
            self.html,
        )
        self.assertNotIn(
            'Number.isFinite(shares)&&shares>0?(person.liquidity_status||"Holding details"):"Company affiliation"',
            self.html,
        )
        self.assertIn(
            'const status=supportedLiquidityStatus(person.liquidity_status);if(status)',
            self.html,
        )
        self.assertIn(
            'if(confidence&&!confidence.toLowerCase().startsWith("unknown"))',
            self.html,
        )
        self.assertIn(
            "No additional filing-supported liquidity details are available for this person.",
            self.html,
        )

    def test_person_accordion_only_renders_supported_money_metrics(self):
        """Liquidity dollar fields require positive, explicit numeric support."""
        self.assertIn(
            "function supportedMoney(value){const n=Number(value);return Number.isFinite(n)&&n>0?money(n):null}",
            self.html,
        )
        for label in (
            "Current holding value",
            "Value at IPO price",
            "Cash realized at IPO",
            "Estimated liquid now",
            "Locked / restricted",
        ):
            self.assertIn(label, self.html)
        self.assertIn("if(value)facts.append(personFact(label,value))", self.html)


if __name__ == "__main__":
    unittest.main()