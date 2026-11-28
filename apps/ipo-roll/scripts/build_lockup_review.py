"""Offline source-selected conditional lock-up timeline for existing reviewed positions.

Never changes liquidity classifications, existing private reports or access grants.
Final 424B4/dated-pre-common path only; unsupported triggers remain held for review.
"""
import argparse
import json
from datetime import date
from pathlib import Path
from build_internal_pilot import uid
from build_holdings_review import build as build_holdings
from capture_sec_evidence import sha, text_blocks
from import_legacy import canonical
from prepare_sec_review import read_object, passage, literal
from review_lockup import review_terms


def build(packet, holdings_manifest, review, archive):
    if holdings_manifest['review'].get('profile') != 'dated-pre-common':
        raise ValueError('Only reviewed dated common-share positions supported')
    rebuilt, _ = build_holdings(packet, holdings_manifest['review'], archive)
    if rebuilt != holdings_manifest:
        raise ValueError('Holdings source manifest mismatch')
    current = packet['lineage']['current']
    doc = next(d for d in packet['documents'] if d['filing'] == current)
    normalized, blocks = text_blocks(read_object(archive, doc['source']['content_sha256']))
    if sha(normalized.encode()) != doc['normalized_text_sha256']:
        raise ValueError('Normalized snapshot mismatch')
    reviewed = date.fromisoformat(review['reviewed_on'])
    if not date.fromisoformat(review['trigger_date']) <= date.fromisoformat(current['filingDate']) <= reviewed <= date.today():
        raise ValueError('Invalid trigger, filing or review date')
    if review['cover']['first'] != 0 or review['cover']['last'] > 60:
        raise ValueError('Use complete opening cover, not a date elsewhere in the filing')
    spans = {}
    selected = {}
    for kind in ('cover', 'definition', 'scope', 'exceptions'):
        spec = review[kind]
        item = passage(blocks, spec['first'], spec['last'], normalized)
        selected[kind] = item
        spans[uid('lockup-span', holdings_manifest['document_id'], canonical(item))] = item
    terms = review_terms(*(selected[k]['excerpt'] for k in ('cover','definition','scope','exceptions')),
                         review['trigger_date'], review['days'])
    manifest = dict(version='lockup-review/1', holdings_release_id=uid('holdings-release',sha(canonical(holdings_manifest).encode())),
                    document_id=holdings_manifest['document_id'], source_sha256=holdings_manifest['source_sha256'],
                    offering_id=holdings_manifest['offering_id'], review=review, terms=terms,
                    positions=holdings_manifest['positions'], spans=spans, published=False,audience='internal_review')
    release = uid('lockup-release',sha(canonical(manifest).encode()))
    q=literal
    stmts=['begin;', 'do $lockup$ declare parent_run uuid; packet_id uuid; begin',
           f"if exists(select 1 from ops.pilot_manifests where release_id='{release}') then if not exists(select 1 from ops.pilot_manifests where release_id='{release}' and manifest={q(canonical(manifest))}::jsonb) then raise exception 'Manifest conflict'; end if; return; end if;",
           f"select r.run_id,m.review_packet_id into strict parent_run,packet_id from ops.releases r join ops.pilot_manifests m on m.release_id=r.id where r.id='{manifest['holdings_release_id']}' and m.manifest={q(canonical(holdings_manifest))}::jsonb;",
           f"if not exists(select 1 from research.offerings o where o.id='{manifest['offering_id']}' and o.current_filing_id='{uid('filing',current['accessionNumber'])}' and not o.published and o.audience='internal_review') then raise exception 'Offering source changed'; end if;"]
    for sid,sp in spans.items():
        stmts += [f"insert into evidence.spans(id,document_id,excerpt,locator,approved) values('{sid}','{manifest['document_id']}',{q(sp['excerpt'])},{q(canonical(sp['locator']))},true) on conflict do nothing;",
                  f"if not exists(select 1 from evidence.spans where id='{sid}' and document_id='{manifest['document_id']}' and excerpt={q(sp['excerpt'])} and locator={q(canonical(sp['locator']))} and approved) then raise exception 'Evidence conflict'; end if;"]
    evidence='array['+','.join(q(s)+'::uuid' for s in spans)+']'
    for p in manifest['positions']:
        oid=p['id']; pid=p['person_id']
        stmts += [f"if not exists(select 1 from research.ownerships h join evidence.spans s on s.id=h.evidence_id join research.parties p on p.id=h.party_id join research.people pp on pp.id=p.id where h.id='{oid}' and h.party_id='{pid}' and p.name={q(p['name'])} and pp.identity_verified and h.offering_id='{manifest['offering_id']}' and h.filing_id='{uid('filing',current['accessionNumber'])}' and h.approved and h.shares={p['shares']} and h.share_class={q(p['share_class'])} and h.quantity_kind='reported_shares' and h.position_basis='pre' and h.holdings_as_of={q(p['holdings_as_of'])} and s.document_id='{manifest['document_id']}' and exists(select 1 from research.roles r where r.person_id=p.id and r.offering_id=h.offering_id and r.verified and r.relationship in ('Executive','Director'))) then raise exception 'Reviewed position or executive/director identity mismatch'; end if;",
            f"insert into research.lockup_terms(id,ownership_id,trigger_date,day_count,reviewed_on,conditions,evidence_ids,approved) values('{uid('lockup-term',oid,manifest['document_id'])}','{oid}',{q(terms['trigger_date'])},{terms['day_count']},{q(review['reviewed_on'])},{q(terms['conditions'])},{evidence},true);"]
    stmts += [f"insert into ops.releases(id,run_id) values('{release}',parent_run);",f"insert into ops.pilot_manifests(release_id,review_packet_id,manifest) values('{release}',packet_id,{q(canonical(manifest))}::jsonb);",'end $lockup$;','commit;']
    return manifest,'\n'.join(stmts)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('packet','holdings-manifest','review','archive-dir','output-dir'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    manifest,sql=build(json.loads(args.packet.read_text()),json.loads(args.holdings_manifest.read_text()),json.loads(args.review.read_text()),args.archive_dir)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'lockup.sql').write_text(sql)
    (args.output_dir/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'positions':len(manifest['positions']),'spans':len(manifest['spans']),'boundary':manifest['terms']['boundary_date'],'published':False}))
