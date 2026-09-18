from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

COLUMNS = [
    "detected_at",
    "type",
    "company",
    "cik",
    "filing_id",
    "form",
    "filed",
    "stage",
    "priority",
    "summary",
    "old_value",
    "new_value",
    "sec_url",
]


def _load_alerts(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    alerts = payload.get("alerts")
    if not isinstance(alerts, list):
        raise ValueError(f"{path} does not contain an alerts list")
    return alerts


def export_alerts_csv(alerts_path: Path, output_path: Path) -> int:
    alerts = _load_alerts(alerts_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for alert in alerts:
            writer.writerow({column: alert.get(column, "") for column in COLUMNS})
    tmp.replace(output_path)
    return len(alerts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export SEC Research Monitor alerts to a flat CSV.")
    parser.add_argument("--alerts", default="docs/data/alerts.json")
    parser.add_argument("--output", default="docs/data/alerts.csv")
    args = parser.parse_args()
    count = export_alerts_csv(Path(args.alerts), Path(args.output))
    print(f"Exported {count} research alert(s) to {args.output}.")


if __name__ == "__main__":
    main()
