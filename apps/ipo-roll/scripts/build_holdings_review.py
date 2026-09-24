"""Offline, explicit projected-position review; never derives current wealth.

Reuses the existing captured-document normalizer and canonical identity namespace.
Generated SQL is private, administrative, transactional and replay-safe. It does
not contact SEC, alter entitlements, publish data or generate customer reports.
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path
from build_internal_pilot import uid
from capture_sec_evidence import sha, text_blocks
from import_legacy import canonical
from prepare_sec_review import read_object, passage, literal


def flat(value):
    return re.sub(r'\s+', ' ', value).strip()


def build(packet, review, directory):
    current = packet['lineage']['current']
    if packet['lineage']['status'] != 'metadata_resolved' or current['form'] not in ('S-1/A', 'S-1', 'F-1', 'F-1/A'):
        raise ValueError('Only reviewed preliminary projected positions are supported')
    docs = [d for d in packet['documents'] if d['filing'] == current]
    if len(docs) != 1:
        raise ValueError('Exactly one current captured document required')
    doc = docs[0]
    raw = read_object(directory, doc['source']['content_sha256'])
    text, blocks = text_blocks(raw)
    if sha(text.encode()) != doc['normalized_text_sha256']:
        raise ValueError('Normalized snapshot mismatch')
    reviewed_on = date.fromisoformat(review['reviewed_on'])
    if not date.fromisoformat(current['filingDate']) <= reviewed_on <= date.today():
        raise ValueError('Invalid review date')
    def select(spec):
        return passage(blocks, spec['first'], spec['last'], text)
    headers, basis, restriction = [select(review[k]) for k in ('headers','basis','restriction')]
    if 'Shares of Common Stock Beneficially Owned After this Offering' not in flat(headers['excerpt']) or 'Shares of Class A Common Stock' not in flat(headers['excerpt']):
        raise ValueError('Projected Class A column evidence required')
    if 'after the offering' not in flat(basis['excerpt']).lower():
        raise ValueError('Projected position assumptions required')
    if not review['restriction_literal'] or review['restriction_literal'] not in flat(restriction['excerpt']):
        raise ValueError('Restriction passage mismatch')
    if not all(term in flat(restriction['excerpt']) for term in ('will sign lock-up agreements', 'not less than 180 days', 'prior written consent', 'subject to certain exceptions')):
        raise ValueError('This preliminary review requires the supported conditional lock-up wording')
    cik = packet['cik']
    offering = uid('offering', cik, packet['lineage']['root']['accessionNumber'])
    document = uid('document', doc['source']['content_sha256'])
    filing = uid('filing', current['accessionNumber'])
    spans = {}
    def span(data):
        key = uid('holdings-span', document, canonical(data))
        spans[key] = data
        return key
    common = [span(x) for x in (headers,basis,restriction)]
    positions = []
    seen = set()
    for item in review['positions']:
        name = item['name']
        if name in seen:
            raise ValueError('Duplicate person position')
        seen.add(name)
        row, note = select(item['row']), select(item['footnote'])
        marker = str(item['footnote_number'])
        if not flat(row['excerpt']).startswith(name + '(' + marker + ')') or not flat(note['excerpt']).startswith('(' + marker + ')'):
            raise ValueError('Row identity or footnote association mismatch')
        if 'trust' not in flat(note['excerpt']).lower():
            raise ValueError('This review path requires explicit trust-component evidence')
        n = item['shares']
        if type(n) is not int or not 0 < n <= 9007199254740991:
            raise ValueError('Unsupported share count')
        index = item['share_block']
        if type(index) is not int or not item['row']['first'] <= index <= item['row']['last']:
            raise ValueError('Share cell outside selected row')
        if text[blocks[index]['start']:blocks[index]['end']] != f'{n:,}':
            raise ValueError('Selected share cell does not match count')
        person = uid('person-in-issuer', cik, name)
        oid = uid('holding-review', document, person, 'projected-A')
        positions.append(dict(id=oid,person_id=person,name=name,shares=n,row=span(row),evidence=common+[span(note)],source_row_key='reviewed-projected-A:'+person))
    if not positions:
        raise ValueError('No explicitly reviewed positions')
    manifest = dict(version='holdings-review/1',offering_id=offering,document_id=document,source_sha256=doc['source']['content_sha256'],normalized_sha256=doc['normalized_text_sha256'],review=review,positions=positions,spans=spans,published=False,audience='internal_review')
    release = uid('holdings-release',sha(canonical(manifest).encode()))
    q = literal
    stmts = ['begin;', 'do $holdings$ declare parent_run uuid; packet_id uuid; begin',
        f"if exists(select 1 from ops.pilot_manifests where release_id='{release}') then if not exists(select 1 from ops.pilot_manifests where release_id='{release}' and manifest={q(canonical(manifest))}::jsonb) then raise exception 'Manifest conflict'; end if; return; end if;",
        f"if not exists(select 1 from research.offerings o join evidence.documents d on d.source_id=o.source_id join research.filings f on f.id=o.current_filing_id where o.id='{offering}' and o.current_filing_id='{filing}' and f.file_number={q(current['fileNumber'])} and d.id='{document}' and d.content_sha256={q(doc['source']['content_sha256'])} and o.audience='internal_review' and not o.published) then raise exception 'Canonical source or lineage mismatch'; end if;",
        f"select r.run_id,m.review_packet_id into strict parent_run,packet_id from research.offerings o join ops.releases r on r.id=o.release_id join ops.pilot_manifests m on m.release_id=r.id where o.id='{offering}';"]
    for sid,data in spans.items():
        stmts += [f"insert into evidence.spans(id,document_id,excerpt,locator,approved) values('{sid}','{document}',{q(data['excerpt'])},{q(canonical(data['locator']))},true) on conflict do nothing;",
                  f"if not exists(select 1 from evidence.spans where id='{sid}' and document_id='{document}' and excerpt={q(data['excerpt'])} and locator={q(canonical(data['locator']))} and approved) then raise exception 'Evidence conflict'; end if;"]
    for p in positions:
        pid,oid=p['person_id'],p['id']
        stmts += [f"if not exists(select 1 from research.parties p join research.people pp on pp.id=p.id join research.roles r on r.person_id=p.id where p.id='{pid}' and p.name={q(p['name'])} and pp.identity_verified and r.offering_id='{offering}' and r.verified) then raise exception 'Person identity mismatch'; end if;",
            f"insert into research.ownerships(id,offering_id,party_id,filing_id,share_class,position_basis,shares,source_row_key,evidence_id,approved) values('{oid}','{offering}','{pid}','{filing}','Class A common stock','post',{p['shares']},{q(p['source_row_key'])},'{p['row']}',true);",
            f"insert into research.liquidity_assessments(ownership_id,reviewed,assessed_on,valid_through,classification,explanation,conditions,evidence_ids) values('{oid}',true,'{reviewed_on}','{reviewed_on}','unknown',",
            q('Projected post-offering position, not confirmed current holdings. The total includes a trust component described in the footnote; personal economic ownership of the entire position is unconfirmed.')+','+
            q('The preliminary filing describes planned lock-ups of not less than 180 days from the prospectus date, subject to underwriter consent and exceptions. No executed lock-up start, release date or present saleability is confirmed. Offering assumptions and ownership footnotes are retained below.')+
            ",array["+','.join(q(e)+'::uuid' for e in p['evidence'])+"]);"]
    stmts += [f"insert into ops.releases(id,run_id) values('{release}',parent_run);",
              f"insert into ops.pilot_manifests(release_id,review_packet_id,manifest) values('{release}',packet_id,{q(canonical(manifest))}::jsonb);",
              'end $holdings$;', 'commit;']
    return manifest,'\n'.join(stmts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('packet','review','archive-dir','output-dir'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    manifest,sql=build(json.loads(args.packet.read_text()),json.loads(args.review.read_text()),args.archive_dir)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'holdings.sql').write_text(sql)
    (args.output_dir/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'positions':len(manifest['positions']),'spans':len(manifest['spans']),'published':False}))
