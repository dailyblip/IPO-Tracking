import csv
import json
from pathlib import Path

from alerts_csv import COLUMNS, export_alerts_csv


def test_export_alerts_csv(tmp_path: Path):
    alerts_path = tmp_path / "alerts.json"
    output_path = tmp_path / "alerts.csv"
    alerts_path.write_text(json.dumps({
        "schema_version": 1,
        "alerts": [
            {
                "detected_at": "2026-08-17T12:00:00+00:00",
                "type": "price_range_update",
                "company": "Example Corp",
                "cik": "1234567",
                "filing_id": "s1:1234567",
                "form": "S-1/A",
                "filed": "2026-08-17",
                "stage": "pre-pricing",
                "priority": "High",
                "summary": "Preliminary IPO price range changed to $18-$20.",
                "old_value": "$16-$18",
                "new_value": "$18-$20",
                "sec_url": "https://www.sec.gov/Archives/example",
                "key": "ignored-in-flat-export",
            }
        ]
    }), encoding="utf-8")

    count = export_alerts_csv(alerts_path, output_path)
    assert count == 1

    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["company"] == "Example Corp"
    assert rows[0]["type"] == "price_range_update"
    assert rows[0]["new_value"] == "$18-$20"
    assert list(rows[0]) == COLUMNS


def test_export_empty_alerts_still_writes_header(tmp_path: Path):
    alerts_path = tmp_path / "alerts.json"
    output_path = tmp_path / "alerts.csv"
    alerts_path.write_text(json.dumps({"schema_version": 1, "alerts": []}), encoding="utf-8")

    assert export_alerts_csv(alerts_path, output_path) == 0
    assert output_path.read_text(encoding="utf-8").splitlines()[0] == ",".join(COLUMNS)
