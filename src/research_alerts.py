from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ALERT_SCHEMA_VERSION = 1
STATE_SCHEMA_VERSION = 1
MAX_ALERT_HISTORY = 250


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _stage(filing: dict) -> str:
    stage = str(filing.get("stage") or "").strip().lower()
    form = str(filing.get("form") or "").upper()
    if stage:
        return stage
    if form in {"S-1", "S-1/A"}:
        return "pre-pricing"
    if form == "424B4":
        return "priced"
    return "other"


def _snapshot(filing: dict) -> dict:
    return {
        "id": filing.get("id"),
        "cik": str(filing.get("cik") or ""),
        "company": filing.get("company"),
        "form": filing.get("form"),
        "filed": filing.get("filed"),
        "stage": _stage(filing),
        "price_range": _clean(filing.get("price_range")),
        "priority": filing.get("priority"),
        "value": filing.get("value"),
        "sec_url": filing.get("sec_url"),
    }


def _priority_rank(priority: str | None) -> int:
    return {"Low": 1, "Medium": 2, "High": 3}.get(str(priority or ""), 0)


def _alert_key(alert: dict) -> str:
    parts = [
        alert.get("type") or "",
        alert.get("filing_id") or "",
        alert.get("cik") or "",
        alert.get("filed") or "",
        alert.get("new_value") or "",
    ]
    return "|".join(map(str, parts))


def _make_alert(kind: str, filing: dict, summary: str, *, old_value=None, new_value=None) -> dict:
    alert = {
        "type": kind,
        "company": filing.get("company"),
        "cik": str(filing.get("cik") or ""),
        "filing_id": filing.get("id"),
        "form": filing.get("form"),
        "filed": filing.get("filed"),
        "stage": _stage(filing),
        "priority": filing.get("priority"),
        "summary": summary,
        "sec_url": filing.get("sec_url"),
        "detected_at": _now_iso(),
    }
    if old_value is not None:
        alert["old_value"] = old_value
    if new_value is not None:
        alert["new_value"] = new_value
    alert["key"] = _alert_key(alert)
    return alert


def detect_alerts(filings: list[dict], previous_state: dict | None) -> tuple[list[dict], dict]:
    previous_state = previous_state or {}
    previous_items = previous_state.get("items", {})
    previous_ciks = previous_state.get("ciks", {})
    alerts: list[dict] = []
    current_items: dict[str, dict] = {}
    current_ciks = dict(previous_ciks)

    for filing in filings:
        filing_id = str(filing.get("id") or "")
        cik = str(filing.get("cik") or "")
        if not filing_id:
            continue

        snap = _snapshot(filing)
        current_items[filing_id] = snap
        old = previous_items.get(filing_id)
        stage = snap["stage"]

        if old is None:
            if stage == "pre-pricing":
                summary = f"New pre-pricing {filing.get('form') or 'S-1'} candidate entered the researcher queue."
                if snap.get("price_range"):
                    summary += f" Preliminary range: {snap['price_range']}."
                alerts.append(_make_alert("new_prepricing", filing, summary, new_value=snap.get("price_range")))
            elif stage == "priced":
                prior_stage = (previous_ciks.get(cik) or {}).get("stage") if cik else None
                kind = "ipo_priced" if prior_stage == "pre-pricing" else "new_424b4"
                summary = (
                    "IPO advanced from pre-pricing monitoring to a filed 424B4."
                    if kind == "ipo_priced"
                    else "New 424B4 entered the researcher queue."
                )
                alerts.append(_make_alert(kind, filing, summary, new_value=filing.get("value_label") or filing.get("value")))
        else:
            old_range = _clean(old.get("price_range"))
            new_range = snap.get("price_range")
            if stage == "pre-pricing" and old_range != new_range and new_range:
                alerts.append(_make_alert(
                    "price_range_update",
                    filing,
                    f"Preliminary IPO price range changed to {new_range}.",
                    old_value=old_range,
                    new_value=new_range,
                ))

            old_priority = old.get("priority")
            new_priority = snap.get("priority")
            if _priority_rank(new_priority) > _priority_rank(old_priority):
                alerts.append(_make_alert(
                    "priority_escalation",
                    filing,
                    f"Research priority increased from {old_priority or 'Unrated'} to {new_priority}.",
                    old_value=old_priority,
                    new_value=new_priority,
                ))

        if cik:
            prior_cik = current_ciks.get(cik, {})
            current_ciks[cik] = {
                "company": filing.get("company") or prior_cik.get("company"),
                "stage": stage,
                "last_filing_id": filing_id,
                "last_filed": filing.get("filed"),
            }

    new_state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "updated_at": _now_iso(),
        "items": current_items,
        "ciks": current_ciks,
    }
    return alerts, new_state


def merge_alert_history(existing_payload: dict | None, new_alerts: list[dict], limit: int = MAX_ALERT_HISTORY) -> dict:
    existing = list((existing_payload or {}).get("alerts", []))
    seen = {a.get("key") or _alert_key(a) for a in new_alerts}
    merged = list(new_alerts)
    for alert in existing:
        key = alert.get("key") or _alert_key(alert)
        if key in seen:
            continue
        seen.add(key)
        merged.append(alert)
    return {
        "schema_version": ALERT_SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "count": len(merged[:limit]),
        "alerts": merged[:limit],
    }


def _load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def run(feed_path: Path, alerts_path: Path, state_path: Path) -> int:
    feed = _load_json(feed_path, {})
    filings = feed.get("filings")
    if not isinstance(filings, list):
        raise ValueError(f"{feed_path} does not contain a filings list")

    state_exists = state_path.exists()
    previous_state = _load_json(state_path, {})
    existing_alerts = _load_json(alerts_path, {})
    new_alerts, new_state = detect_alerts(filings, previous_state)
    # The first production run establishes a baseline rather than treating the
    # entire existing queue as newly discovered. Subsequent runs emit deltas.
    if not state_exists:
        new_alerts = []
    merged = merge_alert_history(existing_alerts, new_alerts)
    _write_json_atomic(alerts_path, merged)
    _write_json_atomic(state_path, new_state)
    return len(new_alerts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate stateful SEC Research Monitor alerts.")
    parser.add_argument("--feed", default="docs/data/filings.json")
    parser.add_argument("--alerts", default="docs/data/alerts.json")
    parser.add_argument("--state", default="docs/data/alerts_state.json")
    args = parser.parse_args()
    count = run(Path(args.feed), Path(args.alerts), Path(args.state))
    print(f"Generated {count} new research alert(s).")


if __name__ == "__main__":
    main()
