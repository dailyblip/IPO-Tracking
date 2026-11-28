"""Private, offline SEC discovery queue and reviewed-import handoff.

Index rows discover candidates, never eligible IPOs or financial facts. The CLI
emits bounded capture requests and append-only private checkpoint SQL; it has no
network or database credentials and never executes an import.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timedelta
import gzip
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from build_internal_pilot import uid
from build_review_batch import build as build_review, plan_artifact_archive
from build_sec_index_intake import ROW, FINDINGS, export_sql
from capture_sec_evidence import Archive, FORMS as CAPTURE_FORMS, capture
from import_legacy import canonical
from reconcile_sec_census import FORMS

VERSION = 'commercial-discovery/1'
INDEX_URL = re.compile(r'https://www\.sec\.gov/Archives/edgar/(?P<kind>full|daily)-index/'
                       r'(?P<year>\d{4})/QTR(?P<quarter>[1-4])/master'
                       r'(?:\.(?P<day>\d{8}))?\.idx')
NY = ZoneInfo('America/New_York')
# Daily dissemination indexes use compact YYYYMMDD; quarterly masters use ISO.
# Preserve the literal row while normalizing only its parsed filing-date field.
DAILY_ROW = re.compile(ROW.pattern.replace(r'\d{4}-\d{2}-\d{2}', r'\d{8}'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def timestamp(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Timezone-aware timestamp required')
    return stamp


def identity(cik, accession):
    if not re.fullmatch(r'\d{10}', cik) or not re.fullmatch(r'\d{10}-\d{2}-\d{6}', accession):
        raise ValueError('Exact CIK/accession identity required')
    return cik + '/' + accession


def seal(payload):
    payload = deepcopy(payload)
    payload.pop('checkpoint_sha256', None)
    payload['checkpoint_sha256'] = sha(canonical(payload).encode())
    return payload


def validate_checkpoint(payload, expected=None):
    checksum = payload.get('checkpoint_sha256')
    if payload.get('version') != VERSION or seal(payload)['checkpoint_sha256'] != checksum:
        raise ValueError('Discovery checkpoint hash/version mismatch')
    if expected is not None and checksum != expected:
        raise ValueError('Unexpected prior checkpoint hash')
    if payload.get('publication_allowed') is not False:
        raise ValueError('Discovery checkpoint must stay private')


def parse_artifact(spec, raw, as_of):
    match = INDEX_URL.fullmatch(spec['url'])
    if not match or ((match['kind'] == 'daily') != bool(match['day'])):
        raise ValueError('Canonical quarterly or dated daily SEC index required')
    if sha(raw) != spec['sha256'] or len(raw) != spec['bytes']:
        raise ValueError('SEC index hash/length mismatch')
    retrieved = timestamp(spec['retrieved_at'])
    if retrieved > as_of:
        raise ValueError('Index retrieval is later than observation time')
    year, quarter = int(match['year']), int(match['quarter'])
    first = date(year, 3 * quarter - 2, 1)
    last = date(year + (quarter == 4), 1 if quarter == 4 else 3 * quarter + 1, 1) - timedelta(days=1)
    # Retrieval is not proof the current trading day's index is complete.
    available_through = retrieved.astimezone(NY).date() - timedelta(days=1)
    if match['day']:
        day = datetime.strptime(match['day'], '%Y%m%d').date()
        if not first <= day <= last or day > retrieved.astimezone(NY).date():
            raise ValueError('Daily index date/quarter/retrieval conflict')
        first = last = day
    complete_last = min(last, available_through)
    text = raw.decode('latin-1')
    if not any(header in text.splitlines() for header in (
            'CIK|Company Name|Form Type|Date Filed|Filename',
            'CIK|Company Name|Form Type|Date Filed|File Name')):
        raise ValueError('Missing SEC master-index header')
    rows, seen, outside, duplicate_rows = [], set(), Counter(), 0
    for line in text.splitlines():
        match_row = ROW.fullmatch(line)
        if not match_row and match['kind'] == 'daily':
            match_row = DAILY_ROW.fullmatch(line)
        if not match_row:
            if re.match(r'^\d+\|', line):
                raise ValueError('Malformed SEC index data row')
            continue
        row = match_row.groupdict()
        if len(row['filed']) == 8:
            row['filed'] = datetime.strptime(row['filed'], '%Y%m%d').date().isoformat()
        filed = date.fromisoformat(row['filed'])
        # Daily dissemination can include older filings released/corrected today.
        # Their actual filing date must not be rewritten to the index date.
        if (filed > last or filed > retrieved.astimezone(NY).date() or
                (match['kind'] == 'full' and filed < first)):
            raise ValueError('SEC row outside index date or retrieval cutoff')
        key = identity(row['cik'].zfill(10), row['accession'])
        if line in seen:
            duplicate_rows += 1
            continue
        seen.add(line)
        if row['form'] not in FORMS:
            outside[row['form']] += 1
            continue
        rows.append(dict(row, cik=row['cik'].zfill(10), exact_index_row=line))
    evidence = {k: spec[k] for k in ('url', 'sha256', 'bytes', 'retrieved_at')}
    evidence.update(covered_from=first.isoformat(), covered_through=complete_last.isoformat(),
                    current_day_complete=False, identical_duplicate_rows=duplicate_rows)
    return rows, evidence, outside


def intake_for(entry, engine_commit):
    """Stable per-filing intake. Re-observation does not create duplicate records."""
    row, source = entry['index_row'], entry['first_source']
    key = identity(row['cik'], row['accession'])
    values = dict(cik=row['cik'], accession_no=row['accession'], form=row['form'],
                  filed=row['filed'], company=row['company'])
    record_hash = sha(canonical(values).encode())
    record = dict(id=uid('commercial-discovery-record', key), status='quarantined',
                  values=values, holders=[], ordinal=0, findings=FINDINGS,
                  observations=[], record_sha256=record_hash,
                  pointer=source['url'] + '#edgar/data/' + str(int(row['cik'])) + '/' + row['accession'] + '.txt',
                  exact_index_row=row['exact_index_row'])
    payload = dict(version='sec-index-intake/1', id=uid('commercial-discovery-intake', key),
                   run_id=uid('sec-index-run', engine_commit, source['sha256']),
                   records=[record], published=False, eligibility='unreviewed',
                   source_url=source['url'], input_sha256=source['sha256'],
                   retrieved_at=source['retrieved_at'], engine_baseline_commit=engine_commit)
    payload['payload_sha256'] = sha(canonical(payload).encode())
    return payload


def build_queue(spec, artifacts_by_sha, previous=None, staged=None, monitor_hints=None):
    if spec.get('version') != 'commercial-discovery-input/1':
        raise ValueError('Unsupported discovery input version')
    start, end = date.fromisoformat(spec['start']), date.fromisoformat(spec['end'])
    as_of = timestamp(spec['as_of'])
    if start > end or end > as_of.astimezone(NY).date():
        raise ValueError('Invalid or future discovery interval')
    engine = spec['engine_baseline_commit']
    if not re.fullmatch(r'[a-f0-9]{40}', engine):
        raise ValueError('Exact engine baseline commit required')
    entries, sources, coverage, outside = {}, {}, set(), Counter()
    if previous:
        validate_checkpoint(previous)
        if timestamp(previous['as_of']) > as_of:
            raise ValueError('Checkpoint time cannot move backwards')
        for entry in previous['entries']:
            key = identity(entry['cik'], entry['accession'])
            if key in entries or key != entry['key']:
                raise ValueError('Duplicate or mismatched prior queue identity')
            entries[key] = deepcopy(entry)
            # Readiness must be revalidated from source/review bytes each run.
            entries[key].pop('handoff', None)
            entries[key]['status'] = ('captured_review_pending' if entry.get('capture')
                                      else 'capture_pending')
        sources = {canonical(s): s for s in previous['index_sources']}
    for artifact in spec['indexes']:
        rows, evidence, other = parse_artifact(artifact, artifacts_by_sha[artifact['sha256']], as_of)
        sources[canonical(evidence)] = evidence
        outside.update(other)
        for row in rows:
            daily_observation = '/daily-index/' in evidence['url'] and spec['start'] <= evidence['covered_from'] <= spec['end']
            if not daily_observation and not spec['start'] <= row['filed'] <= spec['end']:
                continue
            key = identity(row['cik'], row['accession'])
            if key not in entries:
                entry = dict(key=key, cik=row['cik'], accession=row['accession'],
                             form=row['form'], filed=row['filed'], index_row=row,
                             first_source={k: evidence[k] for k in ('url', 'sha256', 'bytes', 'retrieved_at')},
                             observations=[], hold_reasons=[], status='capture_pending',
                             registration_file_number=None, root_accession=None,
                             eligibility='unreviewed', fact_refresh='unverified', capture_attempts=0)
                entry['intake'] = intake_for(entry, engine)
                entries[key] = entry
            entry = entries[key]
            if row['filed'] < '2026-01-01':
                entry['hold_reasons'].append('earlier_filing_requires_2026_activity_review')
            observed = dict(index_sha256=evidence['sha256'], index_url=evidence['url'],
                            row_sha256=sha(row['exact_index_row'].encode()))
            if observed not in entry['observations']:
                entry['observations'].append(observed)
            if ({k: v for k, v in row.items() if k != 'exact_index_row'} !=
                    {k: v for k, v in entry['index_row'].items() if k != 'exact_index_row'}):
                entry['hold_reasons'].append('conflicting_index_rows')
    # Quarter snapshots and dated daily snapshots may overlap. Identical rows
    # coalesce, while each different source hash remains visible in provenance.
    for evidence in sources.values():
        day, last = max(start, date.fromisoformat(evidence['covered_from'])), min(end, date.fromisoformat(evidence['covered_through']))
        while day <= last:
            coverage.add(day.isoformat())
            day += timedelta(days=1)
    observed_staged, issuer_set = {}, set()
    for row in staged or []:
        key = identity(row['cik'].zfill(10), row['accession_no'])
        if key in observed_staged:
            raise ValueError('Duplicate staged filing identity')
        observed_staged[key] = row
        issuer_set.add(row['cik'].zfill(10))
    hints = {identity(r['cik'].zfill(10), r['accession_no']) for r in monitor_hints or []}
    accession_issuers = {}
    for entry in entries.values():
        accession_issuers.setdefault(entry['accession'], set()).add(entry['cik'])
    for key, entry in entries.items():
        entry['monitor_hint'] = key in hints
        entry['existing_issuer'] = entry.get('existing_issuer', False) or entry['cik'] in issuer_set
        entry['staging_inventory_checked'] = staged is not None
        entry['staged_current_snapshot'] = False
        if entry['form'] not in CAPTURE_FORMS:
            entry['hold_reasons'].append('form_requires_extended_capture_review')
        if len(accession_issuers[entry['accession']]) > 1:
            entry['hold_reasons'].append('joint_registrants_require_issuer_review')
        if key in observed_staged:
            staged_row = observed_staged[key]
            if (staged_row.get('form') != entry['form'] or
                    staged_row.get('filing_date') != entry['filed']):
                entry['hold_reasons'].append('staged_metadata_conflict_or_missing')
            else:
                entry['staged_current_snapshot'] = True
                entry['status'] = 'staged_snapshot_observed'
        entry['hold_reasons'] = sorted(set(entry['hold_reasons']))
        entry['observations'].sort(key=canonical)
        if entry['hold_reasons']:
            entry['status'] = 'held'
    expected = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            expected.append(day.isoformat())
        day += timedelta(days=1)
    missing = [day for day in expected if day not in coverage]
    ordered = sorted(entries.values(), key=lambda e: (e['filed'], e['cik'], e['accession']))
    return seal(dict(version=VERSION, start=spec['start'], end=spec['end'], as_of=spec['as_of'],
                     engine_baseline_commit=engine, publication_allowed=False,
                     previous_checkpoint_sha256=previous['checkpoint_sha256'] if previous else None,
                     index_sources=sorted(sources.values(), key=canonical), entries=ordered,
                     coverage=dict(status='incomplete' if missing else 'index_interval_covered',
                                   missing_weekdays=missing, holiday_calendar_verified=False,
                                   complete_ipo_census=False,
                                   latest_retrieved_at=max((s['retrieved_at'] for s in sources.values()), key=timestamp, default=None)),
                     outside_scope_forms=dict(sorted(outside.items())),
                     monitor_only_identities=sorted(hints - set(entries))))


def capture_request(queue, limit=4):
    validate_checkpoint(queue)
    if not 1 <= limit <= 4:
        raise ValueError('Capture budget is one to four filings')
    # Failed retrievals cannot indefinitely starve untouched filings.
    pending = sorted((e for e in queue['entries'] if e['status'] == 'capture_pending'),
                     key=lambda e: (e.get('capture_attempts', 0), e['filed'], e['key']))[:limit]
    if not pending:
        return None
    return dict(version='sec-capture-request/1',
                request_id='discovery-' + queue['checkpoint_sha256'][:24],
                filings=[dict(cik=e['cik'], accession=e['accession']) for e in pending])


def bind_capture(entry, packet, archive):
    """Replay trusted capture logic against retained objects before intake binding."""
    current = packet['lineage']['current']
    if (packet['cik'] != entry['cik'] or current['accessionNumber'] != entry['accession'] or
            current['form'] != entry['form'] or current['filingDate'] != entry['filed']):
        raise ValueError('Captured filing/index identity mismatch')
    if packet.get('publication_allowed') is not False or entry['hold_reasons']:
        raise ValueError('Held or nonprivate capture cannot advance')
    extra = [d['filing']['accessionNumber'] for d in packet['documents']
             if d['filing']['accessionNumber'] not in (current['accessionNumber'], packet['lineage']['root']['accessionNumber'])]
    rebuilt = capture(entry['intake']['records'][0], Archive(archive), [], extra)
    if rebuilt['lineage'] != packet['lineage'] or rebuilt['metadata_artifacts'] != packet['metadata_artifacts']:
        raise ValueError('Captured registration metadata does not replay')
    def document_identity(document):
        return {k: document[k] for k in ('filing', 'source', 'normalized_text_sha256', 'normalizer')}
    if sorted(map(document_identity, rebuilt['documents']), key=canonical) != sorted(map(document_identity, packet['documents']), key=canonical):
        raise ValueError('Captured source version does not replay')
    rebuilt['intake_batch_id'] = entry['intake']['id']
    return rebuilt


def record_capture(queue, key, packet, archive):
    validate_checkpoint(queue)
    updated = deepcopy(queue)
    entry = next(e for e in updated['entries'] if e['key'] == key)
    bound = bind_capture(entry, packet, archive)
    entry['capture'] = dict(packet_sha256=sha(canonical(bound).encode()),
                            source_sha256s=sorted(d['source']['content_sha256'] for d in bound['documents']))
    entry['registration_file_number'] = bound['lineage']['registration_file_number']
    entry['root_accession'] = bound['lineage']['root']['accessionNumber']
    entry['status'] = 'captured_review_pending'
    entry['capture_attempts'] = entry.get('capture_attempts', 0) + 1
    return seal(updated), bound


def record_capture_failure(queue, key, error_type):
    validate_checkpoint(queue)
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', error_type):
        raise ValueError('Sanitized exception type required')
    updated = deepcopy(queue)
    entry = next(e for e in updated['entries'] if e['key'] == key)
    if entry['status'] != 'capture_pending':
        raise ValueError('Only pending captures may record retrieval failures')
    entry['capture_attempts'] = entry.get('capture_attempts', 0) + 1
    entry['last_capture_error_type'] = error_type
    return seal(updated)


def reviewed_handoff(entry, packet, review, archive, expected_manifest):
    """Regenerate reviewed SQL; names/heuristic results cannot authorize facts."""
    bound = bind_capture(entry, packet, archive)
    if review.get('intake_record_id') != entry['intake']['records'][0]['id']:
        raise ValueError('Review must bind to discovered intake identity')
    result, sql, objects = build_review(bound, review, entry['intake'], Path(archive))
    if result != expected_manifest:
        raise ValueError('Exact reviewed release manifest mismatch')
    # Current importer is insert-only. Amendments/new finals for an existing
    # issuer need explicit version-refresh review, never a duplicate insert.
    held = entry['existing_issuer'] or not entry['staging_inventory_checked']
    reason = ('existing_issuer_refresh_requires_review' if entry['existing_issuer']
              else 'staging_inventory_unverified' if not entry['staging_inventory_checked'] else None)
    receipt = dict(status='reviewed_refresh_held' if held else 'reviewed_import_ready',
                   reason=reason,
                   release_id=result['release_id'], offering_id=result['offering_id'],
                   packet_sha256=sha(canonical(bound).encode()), review_sha256=sha(canonical(review).encode()),
                   manifest_sha256=sha(canonical(result).encode()), sql_sha256=sha(sql.encode()),
                   source_sha256s=sorted(d['source']['content_sha256'] for d in bound['documents']),
                   publication_allowed=False, applied=False, complete_offering=False)
    return receipt, sql if not held else None, objects


def checkpoint_sql(queue, artifacts=None):
    """Archive immutable private bytes only. Chunk large index/checkpoint objects."""
    validate_checkpoint(queue)
    objects = dict(artifacts or {})
    raw = canonical(queue).encode()
    objects[sha(raw)] = raw
    stored, chunked = plan_artifact_archive(objects)
    statements = ['begin;']
    for checksum, body in sorted(stored.items()):
        packed = base64.b64encode(gzip.compress(body, mtime=0)).decode()
        statements.append("insert into ops.sec_artifacts(sha256,raw_bytes,content_gzip) values("
                          f"'{checksum}',{len(body)},decode('{packed}','base64')) on conflict do nothing;")
    statements.append('commit;')
    return '\n'.join(statements) + '\n', dict(checkpoint_object_sha256=sha(raw),
                                              checkpoint_sha256=queue['checkpoint_sha256'],
                                              artifact_archive=chunked)


def local_path(base, value):
    path = (base / value).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError('Artifact path escapes input directory')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--previous-sha256')
    parser.add_argument('--staged', type=Path)
    parser.add_argument('--monitor-hints', type=Path)
    parser.add_argument('--capture', action='append', nargs=3, default=[],
                        metavar=('PACKET', 'SHA256', 'ARCHIVE'))
    parser.add_argument('--review', action='append', nargs=3, default=[],
                        metavar=('KEY', 'REVIEW', 'EXPECTED_MANIFEST'))
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    if bool(args.previous) != bool(args.previous_sha256):
        parser.error('Prior checkpoint requires both path and expected checkpoint hash')
    spec = json.loads(args.input.read_text())
    artifacts = {s['sha256']: local_path(args.input.parent, s['path']).read_bytes() for s in spec['indexes']}
    previous = json.loads(args.previous.read_text()) if args.previous else None
    if previous:
        validate_checkpoint(previous, args.previous_sha256)
    queue = build_queue(spec, artifacts, previous,
                        json.loads(args.staged.read_text()) if args.staged else None,
                        json.loads(args.monitor_hints.read_text()) if args.monitor_hints else [])
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    captures = {}
    for packet_path, expected_hash, archive_path in args.capture:
        raw = Path(packet_path).read_bytes()
        if sha(raw) != expected_hash:
            raise ValueError('Capture packet hash mismatch')
        packet = json.loads(raw)
        key = identity(packet['cik'], packet['lineage']['current']['accessionNumber'])
        queue, bound = record_capture(queue, key, packet, Path(archive_path))
        captures[key] = (packet, Path(archive_path))
        bound_raw = canonical(bound).encode()
        artifacts[sha(bound_raw)] = bound_raw
        for metadata in [*bound['metadata_artifacts'], *(d['source'] for d in bound['documents'])]:
            checksum = metadata['content_sha256']
            artifacts[checksum] = (Path(archive_path) / 'objects' / checksum).read_bytes()
        for document in bound['documents']:
            checksum = document['normalized_text_sha256']
            artifacts[checksum] = (Path(archive_path) / 'objects' / checksum).read_bytes()
        (output / ('bound-' + key.replace('/', '-') + '.json')).write_text(canonical(bound) + '\n')
    for key, review_path, manifest_path in args.review:
        if key not in captures:
            raise ValueError('Reviewed handoff requires same-run source replay')
        entry = next(e for e in queue['entries'] if e['key'] == key)
        packet, archive = captures[key]
        receipt, statement, source_objects = reviewed_handoff(
            entry, packet, json.loads(Path(review_path).read_text()), archive,
            json.loads(Path(manifest_path).read_text()))
        entry['handoff'], entry['status'] = receipt, receipt['status']
        artifacts.update(source_objects)
        for path in (review_path, manifest_path):
            raw = Path(path).read_bytes()
            artifacts[sha(raw)] = raw
        if statement:
            (output / ('reviewed-' + key.replace('/', '-') + '.sql')).write_text('begin;\n' + statement + 'commit;\n')
        queue = seal(queue)
    (output / 'queue.json').write_text(canonical(queue) + '\n')
    request = capture_request(queue)
    (output / 'capture-request.json').write_text(canonical(request) + '\n')
    sql, receipt = checkpoint_sql(queue, artifacts)
    (output / 'checkpoint.sql').write_text(sql)
    (output / 'checkpoint-receipt.json').write_text(canonical(receipt) + '\n')
    for entry in queue['entries']:
        if entry['hold_reasons'] or entry['staged_current_snapshot']:
            continue
        stem = entry['cik'] + '-' + entry['accession']
        (output / (stem + '-intake.json')).write_text(canonical(entry['intake']) + '\n')
        (output / (stem + '-intake.sql')).write_text('begin;\n' + export_sql(entry['intake']) + 'commit;\n')
    print(canonical(dict(checkpoint_sha256=queue['checkpoint_sha256'], candidates=len(queue['entries']),
                         states=dict(Counter(e['status'] for e in queue['entries'])),
                         missing_weekdays=queue['coverage']['missing_weekdays'], publication_allowed=False)))


if __name__ == '__main__':
    main()
