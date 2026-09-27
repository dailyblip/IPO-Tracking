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
from capture_sec_evidence import text_blocks
from build_review_batch import passage

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


DISPOSITIONS = {'resale_not_initial_ipo', 'follow_on_prior_2025_ipo',
                'secondary_offering_prior_2025_ipo', 'excluded_blank_check_company'}


def load_dispositions(path, expected_hash, archive):
    """Validate an explicitly reviewed checkpoint against retained source bytes.

    This validates the review's provenance, not its financial interpretation.
    Only a previously reviewed, hash-pinned checkpoint may classify a filing.
    """
    raw = path.read_bytes()
    if sha(raw) != expected_hash:
        raise ValueError('Disposition checkpoint hash mismatch')
    checkpoint = json.loads(raw)
    if (checkpoint.get('version') != 'sec-census-disposition-checkpoint/1'
            or checkpoint.get('issuer_wide_exclusion') is not False):
        raise ValueError('Exact-filing disposition checkpoint required')
    date.fromisoformat(checkpoint['reviewed_at'])
    results = {}
    for row in checkpoint['rows']:
        key = (row['cik'], row['accession'])
        if (not re.fullmatch(r'\d{10}', key[0])
                or not re.fullmatch(r'\d{10}-\d{2}-\d{6}', key[1])
                or row.get('scope') != 'exact_filing_only'
                or row.get('publication_allowed') is not False
                or row.get('disposition') not in DISPOSITIONS):
            raise ValueError('Invalid exact-filing disposition')
        if key in results:
            raise ValueError('Duplicate disposition identity')
        source = row['source']
        checksum = source['content_sha256']
        if not re.fullmatch(r'[0-9a-f]{64}', checksum):
            raise ValueError('Invalid source hash')
        prefix = f'https://www.sec.gov/Archives/edgar/data/{int(key[0])}/{key[1].replace("-", "")}/'
        if not re.fullmatch(re.escape(prefix) + r'[A-Za-z0-9_.-]+', source['url']):
            raise ValueError('Disposition source identity mismatch')
        source_raw = (archive / 'objects' / checksum).read_bytes()
        if len(source_raw) != source['bytes'] or sha(source_raw) != checksum:
            raise ValueError('Disposition source hash/length mismatch')
        text, blocks = text_blocks(source_raw)
        if sha(text.encode()) != row['normalized_text_sha256']:
            raise ValueError('Disposition normalized source mismatch')
        if not row['evidence']:
            raise ValueError('Disposition needs reviewed passages')
        for evidence in row['evidence']:
            locator = evidence['locator']
            actual = passage(blocks, locator['first_block'], locator['last_block'], text)
            if actual != evidence:
                raise ValueError('Disposition passage mismatch')
        results[key] = dict(row, checkpoint_sha256=expected_hash)
    return results


def reconcile(rows, staged, dispositions=None):
    dispositions = dispositions or {}
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
        review = dispositions.get(key)
        if review:
            if key in exact:
                raise ValueError('Reviewed exclusion conflicts with staged offering')
            if row['form'] != review['form'] or row['filed'] != review['filed']:
                raise ValueError('Disposition/index identity mismatch')
        # A known issuer is NOT proof that another registration is imported.
        status = ('reviewed_excluded_filing' if review else
                  'exact_current_snapshot' if key in exact else
                  'issuer_present_lineage_review' if key[0] in issuers else
                  'unreviewed_candidate')
        item = row | {'status': status,
                      'offering_id': exact[key]['id'] if key in exact else None}
        if review:
            item['review'] = {k: review[k] for k in ('disposition', 'checkpoint_sha256')}
            item['review']['source_sha256'] = review['source']['content_sha256']
        result.append(item)
    if set(dispositions) - seen:
        raise ValueError('Disposition not present in scoped SEC index')
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
    parser.add_argument('--disposition-checkpoint', action='append', nargs=3,
                        metavar=('PATH', 'SHA256', 'ARCHIVE'), default=[])
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
    dispositions = {}
    for path, checksum, archive in args.disposition_checkpoint:
        reviewed = load_dispositions(Path(path), checksum, Path(archive))
        if dispositions.keys() & reviewed.keys():
            raise ValueError('Overlapping disposition checkpoints')
        dispositions.update(reviewed)
    result = reconcile(rows, json.loads(staged_raw), dispositions)
    report = {'version': 'sec-census-reconciliation/1', 'start': args.start, 'end': args.end,
              'checkpoint_sha256': args.checkpoint_sha256, 'staged_sha256': sha(staged_raw),
              'indexes': index_evidence, 'forms': sorted(FORMS), 'other_form_counts': dict(outside),
              'filing_month_counts': summarize(result), 'candidates': result,
              'complete': False, 'publication_allowed': False,
              'limitations': ['Counts are filing rows, not unique IPOs or pricing-month totals.',
                             'Retained index snapshot requires end-date freshness reconciliation.',
                             'Other registration/prospectus forms require scope review.',
                             'Unreviewed and lineage rows require registration-lineage and source review.',
                             'Reviewed exclusions apply only to exact filings, never whole issuers.',
                             'Exact offering matches do not establish biography/ownership completeness.']}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'inventory.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'candidates'}, indent=2))


if __name__ == '__main__':
    main()
