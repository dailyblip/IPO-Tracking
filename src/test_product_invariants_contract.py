import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVARIANTS_PATH = ROOT / "PRODUCT_INVARIANTS.md"


class ProductInvariantsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = INVARIANTS_PATH.read_text(encoding="utf-8")

    def test_locked_main_queue_schema_is_current(self):
        expected = (
            "1. Company Name",
            "2. Ticker",
            "3. Form",
            "4. Stage",
            "5. Filed",
            "6. Pricing Date",
            "7. IPO Size / Offering Value",
            "8. Filing Price",
            "9. Final IPO Price",
            "10. Current Price",
            "11. Public Signals",
        )
        positions = [self.text.index(label) for label in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Public Signals remains visible in the main queue.", self.text)
        self.assertNotIn("Do not add a Public Signals / Signal column", self.text)

    def test_stanford_semantics_and_person_accordion_are_locked(self):
        self.assertIn("Stanford Cardinal red `#8C1515`", self.text)
        self.assertIn("Do not show an “S” badge/tag.", self.text)
        self.assertIn("single-open accordion", self.text)
        self.assertIn("do not restore a nested person modal", self.text)
        self.assertIn("Historical Stanford regrading/backfill from June 1, 2026", self.text)
        self.assertIn("remains required until verified complete", self.text)

    def test_lifecycle_and_scale_guardrails_are_locked(self):
        self.assertIn("A live current-price quote must never be attached to an issuer that is genuinely pre-pricing.", self.text)
        self.assertIn("Ticker/provider collisions", self.text)
        self.assertIn("roughly 50–75 records", self.text)
        self.assertIn("25 rows per page", self.text)
        self.assertIn("Around 150–200+ records, add a Year filter.", self.text)

    def test_preliminary_and_saved_ipo_roll_contract_is_locked(self):
        self.assertIn("Saved IPO Roll product direction — do not implement yet", self.text)
        self.assertIn("until the user explicitly requests the product/sellable pivot", self.text)
        self.assertIn("incrementally rather than replacing the application wholesale", self.text)
        self.assertIn("Overview, IPO Activity, Saved/Watchlist, Stanford Affiliations, and Methodology", self.text)
        self.assertIn("This saved direction must not distract from current data/pipeline work", self.text)
        self.assertNotIn("separate future product repository", self.text)
        self.assertNotIn("sellable product should be created later in a separate repository", self.text)

    def test_historical_backfill_hold_is_locked(self):
        self.assertIn("Historical April/May backfill is on hold", self.text)
        self.assertIn("until the user explicitly resumes it", self.text)
        self.assertIn("Do not run a dedicated historical backfill solely to add small/minor IPOs", self.text)

    def test_change_discipline_requires_ownership_refresh_guard(self):
        self.assertIn("Before every repository commit", self.text)
        self.assertIn("Refresh Prospect Ownership History", self.text)
        self.assertIn("neither running nor queued", self.text)


if __name__ == "__main__":
    unittest.main()
