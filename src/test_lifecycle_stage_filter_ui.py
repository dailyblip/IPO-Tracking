import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "index.html"


class LifecycleStageFilterUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")

    def test_stage_filter_exposes_priced_and_prepricing_views(self):
        self.assertIn('id="stageFilter"', self.html)
        self.assertIn('<option value="">All stages</option>', self.html)
        self.assertIn('<option value="Priced">Priced</option>', self.html)
        self.assertIn('<option value="Pre-pricing">Pre-pricing</option>', self.html)

    def test_stage_filter_uses_authoritative_stage_field(self):
        self.assertIn('stage=$("stageFilter").value', self.html)
        self.assertIn('(!stage||f.stage===stage)', self.html)
        self.assertIn('$("stageFilter").addEventListener("change",render)', self.html)

    def test_clear_filters_resets_stage_filter(self):
        self.assertIn('$("stageFilter").value=""', self.html)
        self.assertIn('$("sizeFilter").value=""', self.html)
        self.assertIn('$("statusFilter").value=""', self.html)


if __name__ == "__main__":
    unittest.main()
