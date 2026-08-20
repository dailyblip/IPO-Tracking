from pathlib import Path

p = Path('src/test_prospect_liquidity_site.py')
s = p.read_text(encoding='utf-8')
marker = r'''\n\nclass ProspectResearchGradeRegressionTests(unittest.TestCase):\n    def test_research_grade_feature_regression_contract(self):\n        from pathlib import Path\n        html=(Path(__file__).parents[1]/"docs/prospect-research/index.html").read_text(encoding="utf-8")\n        for required in (\n            'id="clearFilters"', 'id="companySignals"', 'id="companySecSource"',\n            'id="personResearchContext"', 'id="personLockupSchedule"',\n            'Stanford connection', '$500M+ IPO', 'Selling shareholders',\n            'Before IPO', 'Sold in IPO', 'IPO Cash Proceeds', 'Current Value',\n            'Liquid Now', 'Locked / Restricted', 'Classification confidence',\n        ):\n            self.assertIn(required, html)\n'''
replacement = '''\n\nclass ProspectResearchGradeRegressionTests(unittest.TestCase):\n    def test_research_grade_feature_regression_contract(self):\n        from pathlib import Path\n        html=(Path(__file__).parents[1]/"docs/prospect-research/index.html").read_text(encoding="utf-8")\n        for required in (\n            'id="clearFilters"', 'id="companySignals"', 'id="companySecSource"',\n            'id="personResearchContext"', 'id="personLockupSchedule"',\n            'Stanford connection', '$500M+ IPO', 'Selling shareholders',\n            'Before IPO', 'Sold in IPO', 'IPO Cash Proceeds', 'Current Value',\n            'Liquid Now', 'Locked / Restricted', 'Classification confidence',\n        ):\n            self.assertIn(required, html)\n'''
if marker in s:
    s = s.replace(marker, replacement, 1)
p.write_text(s, encoding='utf-8')
