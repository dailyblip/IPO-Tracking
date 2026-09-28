"""Import explicitly reviewed ownership-table quantities independently of liquidity.

Every complete source row and ordered numeric cell is compared literally. This
does not discover/approve identities or interpret awards, conversion, cash or
saleability. Totals remain beneficial totals with incomplete decomposition until
a separate review. Zero and an undisclosed dash are deliberately different.
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path
from html.parser import HTMLParser
from build_internal_pilot import uid
from capture_sec_evidence import sha, text_blocks
from import_legacy import canonical
from prepare_sec_review import passage, read_object, literal
from build_people_supplement import flat


def table_rows(raw):
    """Retain HTML cell boundaries when normalized text glued adjacent numbers."""
    class Rows(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True); self.stack=[]; self.rows=[]
        def handle_starttag(self,tag,attrs):
            if tag=='tr': self.stack.append(dict(cells=[],depth=0,parts=[]))
            if tag in ('td','th'):
                for row in self.stack:
                    row['depth']+=1
                    if row['depth']==1: row['parts']=[]
        def handle_data(self,data):
            for row in self.stack:
                if row['depth']: row['parts'].append(data)
        def handle_endtag(self,tag):
            if tag in ('td','th'):
                for row in self.stack:
                    if row['depth']:
                        row['depth']-=1
                        if row['depth']==0: row['cells'].append(flat(' '.join(row['parts'])))
            if tag=='tr' and self.stack:
                self.rows.append(flat(' '.join(self.stack.pop()['cells'])))
    parser=Rows(); parser.feed(raw.decode('utf-8',errors='replace')); return parser.rows


def quantity(cell):
    if cell in ('—', '–', '-'): return None
    if not re.fullmatch(r'(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)', cell):
        raise ValueError('Invalid quantity cell')
    n = int(cell.replace(',', ''))
    if n > 9007199254740991: raise ValueError('Unsafe quantity')
    return n


def build(packet, review, directory):
    current = packet['lineage']['current']
    if packet['lineage']['status'] != 'metadata_resolved':
        raise ValueError('Resolved lineage required')
    docs = [d for d in packet['documents'] if d['filing'] == current]
    if len(docs) != 1: raise ValueError('Exactly one current document required')
    doc = docs[0]; source = doc['source']['content_sha256']
    raw=read_object(directory, source); text, blocks = text_blocks(raw)
    html_rows=table_rows(raw)
    if sha(text.encode()) != doc['normalized_text_sha256']: raise ValueError('Normalized source mismatch')
    reviewed = date.fromisoformat(review['reviewed_on'])
    if not date.fromisoformat(current['filingDate']) <= reviewed <= date.today():
        raise ValueError('Invalid review date')
    if review.get('column_order_reviewed') is not True or not review.get('basis_review'):
        raise ValueError('Explicit ordered column and table-basis review required')
    cik = packet['cik']; offering = uid('offering', cik, packet['lineage']['root']['accessionNumber'])
    document = uid('document', source); filing = uid('filing', current['accessionNumber'])
    spans = {}
    def selected(spec):
        data = passage(blocks, spec['first'], spec['last'], text)
        sid = uid('disclosed-table-span', document, canonical(data)); spans[sid] = data
        return sid, flat(data['excerpt'])
    header, header_text = selected(review['headers'])
    basis, basis_text = selected(review['basis'])
    common = [header, basis]
    as_of = review.get('holdings_as_of')
    if as_of:
        dt = date.fromisoformat(as_of)
        if dt > date.fromisoformat(current['filingDate']): raise ValueError('Future holdings date')
        date_text = dt.strftime('%B') + f' {dt.day}, {dt.year}'
        if date_text not in basis_text:
            if 'as of the date of this prospectus' not in basis_text:
                raise ValueError('Explicit as-of date or prospectus-date bridge required')
            ds, body = selected(review['prospectus_date'])
            if date_text not in body: raise ValueError('Prospectus date mismatch')
            common.append(ds)
    columns = review['columns']
    keys = [c['key'] for c in columns]
    if len(keys) != len(set(keys)) or not columns: raise ValueError('Unique ordered columns required')
    scenarios = [(c.get('position_basis'), c.get('share_class')) for c in columns if c['kind'] == 'quantity']
    if len(scenarios) != len(set(scenarios)):
        raise ValueError('Alternative quantities on the same basis/class require separate scenario review')
    for c in columns:
        if c['kind'] not in ('quantity','percent','proposed_sale','unselected_quantity'): raise ValueError('Unsupported column')
        if c['kind'] == 'unselected_quantity' and not c.get('not_imported_reason'):
            raise ValueError('Unselected scenario quantity requires a reason')
        if c['kind'] == 'quantity':
            if c['position_basis'] not in ('pre','post'): raise ValueError('Explicit pre/post basis required')
            if not c['header_literal'] or c['header_literal'] not in header_text:
                raise ValueError('Column header evidence mismatch')
    positions = []; names = set()
    reviewed_non_imported_rows = []
    for omitted in review.get('reviewed_non_imported_rows', []):
        if not omitted.get('reason') or not omitted.get('source_label'):
            raise ValueError('Reviewed non-imported row requires a label and reason')
        sid, row = selected(omitted['row'])
        expected = flat(omitted['source_label'] + ' ' + ' '.join(omitted['cells']))
        occurrences = omitted.get('row_occurrence_count', 1)
        if not isinstance(occurrences, int) or occurrences < 1:
            raise ValueError('Reviewed non-imported row occurrence count must be positive')
        if re.sub(r'\s', '', row) != re.sub(r'\s', '', expected) or html_rows.count(expected) != occurrences:
            raise ValueError('Reviewed non-imported whole row mismatch')
        reviewed_non_imported_rows.append(dict(
            source_label=omitted['source_label'], cells=omitted['cells'],
            reason=omitted['reason'], evidence=sid))
    for person in review['people']:
        name = person['name']; label = person['source_label']
        if name in names or not person.get('identity_reviewed'): raise ValueError('Unique reviewed identity required')
        names.add(name)
        party_kind = person.get('party_kind', 'person')
        if party_kind not in ('person','organization','group','unresolved'):
            raise ValueError('Unsupported party kind')
        if label != name and (person.get('alias_reviewed') is not True or not person.get('alias_reason')):
            raise ValueError('Source label/alias review required')
        sid, row = selected(person['row']); cells = person['cells']
        expected=flat(label + ' ' + ' '.join(cells))
        occurrences = person.get('row_occurrence_count', 1)
        if (not isinstance(occurrences, int) or occurrences < 1 or len(cells) != len(columns)
                or re.sub(r'\s','',row)!=re.sub(r'\s','',expected)
                or html_rows.count(expected)!=occurrences):
            raise ValueError('Whole source row / ordered cells mismatch')
        for c, cell in zip(columns, cells):
            if c['kind'] in ('quantity','proposed_sale','unselected_quantity'): quantity(cell)
            elif not re.fullmatch(r'(?:(?:100(?:\.0+)?|\d{1,2}(?:\.\d+)?)\s*%?|\*\s*%?|[—–-])', cell):
                raise ValueError('Invalid percent cell')
        notes = [selected(spec)[0] for spec in person.get('footnotes', [])]
        person_security = person.get('share_class')
        evidence_text = ' '.join([header_text,basis_text]+[flat(spans[n]['excerpt']) for n in notes]).casefold()
        securities = {c.get('share_class', person_security) for c in columns if c['kind'] == 'quantity'}
        if None in securities or any(not security or security.casefold() not in evidence_text for security in securities):
            raise ValueError('Each imported security class must appear in selected evidence')
        if not person.get('interpretation_note'): raise ValueError('Explicit row limitations required')
        pid = uid('person-in-issuer', cik, name) if party_kind == 'person' else uid('party-in-issuer', cik, party_kind, name)
        quantity_keys = {c['key'] for c in columns if c['kind'] == 'quantity'}
        selected_quantity_keys = set(person.get('import_quantity_keys', quantity_keys))
        if not selected_quantity_keys or not selected_quantity_keys <= quantity_keys:
            raise ValueError('Imported quantity keys must select reviewed quantity columns')
        if selected_quantity_keys != quantity_keys and not person.get('not_imported_quantity_reason'):
            raise ValueError('Partially imported row requires a quantity omission reason')
        attributions = []
        for item in person.get('attributions', []):
            if party_kind == 'person':
                raise ValueError('Direct person row cannot also be an attributed entity row')
            if item.get('kind') not in ('beneficial_entitlement','control_authority','reported_beneficial_owner'):
                raise ValueError('Unsupported ownership attribution')
            if not item.get('identity_reviewed') or not item.get('description'):
                raise ValueError('Attributed person identity and limitation review required')
            if item['kind'] in ('control_authority','reported_beneficial_owner') and 'personal economic' not in item['description'].casefold():
                raise ValueError('Non-economic attribution must disclaim personal economic ownership')
            attribution_span, attribution_text = selected(item['evidence'])
            source_name = item.get('source_name', item['name'])
            if source_name != item['name'] and (item.get('alias_reviewed') is not True or not item.get('alias_reason')):
                raise ValueError('Attributed person alias review required')
            if source_name not in attribution_text:
                raise ValueError('Attributed person missing from evidence')
            attributions.append(dict(person_id=uid('person-in-issuer',cik,item['name']),name=item['name'],
                                     kind=item['kind'],description=item['description'],evidence=attribution_span))
        for c, cell in zip(columns,cells):
            if c['kind'] != 'quantity' or c['key'] not in selected_quantity_keys: continue
            if review.get('skip_undisclosed_quantities') is True and quantity(cell) is None: continue
            security = c.get('share_class', person_security)
            position = dict(id=uid('disclosed-holding', document, pid, c['key']),
                name=name, share_class=security, position_basis=c['position_basis'], shares=quantity(cell),
                raw_quantity=cell, holdings_as_of=as_of, row=sid, evidence=common+notes,
                source_row_key='reviewed-table:'+pid+':'+c['key'],
                explanation=('Source-reported '+('before-IPO' if c['position_basis']=='pre' else 'projected after-IPO')+
                 ' beneficial-ownership total. '+person['interpretation_note']+
                 ' Alternative snapshots must not be summed. This does not establish issued common shares, current personal wealth or liquidity.'),
                conditions='Instrument, attribution and restriction decomposition remains incomplete. No saleability date or realized proceeds is established.')
            if party_kind == 'person' and not attributions:
                position['person_id'] = pid
            else:
                position.update(party_id=pid,party_kind=party_kind,attributions=attributions)
            positions.append(position)
    if not positions: raise ValueError('No reviewed quantities')
    version = 'disclosed-holdings/2' if any('party_id' in p for p in positions) else 'disclosed-holdings/1'
    manifest=dict(version=version,offering_id=offering,document_id=document,
                  source_sha256=source,normalized_sha256=doc['normalized_text_sha256'],review=review,
                  positions=positions,reviewed_non_imported_rows=reviewed_non_imported_rows,
                  spans=spans,audience='internal_review',published=False)
    body=canonical(manifest); release=uid('disclosed-holdings-release',sha(body.encode())); q=literal
    tag='$holdings_'+sha(body.encode())+'$'
    lines=['begin;',f'do {tag} declare parent_run uuid; packet_id uuid; begin',
      f"if exists(select 1 from ops.pilot_manifests where release_id='{release}') then if not exists(select 1 from ops.pilot_manifests where release_id='{release}' and manifest={q(body)}::jsonb) then raise exception 'Manifest conflict'; end if; return; end if;",
      f"if not exists(select 1 from research.offerings o join evidence.documents d on d.source_id=o.source_id join research.filings f on f.id=o.current_filing_id where o.id='{offering}' and o.current_filing_id='{filing}' and f.file_number={q(current['fileNumber'])} and d.id='{document}' and d.content_sha256={q(source)} and o.audience='internal_review' and not o.published) then raise exception 'Canonical source or lineage mismatch'; end if;",
      f"select r.run_id,m.review_packet_id into strict parent_run,packet_id from research.offerings o join ops.releases r on r.id=o.release_id join ops.pilot_manifests m on m.release_id=r.id where o.id='{offering}';"]
    for pid in sorted({p.get('party_id',p.get('person_id')) for p in positions}):
        lines.append(f"if exists(select 1 from research.ownerships where party_id='{pid}' and filing_id='{filing}' and approved) then raise exception 'Existing holding requires explicit overlap review'; end if;")
    for sid,data in spans.items():
        lines += [f"insert into evidence.spans(id,document_id,excerpt,locator,approved) values('{sid}','{document}',{q(data['excerpt'])},{q(canonical(data['locator']))},true) on conflict do nothing;",
                  f"if not exists(select 1 from evidence.spans where id='{sid}' and document_id='{document}' and excerpt={q(data['excerpt'])} and locator={q(canonical(data['locator']))} and approved) then raise exception 'Evidence conflict'; end if;"]
    for p in positions:
        pid,oid=p.get('party_id',p.get('person_id')),p['id']; value='null' if p['shares'] is None else str(p['shares']); dt='null' if not as_of else q(as_of)
        if p.get('party_kind','person') == 'person':
            lines += [f"if not exists(select 1 from research.parties p join research.people pp on pp.id=p.id join research.roles r on r.person_id=p.id where p.id='{pid}' and p.name={q(p['name'])} and pp.identity_verified and r.offering_id='{offering}' and r.verified) then raise exception 'Person identity mismatch'; end if;"]
        else:
            lines += [f"insert into research.parties(id,name,kind) values('{pid}',{q(p['name'])},{q(p['party_kind'])}) on conflict do nothing;",
                      f"if not exists(select 1 from research.parties where id='{pid}' and name={q(p['name'])} and kind={q(p['party_kind'])}) then raise exception 'Holder party mismatch'; end if;"]
        lines += [
          f"insert into research.ownerships(id,offering_id,party_id,filing_id,share_class,position_basis,shares,source_row_key,evidence_id,approved,holdings_as_of,quantity_kind) values('{oid}','{offering}','{pid}','{filing}',{q(p['share_class'])},{q(p['position_basis'])},{value},{q(p['source_row_key'])},'{p['row']}',true,{dt},'beneficial_total');",
          f"insert into research.liquidity_assessments(ownership_id,reviewed,assessed_on,valid_through,classification,explanation,conditions,evidence_ids) values('{oid}',true,'{reviewed}','{reviewed}','unknown',{q(p['explanation'])},{q(p['conditions'])},array["+','.join(q(e)+'::uuid' for e in p['evidence'])+']);']
        for attribution in p.get('attributions',[]):
            aid=attribution['person_id']
            lines += [f"if not exists(select 1 from research.parties p join research.people pp on pp.id=p.id join research.roles r on r.person_id=p.id where p.id='{aid}' and p.name={q(attribution['name'])} and pp.identity_verified and r.offering_id='{offering}' and r.verified) then raise exception 'Attributed person identity mismatch'; end if;",
                      f"insert into research.ownership_attributions(ownership_id,person_id,kind,description,evidence_id,approved) values('{oid}','{aid}',{q(attribution['kind'])},{q(attribution['description'])},'{attribution['evidence']}',true);"]
    lines += [f"insert into ops.releases(id,run_id) values('{release}',parent_run);",
              f"insert into ops.pilot_manifests(release_id,review_packet_id,manifest) values('{release}',packet_id,{q(body)}::jsonb);",f'end {tag};','commit;']
    return manifest,'\n'.join(lines)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('packet','review','archive-dir','output-dir'): parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args(); args.output_dir.mkdir(parents=True,exist_ok=True)
    manifest,sql=build(json.loads(args.packet.read_text()),json.loads(args.review.read_text()),args.archive_dir)
    (args.output_dir/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (args.output_dir/'holdings.sql').write_text(sql)
    print(json.dumps(dict(positions=len(manifest['positions']),published=False)))
