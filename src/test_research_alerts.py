import unittest
from unittest.mock import patch

from research_alerts import detect_alerts, merge_alert_history


class ResearchAlertsTests(unittest.TestCase):
    def filing(self, **overrides):
        row = {
            "id": "s1:0001234567",
            "company": "Acme Biotech, Inc.",
            "cik": "0001234567",
            "form": "S-1",
            "filed": "2026-08-17",
            "stage": "pre-pricing",
            "price_range": None,
            "priority": "Medium",
            "sec_url": "https://www.sec.gov/example",
        }
        row.update(overrides)
        return row

    @patch("research_alerts._now_iso", return_value="2026-08-17T20:00:00+00:00")
    def test_new_prepricing_alert(self, _):
        alerts, state = detect_alerts([self.filing(price_range="$15-$17")], {})
        self.assertEqual(alerts[0]["type"], "new_prepricing")
        self.assertEqual(alerts[0]["new_value"], "$15-$17")
        self.assertEqual(state["items"]["s1:0001234567"]["stage"], "pre-pricing")

    @patch("research_alerts._now_iso", return_value="2026-08-17T20:00:00+00:00")
    def test_price_range_change_alert(self, _):
        old_state = {
            "items": {"s1:0001234567": self.filing(price_range="$14-$16")},
            "ciks": {"0001234567": {"stage": "pre-pricing"}},
        }
        alerts, _ = detect_alerts([self.filing(form="S-1/A", price_range="$15-$17")], old_state)
        self.assertEqual([a["type"] for a in alerts], ["price_range_update"])
        self.assertEqual(alerts[0]["old_value"], "$14-$16")

    @patch("research_alerts._now_iso", return_value="2026-08-17T20:00:00+00:00")
    def test_priced_transition_uses_cik_history(self, _):
        old_state = {
            "items": {"s1:0001234567": self.filing()},
            "ciks": {"0001234567": {"stage": "pre-pricing"}},
        }
        priced = self.filing(
            id="0001234567-26-000099",
            form="424B4",
            stage="priced",
            value=125000000,
            value_label="$125M",
        )
        alerts, state = detect_alerts([priced], old_state)
        self.assertEqual(alerts[0]["type"], "ipo_priced")
        self.assertEqual(state["ciks"]["0001234567"]["stage"], "priced")

    @patch("research_alerts._now_iso", return_value="2026-08-17T20:00:00+00:00")
    def test_priority_escalation_only_moves_up(self, _):
        old = self.filing(priority="Low")
        old_state = {"items": {old["id"]: old}, "ciks": {}}
        alerts, _ = detect_alerts([self.filing(priority="High")], old_state)
        self.assertEqual([a["type"] for a in alerts], ["priority_escalation"])

        old_high = self.filing(priority="High")
        state_high = {"items": {old_high["id"]: old_high}, "ciks": {}}
        alerts, _ = detect_alerts([self.filing(priority="Medium")], state_high)
        self.assertEqual(alerts, [])

    @patch("research_alerts._now_iso", return_value="2026-08-17T20:00:00+00:00")
    def test_alert_history_deduplicates(self, _):
        new = {
            "type": "new_prepricing",
            "filing_id": "s1:1",
            "cik": "1",
            "filed": "2026-08-17",
            "new_value": "$10-$12",
            "key": "same",
        }
        old = {"alerts": [{**new, "summary": "older", "key": "same"}, {"key": "other"}]}
        payload = merge_alert_history(old, [new])
        self.assertEqual([a["key"] for a in payload["alerts"]], ["same", "other"])


if __name__ == "__main__":
    unittest.main()
