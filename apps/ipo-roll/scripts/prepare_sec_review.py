"""Select explicit source passages and export a private, immutable staging packet.

No guessed span boundaries, publication grants, inferred claims or database connection.
"""
import argparse
import base64
import gzip
import json
from pathlib import Path
import re
import uuid
from capture_sec_evidence import sha, text_blocks
from import_legacy import canonical


def read_object(directory, checksum):
    if not isinstance(checksum, str) or not re.fullmatch(r'[a-f0-9]{64}', checksum):
        raise ValueError('Invalid object hash')
    raw = (directory / 'objects' / checksum).read_bytes()
    if sha(raw) != checksum:
        raise ValueError('Artifact checksum mismatch')
    return raw


def passage(blocks, first, last, text):
    if type(first) is not int or type(last) is not int or not 0 <= first <= last < len(blocks):
        raise ValueError('Invalid passage boundaries')
    start, end = blocks[first]['start'], blocks[last]['end']
    excerpt = text[start:end]
    if len(excerpt) > 12000 or re.search(r'stanford|#8c1515', excerpt, re.I):
        raise ValueError('Passage requires commercial content review')
    return {'excerpt': excerpt, 'locator': {'first_block': first, 'last_block': last, 'start': start, 'end': end}}


def prepare(packet, selections, directory):
    result = {'version': 'sec-selected-review/1', 'capture': packet, 'people': [],
              'rights_status': 'unreviewed', 'publication_allowed': False}
    current = packet['lineage']['current']['accessionNumber']
    documents = [d for d in packet['documents'] if d['filing']['accessionNumber'] == current]
    if len(documents) != 1:
        raise ValueError('Exactly one captured current document required')
    document = documents[0]
    normalized, blocks = text_blocks(read_object(directory, document['source']['content_sha256']))
    if sha(normalized.encode()) != document['normalized_text_sha256']:
        raise ValueError('Normalizer version or snapshot mismatch')
    for s in selections:
        bio = passage(blocks, s['first_block'], s['last_block'], normalized)
        relation = passage(blocks, s['relationship_first_block'], s['relationship_last_block'], normalized)
        if not (s['first_block'] <= s['relationship_first_block'] <= s['relationship_last_block'] <= s['last_block']):
            raise ValueError('Relationship passage must be inside selected biography')
        text = re.sub(r'\s+', ' ', bio['excerpt'])
        if not text.startswith(s['name'] + ' ') or s['name'] not in relation['excerpt']:
            raise ValueError('Explicit person name missing from biography/relationship evidence')
        if s['relationship'] not in ('Executive', 'Director', 'Beneficial owner'):
            raise ValueError('Unsupported relationship')
        if s['title'] not in re.sub(r'\s+', ' ', relation['excerpt']):
            raise ValueError('Title must be literal in selected relationship evidence')
        terms = s.get('search_terms', [])
        if not all(isinstance(term, str) and len(term) >= 2 and term.casefold() in text.casefold() for term in terms):
            raise ValueError('Search term not explicitly present in biography')
        result['people'].append({'name': s['name'], 'title': s['title'], 'relationship': s['relationship'],
                                 'biography': bio, 'relationship_evidence': relation,
                                 'literal_search_terms': terms, 'source': document['source'],
                                 'normalized_text_sha256': document['normalized_text_sha256'],
                                 'review_status': 'source_selected', 'identity_status': 'unverified', 'approved': False})
    digest = sha(canonical(result).encode())
    return {**result, 'sha256': digest, 'id': str(uuid.uuid5(uuid.NAMESPACE_URL, 'ipo-roll:sec-review:' + digest))}


def artifacts(packet, directory):
    hashes = {m['content_sha256'] for m in packet['metadata_artifacts']}
    for d in packet['documents']:
        hashes.update((d['source']['content_sha256'], d['normalized_text_sha256']))
    for checksum in sorted(hashes):
        raw = read_object(directory, checksum)
        yield checksum, len(raw), base64.b64encode(gzip.compress(raw, mtime=0)).decode()


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def export_sql(review, directory):
    lines = ['begin;']
    for checksum, size, encoded in artifacts(review['capture'], directory):
        lines.append(f"insert into ops.sec_artifacts(sha256,raw_bytes,content_gzip) values('{checksum}',{size},decode('{encoded}','base64')) on conflict do nothing;")
    body = canonical(review)
    rid, record_id = review['id'], review['capture']['intake_record_id']
    uuid.UUID(record_id)
    uuid.UUID(rid)
    tag = '$review_' + sha(body.encode()) + '$'
    if tag in body:
        raise ValueError('SQL delimiter collision')
    lines.append(f"insert into ops.sec_review_packets(id,intake_record_id,packet_sha256,packet) values('{rid}','{record_id}','{review['sha256']}',{literal(body)}::jsonb) on conflict do nothing;")
    lines.append(f"do {tag} begin if not exists(select 1 from ops.sec_review_packets where id='{rid}' and packet={literal(body)}::jsonb) then raise exception 'Immutable packet conflict'; end if; end {tag};")
    for checksum, _, _ in artifacts(review['capture'], directory):
        lines.append(f"insert into ops.sec_packet_artifacts(packet_id,artifact_sha256) values('{rid}','{checksum}') on conflict do nothing;")
    lines.extend(['commit;', f"select id, jsonb_array_length(packet->'people') people from ops.sec_review_packets where id='{rid}';"])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--selections', type=Path, required=True)
    parser.add_argument('--archive-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    review = prepare(json.loads(args.packet.read_text()), json.loads(args.selections.read_text()), args.archive_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir/'selected-review.json').write_text(json.dumps(review, indent=2)+'\n')
    (args.output_dir/'selected-review.sql').write_text(export_sql(review, args.archive_dir))
    print(json.dumps({'packet_id': review['id'], 'people': len(review['people']), 'publication_allowed': False}))


if __name__ == '__main__':
    main()
