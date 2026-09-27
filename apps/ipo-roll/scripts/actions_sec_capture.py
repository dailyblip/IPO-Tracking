"""Bounded capture-only runner. Upload only encrypted evidence, never the contact.

The committed request contains public SEC identifiers, not reviewed research.
No database access, publication, source eligibility decision or inferred people.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import time

from capture_sec_evidence import Archive, capture, load_history, resolve_lineage, sha
from import_legacy import canonical
from build_internal_pilot import uid


def validate_request(request):
    if set(request) != {'version', 'request_id', 'filings'} or request['version'] != 'sec-capture-request/1':
        raise ValueError('Unsupported request format')
    if not isinstance(request['request_id'], str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', request['request_id']):
        raise ValueError('Invalid request identifier')
    rows = request['filings']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 4:
        raise ValueError('Capture requires one to four filings')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'cik', 'accession'}:
            raise ValueError('Only exact SEC identities are allowed')
        if not isinstance(row['cik'], str) or not re.fullmatch(r'\d{10}', row['cik']):
            raise ValueError('Invalid CIK')
        if not isinstance(row['accession'], str) or not re.fullmatch(r'\d{10}-\d{2}-\d{6}', row['accession']):
            raise ValueError('Invalid accession')
        key = (row['cik'], row['accession'])
        if key in seen:
            raise ValueError('Duplicate capture request')
        seen.add(key)
    return rows


class BoundedArchive(Archive):
    def __init__(self, directory):
        super().__init__(directory, fetch=True)
        self.request_count = 0
        self.total_bytes = 0

    def get(self, url):
        cached = self.directory / 'requests' / (sha(url.encode()) + '.json')
        if cached.exists():
            return Archive(self.directory).get(url)
        if self.request_count >= 80 or self.total_bytes >= 256_000_000:
            raise ValueError('Capture budget exhausted')
        time.sleep(max(0, 1 - (time.monotonic() - self.last_request)))
        self.request_count += 1
        raw, meta = super().get(url)
        self.total_bytes += len(raw)
        if self.total_bytes > 256_000_000:
            raise ValueError('Capture byte budget exhausted')
        return raw, meta


def seal(directory, recipient, output):
    """Authenticated CMS encryption; only the recipient private key decrypts."""
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / 'evidence.tar.gz'
        with tarfile.open(bundle, 'w:gz') as archive:
            archive.add(directory, arcname='evidence')
        subprocess.run(['openssl', 'cms', '-encrypt', '-binary', '-aes-256-gcm',
                        '-in', str(bundle), '-outform', 'DER', '-out', str(output),
                        str(recipient)], check=True, capture_output=True)


def run(request, recipient, output):
    rows = validate_request(request)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        archive = BoundedArchive(directory / 'archive')
        results = []
        for row in rows:
            try:
                history, _ = load_history(archive, row['cik'])
                lineage = resolve_lineage(history, row['accession'])
                current = lineage['current']
                amendments = [f for f in lineage['history'] if f['form'] in ('S-1/A', 'F-1/A')]
                extra = [amendments[-1]['accessionNumber']] if amendments else []
                record = dict(id=uid('sec-capture-discovery', row['cik'], row['accession']),
                              values=dict(cik=row['cik'], accession_no=row['accession'],
                                          form=current['form'], filed=current['filingDate']),
                              observations=[], holders=[])
                packet = capture(record, archive, [], extra)
                packet['discovery_only'] = True
                # Bind to a separately reviewed intake before using import tooling.
                (directory / ('capture-' + row['accession'] + '.json')).write_text(canonical(packet))
                results.append(dict(row, status='captured', documents=len(packet['documents'])))
            except Exception as exc:
                # Source failures never print raw response bodies, contact or headers.
                results.append(dict(row, status='held', error_type=type(exc).__name__))
        files = {str(p.relative_to(directory)): dict(sha256=sha(p.read_bytes()), bytes=p.stat().st_size)
                 for p in sorted(directory.rglob('*')) if p.is_file()}
        manifest = dict(version='sec-actions-capture/1', request=request, results=results,
                        retrieved_at=datetime.now(timezone.utc).isoformat(), files=files,
                        publication_allowed=False, eligibility='unreviewed')
        (directory / 'manifest.json').write_text(canonical(manifest))
        seal(directory, recipient, output / 'evidence.cms')
    successes = sum(r['status'] == 'captured' for r in results)
    print(json.dumps(dict(captured=successes, held=len(results)-successes, encrypted=True,
                          publication_allowed=False)))
    return 0 if successes == len(rows) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--recipient', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(json.loads(args.request.read_text()), args.recipient, args.output)
    except Exception as exc:
        print('Capture stopped: ' + type(exc).__name__ + '; no secret or response body logged')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
