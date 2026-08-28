"""Validate the public Research Monitor feed against its versioned JSON Schema."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"


def schema_path_for_version(version: int) -> Path:
    return SCHEMA_DIR / f"filings-v{version}.schema.json"


def load_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema(version: int) -> dict:
    path = schema_path_for_version(version)
    if not path.exists():
        raise ValueError(
            f"No public-feed schema is registered for schema_version={version}. "
            "Add a new versioned schema before publishing a breaking feed change."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def validate_payload(payload: dict) -> list[str]:
    version = payload.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        return ["schema_version must be an integer"]
    try:
        schema = load_schema(version)
    except ValueError as exc:
        return [str(exc)]

    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        location = "$"
        for part in error.absolute_path:
            location += f"[{part}]" if isinstance(part, int) else f".{part}"
        errors.append(f"{location}: {error.message}")
    return errors


def validate_file(path: str | Path) -> list[str]:
    path = Path(path)
    try:
        payload = load_payload(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Unable to read feed JSON: {exc}"]
    return validate_payload(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "feed",
        nargs="?",
        default=str(ROOT / "docs" / "data" / "filings.json"),
        help="Path to the public filings JSON feed",
    )
    args = parser.parse_args()

    failures = validate_file(args.feed)
    if failures:
        raise SystemExit("Public feed schema validation failed:\n- " + "\n- ".join(failures))

    payload = load_payload(Path(args.feed))
    print(
        f"Public feed schema v{payload['schema_version']} valid: "
        f"{len(payload.get('filings', []))} filing(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
