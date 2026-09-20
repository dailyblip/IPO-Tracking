import json
import math
import unittest
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "filings.json"
MARKET_VALUE_SIGNAL_PREFIX = "Largest named holding currently valued at approximately "


def _number(value):
    if value in (None, "", "—"):
        return None
    try:
        number = float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _money(value):
    value = _number(value)
    if value is None or value <= 0:
        return "—"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


class PublicMarketValueSignalIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        cls.filings = payload.get("filings", []) if isinstance(payload, dict) else payload

    def test_largest_named_holding_signal_matches_current_public_people(self):
        """Quote-derived holder signals must not outlive the sanitized person values behind them."""
        failures = []
        checked = 0

        for filing in self.filings:
            label = filing.get("company") or filing.get("id") or "unknown filing"
            signals = filing.get("signals") if isinstance(filing.get("signals"), list) else []
            market_value_signals = [
                str(signal).strip()
                for signal in signals
                if str(signal).strip().startswith(MARKET_VALUE_SIGNAL_PREFIX)
            ]
            if not market_value_signals:
                continue

            checked += 1
            if len(market_value_signals) != 1:
                failures.append(
                    f"{label}: expected one largest-holding market-value signal, found {len(market_value_signals)}"
                )
                continue

            people = filing.get("people") if isinstance(filing.get("people"), list) else []
            values = []
            for person in people:
                if not isinstance(person, dict):
                    continue
                value = _number(person.get("cash_value"))
                if value is not None and value > 0:
                    values.append(value)

            if not values:
                failures.append(
                    f"{label}: market-value signal is published but no person has a supported positive cash_value"
                )
                continue

            expected = MARKET_VALUE_SIGNAL_PREFIX + _money(max(values))
            actual = market_value_signals[0]
            if actual != expected:
                failures.append(
                    f"{label}: stale/mismatched market-value signal {actual!r}; expected {expected!r} "
                    "from the current public person data"
                )

        self.assertGreater(checked, 0, "No published largest-holding market-value signals were available to validate")
        self.assertEqual(
            failures,
            [],
            "Published holder market-value signal integrity failures: " + "; ".join(failures[:10]),
        )


if __name__ == "__main__":
    unittest.main()
