"""Capture exact SEC artifacts and build an UNAPPROVED evidence review packet.

Uses the legacy SEC_EDGAR_USER_AGENT contact convention. No database writes,
production pipeline changes, inferred biographies, or automatic publication.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

VERSION = 'sec-review/1'
MAX_BYTES = 20_000_000
FORMS = {'S-1', 'S-1/A', 'F-1', 'F-1/A', '424B4'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def valid_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.netloc not in ('www.sec.gov', 'data.sec.gov') or p.query or p.fragment:
        raise ValueError('Only canonical SEC artifact URLs are allowed')
    if p.netloc == 'data.sec.gov':
        valid = re.fullmatch(r'/submissions/CIK\d{10}(?:-submissions-\d{3})?\.json', p.path)
    else:
        valid = re.fullmatch(r'/Archives/edgar/data/\d+/\d{18}/[A-Za-z0-9_.-]+\.(?:htm|html|txt)', p.path)
    if not valid:
        raise ValueError('Unsupported SEC artifact path')
    return url


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('SEC redirect requires review; no redirected capture')


class Archive:
    def __init__(self, directory, fetch=False):
        self.directory = Path(directory)
        self.fetch = fetch
        self.last_request = 0.0
        self.agent = os.environ.get('SEC_EDGAR_USER_AGENT', '').strip()
        if fetch and (not re.search(r'[^\s@]+@[^\s@]+\.[^\s@]+', self.agent) or re.search(r'example\.(?:com|org|net)|\.invalid\b', self.agent, re.I)):
            raise ValueError('Set SEC_EDGAR_USER_AGENT to a descriptive application name and real contact email before live capture')
        self.opener = build_opener(NoRedirect())

    def get(self, url):
        valid_url(url)
        key = sha(url.encode())
        path = self.directory / 'requests' / (key + '.json')
        if not self.fetch:
            if not path.exists():
                raise ValueError(f'No captured artifact for {url}; live capture requires --fetch')
            meta = json.loads(path.read_text())
            content_hash = meta.get('content_sha256', '')
            if meta.get('url') != url or not re.fullmatch(r'[a-f0-9]{64}', content_hash):
                raise ValueError('Invalid cached artifact identity')
            raw = (self.directory / 'objects' / content_hash).read_bytes()
            if sha(raw) != content_hash or len(raw) != meta.get('bytes'):
                raise ValueError('Captured artifact hash/length mismatch')
            return raw, meta
        for attempt in range(3):
            time.sleep(max(0, .25 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                with self.opener.open(Request(url, headers={'User-Agent': self.agent, 'Accept-Encoding': 'identity'}), timeout=30) as response:
                    if response.status != 200:
                        raise ValueError('SEC response was not HTTP 200')
                    raw = response.read(MAX_BYTES + 1)
                    kind = response.headers.get_content_type()
                break
            except HTTPError as exc:
                if exc.code not in (429, 503) or attempt == 2:
                    raise
                delay = exc.headers.get('Retry-After', '2')
                if not delay.isdigit() or int(delay) > 30:
                    raise ValueError('SEC retry delay requires a later capture attempt') from exc
                time.sleep(max(1, int(delay)))
        if len(raw) > MAX_BYTES:
            raise ValueError('SEC artifact exceeds capture limit')
        if kind not in ('application/json', 'text/html', 'text/plain', 'application/xhtml+xml'):
            raise ValueError('Unsupported SEC response content type')
        if url.endswith('.json'):
            json.loads(raw)
        elif b'<html' not in raw.lower() and b'<document>' not in raw.lower():
            raise ValueError('SEC response is not a filing document')
        if b'undeclared automated tool' in raw.lower() or b'request rate threshold exceeded' in raw.lower():
            raise ValueError('SEC access response is not evidence')
        meta = {'url': url, 'content_sha256': sha(raw), 'bytes': len(raw), 'content_type': kind,
                'retrieved_at': datetime.now(timezone.utc).isoformat()}
        (self.directory / 'objects').mkdir(parents=True, exist_ok=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        (self.directory / 'objects' / meta['content_sha256']).write_bytes(raw)
        # The URL pointer may advance; content-addressed artifact bytes remain retained.
        path.write_text(json.dumps(meta, indent=2) + '\n')
        return raw, meta


def column_rows(data):
    columns = ('accessionNumber', 'filingDate', 'form', 'fileNumber', 'primaryDocument')
    if any(not isinstance(data.get(k), list) for k in columns):
        raise ValueError('Incomplete SEC submissions columns')
    if len({len(data[k]) for k in columns}) != 1:
        raise ValueError('Unequal SEC submissions column lengths')
    rows = [dict(zip(columns, values)) for values in zip(*(data[k] for k in columns))]
    for row in rows:
        if not all(isinstance(row[k], str) for k in columns):
            raise ValueError('Non-text SEC metadata field')
        if not re.fullmatch(r'\d{10}-\d{2}-\d{6}', row['accessionNumber']):
            raise ValueError('Malformed SEC accession')
        if date.fromisoformat(row['filingDate']).isoformat() != row['filingDate']:
            raise ValueError('Malformed SEC filing date')
    return rows


def load_history(archive, cik):
    if not re.fullmatch(r'\d{10}', cik):
        raise ValueError('Exact ten-digit issuer CIK required')
    raw, meta = archive.get(f'https://data.sec.gov/submissions/CIK{cik}.json')
    data = json.loads(raw)
    if str(data.get('cik', '')).zfill(10) != cik:
        raise ValueError('Submissions issuer CIK mismatch')
    rows = column_rows(data['filings']['recent'])
    artifacts = [meta]
    descriptors = data['filings'].get('files')
    if not isinstance(descriptors, list):
        raise ValueError('Missing archive history descriptor list')
    for descriptor in descriptors:
        name = descriptor.get('name', '')
        if not re.fullmatch(r'CIK' + cik + r'-submissions-\d{3}\.json', name):
            raise ValueError('Archive descriptor issuer/path mismatch')
        raw, meta = archive.get('https://data.sec.gov/submissions/' + name)
        archived = column_rows(json.loads(raw))
        if descriptor.get('filingCount') != len(archived):
            raise ValueError('Archive descriptor filing-count mismatch')
        rows.extend(archived)
        artifacts.append(meta)
    return rows, artifacts


def resolve_lineage(rows, accession, reported_file_number=None):
    by_accession = {}
    for row in rows:
        key = row['accessionNumber']
        if key in by_accession and by_accession[key] != row:
            raise ValueError('Conflicting submissions rows for one accession')
        by_accession[key] = row
    current = by_accession.get(accession)
    if not current or current['form'] not in FORMS:
        raise ValueError('Current filing absent or unsupported in complete submissions history')
    number = current['fileNumber']
    if not isinstance(number, str) or not re.fullmatch(r'333-\d+', number):
        raise ValueError('Current filing has no exact registration file number')
    if reported_file_number and reported_file_number != number:
        raise ValueError('Reported preliminary source conflicts with current registration')
    group = [r for r in by_accession.values() if r['fileNumber'] == number and r['form'] in FORMS and r['filingDate'] <= current['filingDate']]
    roots = [r for r in group if r['form'] in ('S-1', 'F-1')]
    if len(roots) != 1:
        raise ValueError('Registration requires exactly one unamended root; ambiguous or incomplete history')
    root = roots[0]
    # Submissions lineage is metadata evidence, not a positive operating-IPO classification.
    return {'registration_file_number': number, 'root': root, 'current': current,
            'history': sorted(group, key=lambda r: (r['filingDate'], r['accessionNumber'])),
            'status': 'metadata_resolved', 'offering_eligibility': 'unreviewed'}


def document_url(cik, filing):
    accession = filing['accessionNumber']
    if not re.fullmatch(r'\d{10}-\d{2}-\d{6}', accession):
        raise ValueError('Invalid document accession')
    name = filing['primaryDocument']
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*\.(?:htm|html)', name) or '..' in name:
        raise ValueError('Unsafe primary document name')
    return valid_url(f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}/{name}')


class Blocks(HTMLParser):
    """Conservative paragraph/block boundaries. Excludes hidden/script content."""
    boundaries = {'p', 'div', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'br'}
    voids = {'br', 'hr', 'img', 'meta', 'link', 'input', 'wbr', 'area', 'base', 'embed', 'param', 'source', 'track', 'col'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []
        self.blocks = []

    def flush(self):
        text = re.sub(r'\s+', ' ', ''.join(self.parts)).strip()
        if text:
            self.blocks.append(text)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = tag in ('script', 'style', 'noscript', 'ix:hidden') or 'hidden' in attrs or attrs.get('aria-hidden') == 'true' or bool(re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', attrs.get('style', ''), re.I))
        if tag in self.boundaries:
            self.flush()
        if tag not in self.voids:
            self.stack.append((tag, hidden or any(h for _, h in self.stack)))
        elif tag == 'br':
            self.flush()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.voids:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self.boundaries:
            self.flush()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if not any(hidden for _, hidden in self.stack):
            self.parts.append(data)


def text_blocks(raw):
    parser = Blocks()
    # Fail closed on undecodable input rather than silently altering source text.
    parser.feed(raw.decode('utf-8-sig'))
    parser.flush()
    offset = 0
    blocks = []
    for index, text in enumerate(parser.blocks):
        blocks.append({'index': index, 'start': offset, 'end': offset + len(text), 'text': text})
        offset += len(text) + 1
    return '\n'.join(parser.blocks), blocks


def biography_candidates(blocks, names):
    candidates = []
    names = sorted(set(n for n in names if isinstance(n, str) and len(n.split()) >= 2 and not re.search(r'stanford', n, re.I)))
    for block in blocks:
        text = block['text']
        if len(text) < 80 or len(text) > 5000 or re.search(r'stanford|#8c1515', text, re.I):
            continue
        for name in names:
            if not re.match(r'^(?:(?:Mr|Ms|Mrs|Dr)\.\s+)?' + re.escape(name) + r'(?:\s|[,.:])', text, re.I):
                continue
            if not re.search(r'\b(?:served|serves|joined|received|earned|graduated|holds|has been|is our|is the)\b', text, re.I):
                continue
            # Multiple named subjects in a block are ambiguous; require manual selection.
            if any(other != name and re.search(r'\b' + re.escape(other) + r'\b', text, re.I) for other in names):
                continue
            candidates.append({'name': name, 'excerpt': text, 'locator': {'block': block['index'], 'start': block['start'], 'end': block['end']},
                               'identity_status': 'unverified', 'relationship_status': 'unverified', 'approved': False})
    return candidates


def capture(record, archive, names=()):
    values = record['values']
    cik, accession = values['cik'], values['accession_no']
    rows, artifacts = load_history(archive, cik)
    preliminary = next((o.get('reported_source') for o in record['observations'] if o['field'] == 'filing_price'), None)
    lineage = resolve_lineage(rows, accession, (preliminary or {}).get('registration_file_number'))
    current = lineage['current']
    if current['form'] != values['form'] or current['filingDate'] != values['filed']:
        raise ValueError('Current SEC metadata conflicts with intake form/date')
    if preliminary:
        match = next((r for r in lineage['history'] if r['accessionNumber'] == preliminary['accession']), None)
        if not match or match['form'] != preliminary['form'] or match['filingDate'] != preliminary['filed_on']:
            raise ValueError('Preliminary source is not in the verified registration history')
    wanted = [lineage['root'], current]
    if preliminary:
        wanted.append(match)
    documents = []
    for filing in {r['accessionNumber']: r for r in wanted}.values():
        url = document_url(cik, filing)
        raw, meta = archive.get(url)
        normalized, blocks = text_blocks(raw)
        text_hash = sha(normalized.encode())
        (archive.directory / 'objects' / text_hash).write_bytes(normalized.encode())
        candidates = biography_candidates(blocks, names) if filing == current else []
        documents.append({'filing': filing, 'source': meta, 'normalized_text_sha256': text_hash,
                          'normalizer': VERSION, 'block_count': len(blocks), 'biography_candidates': candidates})
    return {'version': VERSION, 'intake_record_id': record['id'], 'cik': cik, 'lineage': lineage,
            'metadata_artifacts': artifacts, 'documents': documents, 'publication_allowed': False,
            'remaining_gates': ['operating_company_review','field_passage_review','person_identity_and_relationship_review','biography_review','commercial_rights_review','release_manifest']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--intake', required=True, type=Path)
    parser.add_argument('--record-index', type=int, required=True)
    parser.add_argument('--archive-dir', type=Path, required=True)
    parser.add_argument('--fetch', action='store_true', help='Opt into live SEC retrieval; requires real SEC_EDGAR_USER_AGENT')
    parser.add_argument('--person', action='append', default=[], help='Exact person name to locate; no inferred aliases')
    args = parser.parse_args()
    from import_legacy import digest
    batch = json.loads(args.intake.read_text())
    if batch.get('payload_sha256') != digest({k: v for k, v in batch.items() if k != 'payload_sha256'}):
        parser.error('Intake payload hash mismatch')
    if args.record_index < 0 or args.record_index >= len(batch['records']):
        parser.error('Record index out of bounds')
    archive = Archive(args.archive_dir, args.fetch)
    record = batch['records'][args.record_index]
    names = args.person + [h['values']['name'] for h in record['holders'] if h['values'].get('holder_type') in ('individual', 'person')]
    packet = capture(record, archive, names)
    packet['intake_batch_id'] = batch['id']
    target = args.archive_dir / ('review-' + record['id'] + '.json')
    target.write_text(json.dumps(packet, indent=2) + '\n')
    print(json.dumps({'packet': str(target), 'documents': len(packet['documents']), 'biography_candidates': sum(len(d['biography_candidates']) for d in packet['documents']), 'publication_allowed': False}, indent=2))


if __name__ == '__main__':
    main()
