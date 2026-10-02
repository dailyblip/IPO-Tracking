"""Build a private, reproducible intake from a committed legacy feed. Never publishes.

No network, database credentials or legacy writes. Generated SQL is for an administrator
on staging only. Every value is an observation, not an independently verified fact.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import uuid
from urllib.parse import urlsplit

VERSION = 'legacy-intake/1'
FEED_PATH = 'docs/data/filings.json'
NAMESPACE = uuid.UUID('bc8421c2-9b4d-4b91-92ea-096b30313622')
FIELDS = ('company', 'ticker', 'cik', 'accession_no', 'form', 'filed',
          'filing_date', 'stage', 'pricing_date', 'offering_price', 'value',
          'filing_price', 'primary_offering_shares', 'secondary_offering_shares')
HOLDER_FIELDS = ('name', 'holder_type', 'is_beneficial_owner', 'ownership_percent',
                 'ownership_percent_before', 'ownership_percent_after',
                 'shares_before_ipo', 'shares_sold_ipo', 'shares_after_ipo')
NUMERIC = {'offering_price', 'value', 'primary_offering_shares', 'secondary_offering_shares'}
DATES = {'filed', 'filing_date', 'pricing_date'}
RESTRICTED = re.compile(r'stanford|#8c1515', re.I)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def identity(*parts):
    return str(uuid.uuid5(NAMESPACE, ':'.join(str(p) for p in parts)))


def valid_date(value):
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def valid_number(value, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum


def safe_text(value, limit=250):
    return isinstance(value, str) and len(value) <= limit and '\x00' not in value and not RESTRICTED.search(value)


def sec_index(url, cik, accession):
    """CIK belongs to the issuer; accession prefix can belong to the filing agent."""
    if not isinstance(url, str) or not isinstance(cik, str) or not re.fullmatch(r'\d{10}', cik):
        return None
    if not isinstance(accession, str) or not re.fullmatch(r'\d{10}-\d{2}-\d{6}', accession):
        return None
    expected = f'/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}/{accession}-index.htm'
    try:
        parsed = urlsplit(url)
        if parsed.scheme == 'https' and parsed.netloc == 'www.sec.gov' and parsed.path == expected and not parsed.query and not parsed.fragment:
            return url
    except ValueError:
        pass
    return None


def source_ref(source, cik):
    if not isinstance(source, dict):
        return None
    accession = source.get('accession_no')
    url = sec_index(source.get('sec_url'), cik, accession)
    if not url or source.get('form') not in ('S-1', 'S-1/A', 'F-1', 'F-1/A', '424B4') or not valid_date(source.get('filing_date')):
        return None
    result = {'url': url, 'accession': accession, 'form': source['form'], 'filed_on': source['filing_date']}
    number = source.get('file_number')
    if isinstance(number, str) and re.fullmatch(r'333-\d+', number):
        result['registration_file_number'] = number
    return result


def build(raw, commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('An exact full Git commit SHA is required')
    feed = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON')))
    if feed.get('schema_version') != 1 or not isinstance(feed.get('filings'), list):
        raise ValueError('Unsupported feed contract')
    if not isinstance(feed.get('generated_at'), str):
        raise ValueError('Missing generated_at')
    generated = datetime.fromisoformat(feed['generated_at'])
    if generated.tzinfo is None:
        raise ValueError('generated_at must include timezone')
    sha = digest(raw)
    batch = {'version': VERSION, 'source_commit': commit, 'input_sha256': sha,
             'source_path': FEED_PATH, 'generated_at': generated.isoformat(),
             'run_id': identity('run', commit, sha), 'id': identity('batch', commit, sha, VERSION),
             'records': []}
    keys = Counter((r.get('cik'), r.get('accession_no')) for r in feed['filings'] if isinstance(r, dict))
    for i, row in enumerate(feed['filings']):
        if not isinstance(row, dict):
            raise ValueError(f'filings/{i} is not an object')
        pointer = f'/filings/{i}'
        rid = identity(batch['id'], pointer)
        findings = {'ROOT_LINEAGE_UNVERIFIED', 'OPERATING_COMPANY_REVIEW_REQUIRED', 'SOURCE_DOCUMENT_CAPTURE_REQUIRED', 'COMMERCIAL_RIGHTS_REVIEW_REQUIRED'}
        projected = {}
        for field in FIELDS:
            value = row.get(field)
            if value is None:
                continue
            valid = valid_number(value) if field in NUMERIC else valid_date(value) if field in DATES else safe_text(value)
            if not valid:
                findings.add('INVALID_OR_RESTRICTED_FIELD')
                continue
            projected[field] = value
        cik, accession = projected.get('cik'), projected.get('accession_no')
        current = source_ref({'sec_url': row.get('sec_url'), 'accession_no': accession,
                              'form': projected.get('form'), 'filing_date': projected.get('filed')}, cik)
        preliminary = source_ref(row.get('filing_price_source'), cik)
        if preliminary and preliminary['form'] not in ('S-1', 'S-1/A', 'F-1', 'F-1/A'):
            preliminary = None
        if not current:
            findings.add('INVALID_CURRENT_FILING_IDENTITY')
        if not preliminary or not preliminary.get('registration_file_number'):
            findings.add('REGISTRATION_NUMBER_MISSING')
        if keys[(row.get('cik'), row.get('accession_no'))] > 1:
            findings.add('DUPLICATE_FILING_IDENTITY')
        stage = projected.get('stage')
        if stage not in ('Pre-pricing', 'Priced'):
            findings.add('INVALID_LIFECYCLE_STAGE')
        elif stage == 'Pre-pricing':
            if row.get('offering_price') is not None or row.get('pricing_date') is not None or row.get('current_price') is not None:
                findings.add('PREPRICING_FINAL_OR_QUOTE_CONFLICT')
            if projected.get('form') not in ('S-1', 'S-1/A', 'F-1', 'F-1/A'):
                findings.add('FORM_STAGE_CONFLICT')
        else:
            if not valid_number(projected.get('offering_price'), minimum=0.000001) or not valid_date(projected.get('pricing_date')):
                findings.add('FINAL_PRICE_DATE_MISSING')
            if projected.get('form') != '424B4':
                findings.add('FORM_STAGE_CONFLICT')
            # Legacy `filed` is the current document date, not the root registration date.
            if projected.get('filing_date') and projected.get('pricing_date') and projected['pricing_date'] < projected['filing_date']:
                findings.add('PRICING_PRECEDES_REPORTED_REGISTRATION')
        if row.get('filing_price') is not None and preliminary is None:
            findings.add('PRELIMINARY_PRICE_SOURCE_MISSING')
        observations = []
        for field, value in projected.items():
            source = preliminary if field == 'filing_price' else current
            # These dates/amounts lack field-specific source spans in the public feed.
            observations.append({'field': field, 'value': value, 'pointer': f'{pointer}/{field}',
                                 'reported_source': source, 'verification': 'feed_reported'})
        holders = []
        people = row.get('people', [])
        if not isinstance(people, list):
            raise ValueError(f'{pointer}/people is not an array')
        ownership = source_ref(row.get('ownership_source'), cik)
        for j, person in enumerate(people):
            if not isinstance(person, dict):
                findings.add('INVALID_HOLDER_ENTRY')
                continue
            holder = {}
            for field in HOLDER_FIELDS:
                value = person.get(field)
                if value is None:
                    continue
                if field == 'is_beneficial_owner':
                    valid = type(value) is bool
                elif field in ('name', 'holder_type'):
                    valid = safe_text(value)
                else:
                    valid = valid_number(value) or (safe_text(value, 80) and bool(re.fullmatch(r'[\d.,%<>*\s-]+', value)))
                if valid:
                    holder[field] = value
                else:
                    findings.add('INVALID_OR_RESTRICTED_HOLDER_FIELD')
            if holder.get('name'):
                holders.append({'ordinal': j, 'pointer': f'{pointer}/people/{j}', 'values': holder,
                                'reported_source': ownership, 'verification': 'unverified'})
        if holders:
            findings.add('HOLDER_IDENTITY_AND_EVIDENCE_REVIEW_REQUIRED')
        batch['records'].append({'id': rid, 'ordinal': i, 'pointer': pointer,
                                 'record_sha256': digest(row), 'values': projected,
                                 'observations': observations, 'holders': holders,
                                 'findings': sorted(findings), 'status': 'quarantined'})
    batch['payload_sha256'] = digest(batch)
    return batch


def summary(batch):
    records = batch['records']
    return {'importer_version': VERSION, 'batch_id': batch['id'], 'source_commit': batch['source_commit'],
            'input_sha256': batch['input_sha256'], 'payload_sha256': batch['payload_sha256'],
            'records': len(records), 'observations': sum(len(r['observations']) for r in records),
            'holder_candidates': sum(len(r['holders']) for r in records),
            'quarantined': len(records), 'published': 0,
            'findings': dict(sorted(Counter(code for r in records for code in r['findings']).items()))}


def sql(batch):
    # A deterministic delimiter absent from the entire payload, not SQL interpolation.
    payload = canonical(batch)
    tag = '$intake_' + digest(payload.encode()) + '$'
    if tag in payload:
        raise ValueError('Unsafe SQL delimiter')
    return f'-- Private staging intake only. Never publishes research records.\nselect ops.import_legacy_intake({tag}{payload}{tag}::jsonb);\n'


def committed_feed(repo, commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Use an exact full commit SHA')
    resolved = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', '--verify', commit + '^{commit}'], text=True).strip()
    if resolved != commit:
        raise ValueError('Commit does not resolve exactly')
    return subprocess.check_output(['git', '-C', str(repo), 'show', f'{commit}:{FEED_PATH}'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    batch = build(committed_feed(args.repo, args.source_commit), args.source_commit)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, contents in [('intake.json', canonical(batch)), ('intake.sql', sql(batch)), ('summary.json', json.dumps(summary(batch), indent=2))]:
        (args.output_dir / name).write_text(contents + '\n')
    print(json.dumps(summary(batch), indent=2))


if __name__ == '__main__':
    main()
