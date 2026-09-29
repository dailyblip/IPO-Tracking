"""Bounded SEC daily-index discovery and encrypted evidence capture.

Uses the existing isolated Actions contact, never a new credential or provider.
Dates discover exact identities; source eligibility and facts remain unreviewed.
No database writes, source publication, production scheduling or secret export.
"""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request
from zoneinfo import ZoneInfo

from actions_sec_capture import BoundedArchive, seal
from capture_sec_evidence import capture, load_history, resolve_lineage, sha
from commercial_discovery import build_queue, capture_request, parse_artifact, record_capture, record_capture_failure
from import_legacy import canonical

NY = ZoneInfo('America/New_York')
INDEX_LIMIT = 20_000_000
SAFE_INDEX_ERRORS = {
    'Capture budget exhausted': 'request_budget',
    'Index byte budget exhausted': 'byte_budget',
    'SEC index response was not HTTP 200': 'http_status',
    'Unexpected SEC index content type': 'content_type',
    'SEC response lacks master-index header': 'missing_header',
    'SEC retry requires a later run': 'retry_later',
    'Malformed SEC index data row': 'malformed_row',
    'SEC row outside index date or retrieval cutoff': 'row_date_conflict',
}


def validate_request(request, now=None):
    required = {'version', 'request_id', 'start', 'end', 'capture_limit', 'engine_baseline_commit'}
    if set(request) != required or request['version'] != 'sec-discovery-request/1':
        raise ValueError('Unsupported discovery request')
    if not isinstance(request['request_id'], str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', request['request_id']):
        raise ValueError('Invalid request identifier')
    start, end = date.fromisoformat(request['start']), date.fromisoformat(request['end'])
    today = (now or datetime.now(timezone.utc)).astimezone(NY).date()
    if start.isoformat() != request['start'] or end.isoformat() != request['end']:
        raise ValueError('Canonical dates required')
    if start > end or (end-start).days > 6 or end > today or start < date(2026, 1, 1):
        raise ValueError('Discovery requires at most seven authorized, nonfuture days')
    if type(request['capture_limit']) is not int or not 1 <= request['capture_limit'] <= 4:
        raise ValueError('Capture requires one to four filings')
    if not isinstance(request['engine_baseline_commit'], str) or not re.fullmatch(r'[a-f0-9]{40}', request['engine_baseline_commit']):
        raise ValueError('Exact engine baseline required')
    return start, end


def index_urls(start, end):
    day = start
    while day <= end:
        if day.weekday() < 5:
            yield f'https://www.sec.gov/Archives/edgar/daily-index/{day.year}/QTR{(day.month-1)//3+1}/master.{day:%Y%m%d}.idx'
        day += timedelta(days=1)


def get_index(archive, url):
    # Independent exact allowlist: generic filing capture stays unchanged.
    match = re.fullmatch(r'https://www\.sec\.gov/Archives/edgar/daily-index/(\d{4})/QTR([1-4])/master\.(\d{8})\.idx', url)
    if not match:
        raise ValueError('Canonical dated daily index required')
    day = datetime.strptime(match[3], '%Y%m%d').date()
    if day.year != int(match[1]) or (day.month-1)//3+1 != int(match[2]):
        raise ValueError('Index date/quarter conflict')
    for attempt in range(3):
        if archive.request_count >= 80 or archive.total_bytes >= 256_000_000:
            raise ValueError('Capture budget exhausted')
        time.sleep(max(0, 1-(time.monotonic()-archive.last_request)))
        archive.last_request = time.monotonic()
        archive.request_count += 1
        try:
            with archive.opener.open(Request(url, headers={'User-Agent': archive.agent, 'Accept-Encoding': 'identity'}), timeout=30) as response:
                if response.status != 200:
                    raise ValueError('SEC index response was not HTTP 200')
                raw = response.read(INDEX_LIMIT+1)
                kind = response.headers.get_content_type()
            break
        except HTTPError as exc:
            if exc.code not in (429, 503) or attempt == 2:
                raise
            delay = exc.headers.get('Retry-After', '2')
            if not delay.isdigit() or int(delay) > 30:
                raise ValueError('SEC retry requires a later run') from exc
            time.sleep(max(1, int(delay)))
    archive.total_bytes += len(raw)
    if len(raw) > INDEX_LIMIT or archive.total_bytes > 256_000_000:
        raise ValueError('Index byte budget exhausted')
    # Retain bounded responses privately for diagnosis, including access-denial
    # responses. Such bytes never become a verified index or candidate source.
    if hasattr(archive, 'directory'):
        rejected = archive.directory/'index-responses'
        rejected.mkdir(parents=True, exist_ok=True)
        (rejected/sha(raw)).write_bytes(raw)
        (rejected/(sha(raw)+'.json')).write_text(canonical(dict(url=url, content_type=kind, bytes=len(raw))))
    if kind not in ('text/plain', 'application/octet-stream', 'binary/octet-stream', 'text/html'):
        raise ValueError('Unexpected SEC index content type')
    if b'CIK|Company Name|Form Type|Date Filed|Filename' not in raw or b'<html' in raw.lower():
        raise ValueError('SEC response lacks master-index header')
    meta = dict(url=url, sha256=sha(raw), bytes=len(raw), retrieved_at=datetime.now(timezone.utc).isoformat())
    return raw, meta


def run(request, recipient, output):
    start, end = validate_request(request)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        archive = BoundedArchive(directory/'archive')
        artifacts, indexes, results = {}, [], []
        for url in index_urls(start, end):
            try:
                raw, meta = get_index(archive, url)
                relative = 'indexes/'+meta['sha256']+'.idx'
                (directory/'indexes').mkdir(exist_ok=True)
                (directory/relative).write_bytes(raw)
                parse_artifact(meta, raw, datetime.now(timezone.utc))
                artifacts[meta['sha256']] = raw
                indexes.append(dict(meta, path=relative))
                results.append(dict(url=url, status='captured'))
            except Exception as exc:
                results.append(dict(url=url, status='held', error_type=type(exc).__name__,
                                    reason_code=SAFE_INDEX_ERRORS.get(str(exc), 'unclassified_index_error'),
                                    http_status=exc.code if isinstance(exc, HTTPError) else None))
        spec = dict(version='commercial-discovery-input/1', start=request['start'], end=request['end'],
                    as_of=datetime.now(timezone.utc).isoformat(), engine_baseline_commit=request['engine_baseline_commit'], indexes=indexes)
        (directory/'discovery-input.json').write_text(canonical(spec))
        queue = build_queue(spec, artifacts)
        selected = capture_request(queue, request['capture_limit'])
        for row in selected['filings'] if selected else []:
            key = row['cik']+'/'+row['accession']
            entry = next(e for e in queue['entries'] if e['key'] == key)
            try:
                history, _ = load_history(archive, row['cik'])
                lineage = resolve_lineage(history, row['accession'])
                amendments = [f for f in lineage['history'] if f['form'] in ('S-1/A', 'F-1/A')]
                extra = [amendments[-1]['accessionNumber']] if amendments else []
                packet = capture(entry['intake']['records'][0], archive, [], extra)
                queue, bound = record_capture(queue, key, packet, archive.directory)
                (directory/('capture-'+row['accession']+'.json')).write_text(canonical(bound))
                results.append(dict(row, status='captured_review_pending'))
            except Exception as exc:
                queue = record_capture_failure(queue, key, type(exc).__name__)
                results.append(dict(row, status='held', error_type=type(exc).__name__))
        (directory/'discovery-queue.json').write_text(canonical(queue))
        files = {str(p.relative_to(directory)): dict(sha256=sha(p.read_bytes()), bytes=p.stat().st_size)
                 for p in sorted(directory.rglob('*')) if p.is_file()}
        manifest = dict(version='sec-actions-discovery/1', request=request, results=results,
                        retrieved_at=datetime.now(timezone.utc).isoformat(), files=files,
                        publication_allowed=False, eligibility='unreviewed')
        (directory/'manifest.json').write_text(canonical(manifest))
        seal(directory, recipient, output/'evidence.cms')
    # No filing names, raw sources, contact, headers or private facts in job logs.
    print(json.dumps(dict(indexes=len(indexes), candidates=len(queue['entries']),
                          captured=sum(r['status']=='captured_review_pending' for r in results),
                          retrieval_holds=sum(r['status']=='held' for r in results),
                          coverage=queue['coverage']['status'], encrypted=True, publication_allowed=False)))
    return 1 if any(r['status']=='held' for r in results) else 0
