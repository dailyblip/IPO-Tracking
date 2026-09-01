"""Normalize issuer display names without changing already-correct mixed-case names."""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

KEEP_UPPER = {"AI", "US", "USA", "UK", "LLC", "LLP", "LP", "REIT"}
BRAND_OVERRIDES = {"SPACEX": "SpaceX"}


def normalize_company_name(value: str) -> str:
    raw = " ".join(str(value or "").split())
    # SEC company-name strings can include a terminal state-of-incorporation marker
    # such as /DE/, /DE, or / DE. It is provenance metadata, not part of the issuer
    # display name.
    raw = re.sub(r"\s*/\s*[A-Z]{2}\s*/?\s*$", "", raw, flags=re.IGNORECASE).rstrip()
    if not raw or raw != raw.upper() or not re.search(r"[A-Z]", raw):
        return raw

    def convert_word(word: str) -> str:
        prefix = ""
        suffix = ""
        core = word
        while core and not core[0].isalnum():
            prefix += core[0]
            core = core[1:]
        while core and not core[-1].isalnum():
            suffix = core[-1] + suffix
            core = core[:-1]
        upper = core.upper()
        if upper in BRAND_OVERRIDES:
            converted = BRAND_OVERRIDES[upper]
        elif upper in KEEP_UPPER:
            converted = upper
        elif re.fullmatch(r"[IVXLCDM]+", upper) and len(upper) <= 5:
            converted = upper
        else:
            converted = core.lower().capitalize()
        return prefix + converted + suffix

    return " ".join(convert_word(word) for word in raw.split())


def normalize_json(path: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for filing in payload.get("filings", []):
        old = filing.get("company")
        new = normalize_company_name(old)
        if new and new != old:
            filing["company"] = new
            changed = True
    if changed:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


def normalize_csv(path: Path) -> bool:
    if not path.exists():
        return False
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []
    if not rows or "company" not in fieldnames:
        return False
    changed = False
    for row in rows:
        old = row.get("company", "")
        new = normalize_company_name(old)
        if new != old:
            row["company"] = new
            changed = True
    if changed:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    return changed


def main() -> None:
    json_path = Path(sys.argv[1] if len(sys.argv) > 1 else "../docs/data/filings.json")
    csv_path = json_path.with_suffix(".csv")
    normalize_json(json_path)
    normalize_csv(csv_path)


if __name__ == "__main__":
    main()
