"""Restore retained SEC indexes and account for every scoped filing candidate.

Offline only; no publication, inferred eligibility or issuer-name matching.
Generated inventory is private review work, not a public enriched dataset.
"""
import argparse
import base64
from collections import Counter, defaultdict
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
import re

from build_sec_index_intake import ROW

FORMS = {'S-1', 'S-1/A', 'F-1', 'F-1/A', 'S-11', 'S-11/A',
         'F-10', 'F-10/A', '424B1', '424B3', '424B4'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode_object(path, expected):
    raw = gzip.decompress(base64.b64decode(path.read_text()))
    if sha(raw) != expected:
        raise ValueError('Retained object hash mismatch')
    return raw


def restore_index(spec, chunks):
    parts, offset = [], 0
    for item in spec['chunks']:
        if item['start'] != offset:
            raise ValueError('Index chunk gap, overlap or order mismatch')
        raw = decode_object(chunks / (item['sha256'] + '.b64'), item['sha256'])
        if len(raw) != item['length']:
            raise ValueError('Index chunk length mismatch')
        parts.append(raw)
        offset += len(raw)
    raw = b''.join(parts)
    if len(raw) != spec['bytes'] or sha(raw) != spec['sha256']:
        raise ValueError('Full SEC index hash/length mismatch')
    if spec['metadata']['sha256'] != spec['sha256']:
        raise ValueError('SEC index metadata hash mismatch')
    return raw


def parse_index(raw, source_url, index_hash, start, end):
    if not re.fullmatch(r'https://www\.sec\.gov/Archives/edgar/full-index/\d{4}/QTR[1-4]/master\.idx', source_url):
        raise ValueError('Canonical quarterly index URL required')
    if sha(raw) != index_hash:
        raise ValueError('SEC index hash mismatch')
    rows, outside_forms, seen = [], Counter(), set()
    for line in raw.decode('latin-1').splitlines():
        match = ROW.fullmatch(line)
        if not match:
            # Reject malformed data, not the SEC header/preamble.
            if re.match(r'^\d+\|', line):
                raise ValueError('Malformed SEC index data row')
            continue
        row = match.groupdict()
        date.fromisoformat(row['filed'])
        if not start <= row['filed'] <= end:
            continue
        if row['form'] not in FORMS:
            if row['form'].startswith(('424', 'S-', 'F-')):
                outside_forms[row['form']] += 1
            continue
        key = (row['cik'].zfill(10), row['accession'])
        if key in seen:
            raise ValueError('Duplicate SEC filing identity')
        seen.add(key)
        rows.append(row | {'cik': key[0], 'exact_index_row': line,
                          'index_url': source_url, 'index_sha256': index_hash})
    return rows, dict(outside_forms)


def reconcile(rows, staged):
    exact = {(r['cik'].zfill(10), r['accession_no']): r for r in staged}
    issuers = {key[0] for key in exact}
    if len(exact) != len(staged):
        raise ValueError('Duplicate staged filing identity')
    result, seen = [], set()
    for row in sorted(rows, key=lambda r: (r['filed'], r['cik'], r['accession'])):
        key = (row['cik'], row['accession'])
        if key in seen:
            raise ValueError('Duplicate candidate across indexes')
        seen.add(key)
        # A known issuer is NOT proof that another registration is imported.
        status = ('exact_current_snapshot' if key in exact else
                  'issuer_present_lineage_review' if key[0] in issuers else
                  'unreviewed_candidate')
        result.append(row | {'status': status,
                            'offering_id': exact[key]['id'] if key in exact else None})
    return result


def summarize(rows):
    months = defaultdict(Counter)
    for row in rows:
        months[row['filed'][:7]][row['status']] += 1
    return {month: dict(counts) for month, counts in sorted(months.items())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True, type=Path)
    parser.add_argument('--checkpoint-sha256', required=True)
    parser.add_argument('--chunks', required=True, type=Path)
    parser.add_argument('--staged', required=True, type=Path)
    parser.add_argument('--start', default='2026-01-01')
    parser.add_argument('--end', required=True)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    if date.fromisoformat(args.start) > date.fromisoformat(args.end):
        raise ValueError('Reversed census interval')
    checkpoint = json.loads(decode_object(args.checkpoint, args.checkpoint_sha256))
    if checkpoint['version'] != 'sec-index-checkpoint/1':
        raise ValueError('Unsupported checkpoint version')
    staged_raw = args.staged.read_bytes()
    rows, index_evidence, outside = [], [], Counter()
    for spec in checkpoint['indexes']:
        raw = restore_index(spec, args.chunks)
        parsed, other = parse_index(raw, spec['metadata']['url'], spec['sha256'], args.start, args.end)
        rows.extend(parsed)
        outside.update(other)
        index_evidence.append({k: spec['metadata'][k] for k in ('url', 'sha256', 'retrieved_at')})
    result = reconcile(rows, json.loads(staged_raw))
    report = {'version': 'sec-census-reconciliation/1', 'start': args.start, 'end': args.end,
              'checkpoint_sha256': args.checkpoint_sha256, 'staged_sha256': sha(staged_raw),
              'indexes': index_evidence, 'forms': sorted(FORMS), 'other_form_counts': dict(outside),
              'filing_month_counts': summarize(result), 'candidates': result,
              'complete': False, 'publication_allowed': False,
              'limitations': ['Counts are filing rows, not unique IPOs or pricing-month totals.',
                             'Retained index snapshot requires end-date freshness reconciliation.',
                             'Other registration/prospectus forms require scope review.',
                             'All non-exact rows require registration-lineage and source review.',
                             'Exact offering matches do not establish biography/ownership completeness.']}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'inventory.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'candidates'}, indent=2))


if __name__ == '__main__':
    main()
