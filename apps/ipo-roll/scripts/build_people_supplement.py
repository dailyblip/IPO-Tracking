"""Append explicitly reviewed people/biographies to an existing staging offering.

Discovery never approves people. Reviews must bind a named individual, relationship
and optional complete biography to exact captured passages. No holdings or wealth
are inferred. Existing identities/evidence must match; conflicting imports fail.
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path
from build_internal_pilot import uid
from discover_people import discover
from capture_sec_evidence import sha, text_blocks
from import_legacy import canonical
from prepare_sec_review import literal, passage, read_object


def flat(value):
    return re.sub(r'\s+', ' ', value).strip()




def build(packet, review, directory):
    current, root = packet['lineage']['current'], packet['lineage']['root']
    if packet['lineage']['status'] != 'metadata_resolved':
        raise ValueError('Resolved filing lineage required')
    docs = [d for d in packet['documents'] if d['filing'] == current]
    if len(docs) != 1:
        raise ValueError('Exactly one captured current document required')
    doc = docs[0]
    text, blocks = text_blocks(read_object(directory, doc['source']['content_sha256']))
    if sha(text.encode()) != doc['normalized_text_sha256']:
        raise ValueError('Normalized snapshot mismatch')
    reviewed_on = date.fromisoformat(review['reviewed_on'])
    if not date.fromisoformat(current['filingDate']) <= reviewed_on <= date.today():
        raise ValueError('Invalid review date')
    cik = packet['cik']
    offering = uid('offering', cik, root['accessionNumber'])
    document = uid('document', doc['source']['content_sha256'])
    filing = uid('filing', current['accessionNumber'])
    spans, people, seen = {}, [], set()
    def selected(spec):
        data = passage(blocks, spec['first'], spec['last'], text)
        sid = uid('people-supplement-span', document, canonical(data))
        spans[sid] = data
        return sid, flat(data['excerpt'])
    for p in review['people']:
        name = p['name']
        if not isinstance(name, str) or not 3 <= len(name) <= 180 or name in seen or not p.get('identity_reviewed'):
            raise ValueError('Explicit unique individual identity review required')
        seen.add(name)
        if p['relationship'] not in ('Executive', 'Director', 'Beneficial owner'):
            raise ValueError('Unsupported relationship')
        sid, body = selected(p['relationship_evidence'])
        relationship_name = p.get('relationship_name', name)
        if relationship_name != name and (p.get('alias_reviewed') is not True or
                                         not isinstance(p.get('alias_reason'), str) or
                                         not p['alias_reason'].strip()):
            raise ValueError('Alternate relationship name requires explicit alias review')
        if not isinstance(relationship_name, str) or len(relationship_name.strip()) < 3:
            raise ValueError('Literal relationship name required')
        if relationship_name not in body or not p['title'] or p['title'].casefold() not in body.casefold():
            raise ValueError('Name/title missing from relationship evidence')
        bio = None
        if p.get('biography'):
            bio, body = selected(p['biography'])
            if not p.get('biography_complete_reviewed') or not re.match(re.escape(name)+r'(?:\s|[,.:])', body):
                raise ValueError('Complete person-specific biography review required')
        elif p.get('biography_status') != 'not_found_in_reviewed_filing':
            raise ValueError('Missing biography must be explicitly accounted for')
        people.append(dict(name=name,person_id=uid('person-in-issuer',cik,name),
                           title=p['title'],relationship=p['relationship'],
                           relationship_span=sid,biography_span=bio))
    if not people:
        raise ValueError('Empty supplement')
    manifest = dict(version='people-supplement/1',offering_id=offering,
                    source_sha256=doc['source']['content_sha256'],document_id=document,
                    normalized_sha256=doc['normalized_text_sha256'],review=review,
                    people=people,spans=spans,audience='internal_review',published=False)
    body = canonical(manifest)
    release = uid('people-supplement',sha(body.encode()))
    q = literal
    tag = '$people_' + sha(body.encode()) + '$'
    if tag in body:
        raise ValueError('SQL delimiter collision')
    lines = ['begin;', f'do {tag} declare parent_run uuid; packet_id uuid; begin',
        f"if exists(select 1 from ops.pilot_manifests where release_id='{release}') then if not exists(select 1 from ops.pilot_manifests where release_id='{release}' and manifest={q(body)}::jsonb) then raise exception 'Manifest conflict'; end if; return; end if;",
        f"if not exists(select 1 from research.offerings o join research.companies c on c.id=o.company_id join evidence.documents d on d.source_id=o.source_id join research.filings f on f.id=o.current_filing_id where o.id='{offering}' and c.cik={q(cik)} and o.current_filing_id='{filing}' and f.file_number={q(current['fileNumber'])} and d.id='{document}' and d.content_sha256={q(doc['source']['content_sha256'])} and o.audience='internal_review' and not o.published) then raise exception 'Canonical source or lineage mismatch'; end if;",
        f"select r.run_id,m.review_packet_id into strict parent_run,packet_id from research.offerings o join ops.releases r on r.id=o.release_id join ops.pilot_manifests m on m.release_id=r.id where o.id='{offering}';"]
    for sid, data in spans.items():
        lines += [f"insert into evidence.spans(id,document_id,excerpt,locator,approved) values('{sid}','{document}',{q(data['excerpt'])},{q(canonical(data['locator']))},true) on conflict do nothing;",
                  f"if not exists(select 1 from evidence.spans where id='{sid}' and document_id='{document}' and excerpt={q(data['excerpt'])} and locator={q(canonical(data['locator']))} and approved) then raise exception 'Evidence conflict'; end if;"]
    for p in people:
        pid, rel = p['person_id'], p['relationship_span']
        rid = uid('role',pid,offering,p['relationship'])
        lines += [f"insert into research.parties(id,name,kind) values('{pid}',{q(p['name'])},'person') on conflict do nothing;",
                  f"if not exists(select 1 from research.parties where id='{pid}' and name={q(p['name'])} and kind='person') then raise exception 'Party conflict'; end if;",
                  f"insert into research.people(id,identity_verified) values('{pid}',true) on conflict do nothing;",
                  f"if not exists(select 1 from research.people where id='{pid}' and identity_verified) then raise exception 'Identity conflict'; end if;",
                  f"insert into research.roles(id,person_id,offering_id,title,relationship,evidence_id,verified) values('{rid}','{pid}','{offering}',{q(p['title'])},{q(p['relationship'])},'{rel}',true) on conflict do nothing;",
                  f"if not exists(select 1 from research.roles where id='{rid}' and person_id='{pid}' and offering_id='{offering}' and title={q(p['title'])} and relationship={q(p['relationship'])} and evidence_id='{rel}' and verified) then raise exception 'Role conflict'; end if;"]
        if p['biography_span']:
            sid = p['biography_span']
            bid = uid('biography',pid,document)
            claim = uid('claim',bid,'biography_text')
            lines += [f"insert into research.biographies(id,person_id,span_id,approved) values('{bid}','{pid}','{sid}',true) on conflict do nothing;",
                      f"if not exists(select 1 from research.biographies where id='{bid}' and person_id='{pid}' and span_id='{sid}' and approved) then raise exception 'Biography conflict'; end if;",
                      f"insert into research.claims(id,biography_id,predicate,object_text,evidence_id,verified) values('{claim}','{bid}','biography_text',{q(flat(spans[sid]['excerpt']))},'{sid}',true) on conflict do nothing;",
                      f"if not exists(select 1 from research.claims where id='{claim}' and biography_id='{bid}' and predicate='biography_text' and object_text={q(flat(spans[sid]['excerpt']))} and evidence_id='{sid}' and verified) then raise exception 'Claim conflict'; end if;"]
    lines += [f"insert into ops.releases(id,run_id) values('{release}',parent_run);",
              f"insert into ops.pilot_manifests(release_id,review_packet_id,manifest) values('{release}',packet_id,{q(body)}::jsonb);",
              f'end {tag};', 'commit;']
    return manifest, '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('packet','review','archive-dir','output-dir'):
        parser.add_argument('--'+key,type=Path,required=True)
    args = parser.parse_args()
    manifest, sql = build(json.loads(args.packet.read_text()),json.loads(args.review.read_text()),args.archive_dir)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (args.output_dir/'people.sql').write_text(sql)
    print(json.dumps(dict(people=len(manifest['people']),biographies=sum(bool(p['biography_span']) for p in manifest['people']),published=False)))
