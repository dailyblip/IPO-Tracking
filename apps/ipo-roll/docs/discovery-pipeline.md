# Private commercial SEC discovery handoff

`scripts/commercial_discovery.py` is the bounded queue between independent SEC
indexes, the isolated capture runner, and existing reviewed import contracts.
It discovers issuer/accession candidates without a company-name list. It does not
approve IPO eligibility, publish evidence, infer financial facts, execute SQL, or
modify production ingestion. Generated files belong under ignored `import-output/`.

## Implemented boundary

1. Validate raw SHA-256, byte count, canonical daily/quarterly URL, index header,
   row dates, and aware retrieval timestamps. Discover the census form set,
   including registration statements, amendments and final prospectuses. Wider
   forms unsupported by the current capture parser remain explicitly held.
2. Merge identical issuer/accession observations across overlapping daily and
   quarterly indexes. Preserve every index source version. Conflicting rows and
   joint registrants remain held. Identity never comes from company names.
3. Retain exact-filing state, registration/root identity after source capture,
   stable per-filing quarantine intake, capture attempts and reviewed handoff
   receipts. Reusing a checkpoint preserves capture progress; failed retrievals
   cannot starve untouched filings. Monitor entries are optional hints, never a
   completeness denominator or a source of automatically promoted queue records.
4. Emit a maximum four-filing request using `sec-capture-request/1`. The existing
   isolated capture runner can consume this exact request. Rebind its returned
   discovery packets only after replaying capture against retained metadata,
   registration lineage, source bytes and normalized hashes.
5. Regenerate `build_review_batch.build` from explicit source reviews and require
   exact agreement with its expected result manifest. A successful validation
   produces *prepared* private SQL and a receipt, never an applied-state claim.
   A current staging inventory is required. Existing issuers are held for explicit
   registration/version refresh because the current importer is insert-only.
6. Archive queue, index, capture and reviewed-source bytes using existing private
   `ops.sec_artifacts`, including existing chunk manifests for oversized objects.
   No new database schema, access policy, service or paid provider is needed.

An index retrieved during a US Eastern calendar day does not establish that day's
complete filings. Coverage conservatively ends on the previous date. Missing
weekdays stay incomplete; no holiday calendar is assumed. Covered index dates do
not establish a reviewed IPO census. Offering, biography, ownership, footnote and
liquidity completeness remain separate tasks. A staged exact filing is only an
observed current snapshot, not proof its research tracks are complete.

## Input and use

Private input JSON (paths relative to this JSON; traversal is rejected):

```json
{
  "version": "commercial-discovery-input/1",
  "start": "2026-09-25",
  "end": "2026-09-28",
  "as_of": "2026-09-29T12:00:00+00:00",
  "engine_baseline_commit": "<exact 40-character commit>",
  "indexes": [{
    "url": "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/master.20260928.idx",
    "sha256": "<raw SHA-256>",
    "bytes": 12345,
    "retrieved_at": "2026-09-29T12:00:00+00:00",
    "path": "indexes/20260928.idx"
  }]
}
```

```sh
python apps/ipo-roll/scripts/commercial_discovery.py \
  --input import-output/discovery/input.json \
  --previous import-output/discovery/prior/queue.json \
  --previous-sha256 CHECKPOINT_SHA256 \
  --staged import-output/discovery/staged-current-filings.json \
  --output-dir import-output/discovery/next
```

Omit both previous arguments for the initial checkpoint. `--previous-sha256`
expects the `checkpoint_sha256` field, which hashes the canonical payload before
adding that field. The archive receipt also provides `checkpoint_object_sha256`,
which hashes the complete canonical JSON bytes for restoration from
`ops.sec_artifacts`. These hashes intentionally differ. Always verify the restored
object and then the internal checkpoint before using it.

The staged inventory is a freshly read list containing `cik`, `accession_no`,
`form`, and `filing_date` for every current staged offering. Record its retrieval
time with the private batch's QA receipt. Omitting it never permits an import-ready
state. `--monitor-hints` accepts a list of exact `cik` and `accession_no` pairs;
unindexed Monitor identities remain separately listed for investigation.

The CLI produces `queue.json`, `capture-request.json` (JSON null if none pending),
stable per-filing intake JSON/SQL, `checkpoint.sql`, and `checkpoint-receipt.json`.
The checkpoint SQL archives private artifacts only. Intake SQL remains quarantined
and carries the existing review findings. Apply neither to production.

For captured files, repeat `--capture PACKET RAW_SHA256 ARCHIVE_DIRECTORY`.
Source replay emits `bound-CIK-ACCESSION.json`, suitable for existing source-review
tooling. To prepare a reviewed import, also pass:

```sh
--review CIK/ACCESSION review.json expected-result-manifest.json
```

The expected result is the single dictionary returned by
`build_review_batch.build`, not an arbitrary reviewer boolean. Its release ID
binds the full reviewed packet, passages, persons, values and private audience.
The review must use the stable discovered intake-record ID. The CLI archives the
review and manifest bytes as well as source objects. Apply the archive and intake
first, then rehearse prepared reviewed SQL inside a rollback transaction, validate
the affected research and private-report invariants, and apply/replay only the
authorized source-reviewed batch. Save the actual database receipt separately.
No saved Liquidity Analysis report is rewritten.

## Capture-runner integration

The live runner can call:

```python
queue = build_queue(input_spec, raw_indexes_by_hash, previous=prior_queue)
request = capture_request(queue, limit=4)
# Existing isolated SEC capture runs for request['filings'].
queue, bound_packet = record_capture(queue, key, packet, archive_directory)
# On a sanitized retrieval failure:
queue = record_capture_failure(queue, key, type(error).__name__)
```

Retain the complete input/index/queue/capture archive through the existing
encrypted evidence artifact and private staging persistence. The runner uses the
already authorized SEC contact in its existing environment; never expose it in
request files or logs. `record_capture` and `record_capture_failure` return a new
hash-sealed queue. A subsequent run must restore that queue to advance work. A
workflow that starts with no prior checkpoint every time is repeat capture, not
durable ongoing ingestion.

## Verification and remaining work

Synthetic tests cover independent discovery, overlapping indexes, exact replay,
source corruption, malformed input and path traversal, missing/current-day
coverage, joint registrants, unsupported forms, metadata conflicts, Monitor-only
hints, staged exact identity, retry progression, replayed captures, exact reviewed
manifest binding, held existing-issuer refresh, and private checkpoint SQL.

This module alone does not fetch a fresh index, install a recurring runner,
transfer private checkpoints between jobs, authenticate a reviewer, or execute
an import. Live retrieval/deployment/persistence receipts must be recorded in the
development ledger after verification. Existing-issuer amendment/final refresh
requires its own reviewed version-update contract before those held entries can
advance. Full management/ownership/footnote review and the complete historical
census remain unfinished even when the bounded queue works end to end.
