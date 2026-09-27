"""Build a private, deterministic intake from exact SEC master-index rows.

The output is quarantine-only. It never classifies an issuer, publishes research,
or writes to a database. Generated SQL is append-only and detects replay conflicts.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from build_internal_pilot import uid
from import_legacy import canonical
from prepare_sec_review import literal


VERSION = "sec-index-intake/1"
FORMS = {"S-1", "S-1/A", "F-1", "F-1/A", "424B4"}
FINDINGS = [
    "OPERATING_COMPANY_REVIEW_REQUIRED",
    "SOURCE_DOCUMENT_CAPTURE_REQUIRED",
    "ROOT_LINEAGE_UNVERIFIED",
    "COMMERCIAL_RIGHTS_REVIEW_REQUIRED",
]
ROW = re.compile(
    r"^(?P<cik>\d{1,10})\|(?P<company>[^|]{1,500})\|(?P<form>[^|]{1,20})\|"
    r"(?P<filed>\d{4}-\d{2}-\d{2})\|edgar/data/(?P=cik)/"
    r"(?P<accession>\d{10}-\d{2}-\d{6})\.txt$"
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sql_value(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return literal(value)


def insert(table, values):
    return (
        "insert into " + table + "(" + ",".join(values) + ") values(" +
        ",".join(sql_value(v) for v in values.values()) + ");"
    )


def parse_rows(raw: bytes):
    text = raw.decode("latin-1")
    rows = []
    seen = set()
    for line in text.splitlines():
        match = ROW.fullmatch(line.rstrip("\r"))
        if not match:
            continue
        data = match.groupdict()
        if data["form"] not in FORMS:
            continue
        key = data["accession"]
        if key in seen:
            raise ValueError("Duplicate SEC index accession")
        seen.add(key)
        rows.append(data | {"exact_index_row": line.rstrip("\r")})
    return rows


def build(raw: bytes, source_url: str, accessions: list[str], retrieved_at: str,
          engine_baseline_commit: str):
    if not re.fullmatch(r"https://www\.sec\.gov/Archives/edgar/full-index/\d{4}/QTR[1-4]/master\.idx", source_url):
        raise ValueError("Canonical SEC quarterly master-index URL required")
    if not re.fullmatch(r"[0-9a-f]{40}", engine_baseline_commit):
        raise ValueError("Exact engine baseline commit required")
    try:
        timestamp = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("ISO retrieval timestamp required") from exc
    if timestamp.tzinfo is None:
        raise ValueError("Retrieval timestamp must include timezone")
    if not accessions or len(accessions) != len(set(accessions)):
        raise ValueError("Unique non-empty accession selection required")
    wanted = set(accessions)
    selected = [r for r in parse_rows(raw) if r["accession"] in wanted]
    if {r["accession"] for r in selected} != wanted:
        raise ValueError("Selected accession missing from exact index")
    selected.sort(key=lambda r: (r["filed"], r["accession"]))
    input_sha = sha(raw)
    records = []
    for ordinal, row in enumerate(selected):
        values = {
            "cik": row["cik"].zfill(10),
            "form": row["form"],
            "filed": row["filed"],
            "company": row["company"],
            "accession_no": row["accession"],
        }
        pointer = source_url + "#edgar/data/" + row["cik"] + "/" + row["accession"] + ".txt"
        identity = canonical({"source_url": source_url, "exact_index_row": row["exact_index_row"]})
        record = {
            "id": uid("sec-index-record", identity),
            "status": "quarantined",
            "values": values,
            "holders": [],
            "ordinal": ordinal,
            "pointer": pointer,
            "findings": FINDINGS,
            "observations": [],
            "record_sha256": sha(identity.encode()),
            "exact_index_row": row["exact_index_row"],
        }
        records.append(record)
    seed = canonical({"version": VERSION, "input_sha256": input_sha,
                      "records": [r["record_sha256"] for r in records]})
    # One immutable ingestion run represents one exact SEC index snapshot. Several
    # bounded candidate batches may safely reference it without duplicating the run.
    run_id = uid("sec-index-run", engine_baseline_commit, input_sha)
    batch_id = uid("sec-index-batch", seed)
    payload = {
        "id": batch_id,
        "run_id": run_id,
        "records": records,
        "version": VERSION,
        "published": False,
        "source_url": source_url,
        "eligibility": "unreviewed",
        "input_sha256": input_sha,
        "retrieved_at": timestamp.isoformat(),
        "engine_baseline_commit": engine_baseline_commit,
    }
    payload["payload_sha256"] = sha(canonical(payload).encode())
    return payload


def export_sql(payload):
    body = canonical(payload)
    importer = VERSION + ":" + payload["payload_sha256"]
    tag = "$sec_index_" + payload["payload_sha256"] + "$"
    run_values = {
        "id": payload["run_id"],
        "source_commit": payload["engine_baseline_commit"],
        "input_sha256": payload["input_sha256"],
        "engine_version": "sec-index-capture/1",
        "status": "quarantined",
        "finished_at": payload["retrieved_at"],
    }
    run_insert = insert("ops.ingestion_runs", run_values).removesuffix(";") + \
        " on conflict (source_commit,input_sha256) do nothing;"
    run_check = (
        "if not exists(select 1 from ops.ingestion_runs where id=" + literal(payload["run_id"]) +
        " and source_commit=" + literal(payload["engine_baseline_commit"]) +
        " and input_sha256=" + literal(payload["input_sha256"]) +
        " and engine_version='sec-index-capture/1') then "
        "raise exception 'SEC index run identity conflict'; end if;"
    )
    stmts = [
        run_insert,
        run_check,
        insert("ops.intake_batches", {
            "id": payload["id"],
            "run_id": payload["run_id"],
            "importer_version": importer,
            "payload_sha256": payload["payload_sha256"],
            "payload": body,
            "record_count": len(payload["records"]),
        }),
    ]
    for record in payload["records"]:
        stmts.append(insert("ops.intake_records", {
            "id": record["id"],
            "batch_id": payload["id"],
            "ordinal": record["ordinal"],
            "source_pointer": record["pointer"],
            "source_record_sha256": record["record_sha256"],
            "candidate_values": canonical(record["values"]),
        }))
        for code in record["findings"]:
            stmts.append(insert("ops.quality_findings", {
                "run_id": payload["run_id"],
                "record_key": payload["id"] + ":" + str(record["ordinal"]),
                "rule_code": code,
                "reason": "Unverified SEC master-index intake: " + code,
            }))
    guard = (
        "perform pg_advisory_xact_lock(hashtextextended(" + literal(payload["id"]) + ",0));\n"
        "if exists(select 1 from ops.intake_batches where id=" + literal(payload["id"]) +
        " and payload=" + literal(body) + "::jsonb) then return; end if;\n"
        "if exists(select 1 from ops.intake_batches where id=" + literal(payload["id"]) +
        ") then raise exception 'Immutable SEC index batch conflict'; end if;"
    )
    return "do " + tag + " begin\n" + guard + "\n" + "\n".join(stmts) + "\nend " + tag + ";\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--accession", action="append", required=True)
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument("--engine-baseline-commit", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    payload = build(args.index.read_bytes(), args.source_url, args.accession,
                    args.retrieved_at, args.engine_baseline_commit)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "intake.json").write_text(json.dumps(payload, indent=2) + "\n")
    (args.output_dir / "intake.sql").write_text("begin;\n" + export_sql(payload) + "commit;\n")
    print(json.dumps({"records": len(payload["records"]), "batch_id": payload["id"],
                      "payload_sha256": payload["payload_sha256"], "published": False}, indent=2))


if __name__ == "__main__":
    main()
