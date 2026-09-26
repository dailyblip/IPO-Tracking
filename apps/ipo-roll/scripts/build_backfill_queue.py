"""Audit a private legacy intake against staging. No publication or database writes.

The queue is a discovery inventory, never proof of complete SEC coverage. Include
2026 pricing even when the root registration predates the requested interval.
"""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
from import_legacy import digest, valid_date


def build_queue(intake, staged, start, through):
    if not valid_date(start) or not valid_date(through) or start > through:
        raise ValueError('Invalid inclusive date interval')
    if intake.get('payload_sha256') != digest({k: v for k, v in intake.items() if k != 'payload_sha256'}):
        raise ValueError('Intake payload hash mismatch')
    existing = {(r['cik'], r['accession']) for r in staged}
    issuers = {r['cik'] for r in staged}
    duplicates = Counter((r['values'].get('cik'), r['values'].get('accession_no')) for r in intake['records'])
    rows = []
    for index, record in enumerate(intake['records']):
        values = record['values']
        dates = {key: values[key] for key in ('pricing_date', 'filed', 'filing_date')
                 if valid_date(values.get(key)) and start <= values[key] <= through}
        if not dates:
            continue
        key = (values.get('cik'), values.get('accession_no'))
        if duplicates[key] > 1:
            status = 'duplicate_identity_review'
        elif key in existing:
            status = 'already_staged_snapshot'
        elif key[0] in issuers:
            status = 'existing_issuer_reconciliation'
        else:
            status = 'source_review_required'
        # Pricing cohort takes precedence; otherwise use earliest activity in range.
        cohort = dates.get('pricing_date') or min(dates.values())
        rows.append({'index': index, 'record_id': record['id'], 'cik': key[0],
                     'accession': key[1], 'cohort_month': cohort[:7],
                     'qualifying_dates': dates, 'status': status})
    rows.sort(key=lambda r: (r['cohort_month'], r['accession'] or '', r['record_id']))
    months = {}
    cursor = date.fromisoformat(start).replace(day=1)
    while cursor.isoformat() <= through:
        month = cursor.strftime('%Y-%m')
        months[month] = dict(sorted(Counter(r['status'] for r in rows if r['cohort_month'] == month).items()))
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return {'version': 'backfill-queue/1', 'start': start, 'through': through,
            'source_commit': intake['source_commit'], 'intake_batch_id': intake['id'],
            'intake_sha256': intake['payload_sha256'], 'staging_snapshot_sha256': digest(staged),
            'candidate_count': len(rows), 'months': months, 'records': rows,
            'publication_allowed': False, 'sec_coverage_complete': False,
            'next_gate': 'Capture SEC evidence and review issuer/registration, eligibility, terms and people; independently reconcile SEC interval coverage.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--intake', type=Path, required=True)
    parser.add_argument('--staging-snapshot', type=Path, required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--through', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build_queue(json.loads(args.intake.read_text()), json.loads(args.staging_snapshot.read_text()), args.start, args.through)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}, indent=2))
