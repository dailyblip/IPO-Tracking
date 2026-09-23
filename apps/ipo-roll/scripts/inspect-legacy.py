"""Read-only migration assessment. Never imports data or modifies the legacy feed."""
import argparse, hashlib, json, re
from pathlib import Path

def inspect(path):
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    if data.get('schema_version') != 1 or not isinstance(data.get('filings'), list):
        raise ValueError('Unsupported source contract')
    findings = []
    ready = 0
    people = 0
    for row in data['filings']:
        accession = row.get('accession_no', '')
        issues = []
        if not re.fullmatch(r'\d{10}', row.get('cik', '')):
            issues.append('Missing exact company CIK')
        if not re.fullmatch(r'\d{10}-\d{2}-\d{6}', accession):
            issues.append('Missing exact filing accession')
        lineage = (row.get('filing_price_source') or {}).get('file_number')
        if not lineage:
            issues.append('Registration lineage requires SEC resolution')
        if row.get('stage') != 'Pre-pricing' and not (row.get('pricing_date') and isinstance(row.get('offering_price'), (int, float)) and row['offering_price'] > 0):
            issues.append('Final price/date requires validation')
        if issues:
            findings.append({'accession': accession, 'issues': issues})
        else:
            ready += 1
        people += len(row.get('people', []))
    return {'mode': 'READ_ONLY_ASSESSMENT', 'input_sha256': hashlib.sha256(raw).hexdigest(), 'generated_at': data.get('generated_at'), 'offerings': len(data['filings']), 'person_or_holder_entries': people, 'basic_identity_candidates': ready, 'findings': findings, 'publication_allowed': False, 'next_gate': 'Resolve root lineage, field-specific provenance and release approval before import. Collect biographies separately. No provider quotes are copied.'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feed')
    args = parser.parse_args()
    print(json.dumps(inspect(args.feed), indent=2))
