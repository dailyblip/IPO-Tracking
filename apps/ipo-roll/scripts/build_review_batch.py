"""Build a private, atomic staging import from explicit reviews of captured filings.

This does not fetch data, infer roles, approve commercial rights, or execute SQL.
Real inputs and generated SQL belong in the ignored import-output directory.
"""
import argparse
import base64
import gzip
import json
import re
from pathlib import Path

from build_internal_pilot import uid
from capture_sec_evidence import sha, text_blocks
from import_legacy import canonical
from prepare_sec_review import literal, passage, read_object


def flat(s):
    return re.sub(r"\s+", " ", s).strip()


def sql_value(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return literal(v)


def insert(table, values):
    return "insert into " + table + "(" + ",".join(values) + ") values(" + ",".join(sql_value(v) for v in values.values()) + ");"


def build(packet, review, intake, archive):
    record = next(r for r in intake['records'] if r['id'] == packet['intake_record_id'])
    current, root = packet['lineage']['current'], packet['lineage']['root']
    if packet['cik'] != record['values']['cik'] or current['filingDate'] != record['values']['filed']:
        raise ValueError('Intake/capture identity mismatch')
    if packet['lineage']['status'] != 'metadata_resolved' or current['fileNumber'] != root['fileNumber']:
        raise ValueError('Unresolved registration lineage')
    if review['operating_company'] is not True or review['intake_record_id'] != record['id']:
        raise ValueError('Explicit operating-company review required')
    docs = {}
    artifacts = {}
    for d in packet['documents']:
        raw = read_object(archive, d['source']['content_sha256'])
        text, blocks = text_blocks(raw)
        if sha(text.encode()) != d['normalized_text_sha256']:
            raise ValueError('Captured document/normalizer mismatch')
        if d['filing']['fileNumber'] != current['fileNumber']:
            raise ValueError('Cross-registration document')
        docs[d['filing']['accessionNumber']] = (d, text, blocks)
        artifacts[d['source']['content_sha256']] = raw
        artifacts[d['normalized_text_sha256']] = read_object(archive, d['normalized_text_sha256'])
    for m in packet['metadata_artifacts']:
        artifacts[m['content_sha256']] = read_object(archive, m['content_sha256'])
    cur = current['accessionNumber']
    if cur not in docs or root['accessionNumber'] not in docs:
        raise ValueError('Missing root or current filing')

    def selected(spec):
        accession = spec.get('accession', cur)
        d, text, blocks = docs[accession]
        out = passage(blocks, spec['first'], spec.get('last', spec['first']), text)
        if spec.get('literal') and spec['literal'].casefold() not in flat(out['excerpt']).casefold():
            raise ValueError('Selected literal not in captured passage')
        return dict(out, accession=accession, source_sha256=d['source']['content_sha256'])

    fields = {k: selected(v) for k, v in review['fields'].items()}
    for key in ('company', 'initial_offering', 'operating_business'):
        if key not in fields:
            raise ValueError('Missing reviewed field: ' + key)
    if 'initial public offering' not in flat(fields['initial_offering']['excerpt']).lower():
        raise ValueError('Missing IPO evidence')
    name = review['company']
    if name.casefold() not in flat(fields['company']['excerpt']).casefold():
        raise ValueError('Issuer display name absent from selected passage')
    ticker = review.get('ticker', '')
    if ticker and (not re.fullmatch('[A-Z]{1,8}', ticker) or not re.search(r'(?<![A-Z])'+re.escape(ticker)+r'(?![A-Z])', fields['ticker']['excerpt'])):
        raise ValueError('Ticker lacks literal evidence')
    prelim = review.get('preliminary')
    filing_price = None
    if prelim:
        if docs[fields['preliminary']['accession']][0]['filing']['form'] not in ('S-1','S-1/A','F-1','F-1/A'):
            raise ValueError('Preliminary price requires registration statement')
        text = flat(fields['preliminary']['excerpt'])
        if 'low' in prelim:
            lo, hi = prelim['low'], prelim['high']
            if not (0 < lo <= hi) or f'between ${lo:.2f} and ${hi:.2f}' not in text:
                raise ValueError('Preliminary range not supported')
            filing_price = f'${lo:.2f}–${hi:.2f}'
        else:
            value = prelim['fixed']
            if value <= 0 or f'fixed at ${value:.2f}' not in text:
                raise ValueError('Fixed filing price not supported')
            filing_price = f'${value:.2f}'
    final, pricing_date, value = None, None, None
    if current['form'] == '424B4':
        if not review.get('preceding_filings_reviewed') or not all(k in fields for k in ('final_price','pricing_date','offering_value')):
            raise ValueError('Priced offering needs final terms and preliminary-history review')
        final, pricing_date, value = review['final_price'], review['pricing_date'], review['offering_value']
        if final <= 0 or f'${final:.2f}' not in flat(fields['final_price']['excerpt']).replace('$ ', '$'):
            raise ValueError('Final IPO price lacks evidence')
        if f'{value:,}' not in fields['offering_value']['excerpt']:
            raise ValueError('Offering value lacks evidence')
        from datetime import date
        if date.fromisoformat(pricing_date).strftime('%B %-d, %Y') not in fields['pricing_date']['excerpt']:
            raise ValueError('Pricing date lacks evidence')
        stage = 'Priced'
    elif current['form'] in ('S-1','S-1/A','F-1','F-1/A'):
        stage = 'Pre-pricing'
    else:
        raise ValueError('Unsupported filing form')

    people = []
    for p in review['people']:
        bio = selected(p['biography'])
        body = flat(bio['excerpt'])
        if bio['accession'] != cur or not re.match(re.escape(p['name'])+r'(?:[\s,.]|$)', body) or p['title'].casefold() not in body.casefold():
            raise ValueError('Person name/title not present in reviewed biography')
        if p['relationship'] not in ('Executive','Director'):
            raise ValueError('Biography alone cannot establish beneficial ownership')
        people.append(dict(p, biography=bio))
    manifest = dict(version='reviewed-month/1', intake_record_id=record['id'],
                    capture=packet, review=review, fields=fields, people=people,
                    audience='internal_review', published=False,
                    snapshot_note='Captured filing snapshot; not a live market or ownership update')
    digest = sha(canonical(manifest).encode())
    release = uid('release', digest)
    offering = uid('offering', packet['cik'], root['accessionNumber'])
    company = uid('company', packet['cik'])
    review_packet = dict(version='sec-selected-review/1', capture=packet, people=people,
                         rights_status='unreviewed', publication_allowed=False, field_review=fields)
    packet_hash = sha(canonical(review_packet).encode())
    packet_id = uid('review-packet', packet_hash)
    stmts = [insert('ops.sec_review_packets',dict(id=packet_id,intake_record_id=record['id'],packet_sha256=packet_hash,packet=canonical(review_packet))),
             insert('ops.releases',dict(id=release,run_id=intake['run_id'])),
             insert('research.companies',dict(id=company,cik=packet['cik'],name=name,classification='operating_company',eligible=True,audience='internal_review'))]
    sources, documents, filings = {}, {}, {}
    for acc, (d, _, _) in docs.items():
        f = d['filing']; fid=uid('filing',acc); sid=uid('source',d['source']['url']); did=uid('document',d['source']['content_sha256'])
        filings[acc],sources[acc],documents[acc] = fid,sid,did
        stmts.append(insert('research.filings',dict(id=fid,company_id=company,accession=acc,form=f['form'],filed_on=f['filingDate'],file_number=f['fileNumber'],index_url=f"https://www.sec.gov/Archives/edgar/data/{int(packet['cik'])}/{acc.replace('-','')}/{acc}-index.htm")))
        stmts.append(insert('evidence.sources',dict(id=sid,filing_id=fid,title=name+' — '+f['form'],url=d['source']['url'],published_on=f['filingDate'],rights_status='internal_review')))
        stmts.append(insert('evidence.documents',dict(id=did,source_id=sid,content_sha256=d['source']['content_sha256'],retrieved_at=d['source']['retrieved_at'],parser_version=d['normalizer'])))
    def span(key, data):
        sid=uid('span',documents[data['accession']],key)
        stmts.append(insert('evidence.spans',dict(id=sid,document_id=documents[data['accession']],excerpt=data['excerpt'],locator=canonical(data['locator']),approved=True)))
        return sid
    field_ids={k:span(k,v) for k,v in fields.items()}
    stmts.append(insert('research.offerings',dict(id=offering,company_id=company,root_filing_id=filings[root['accessionNumber']],current_filing_id=filings[cur],registration_file_number=current['fileNumber'],stage=stage,filed_on=root['filingDate'],pricing_date=pricing_date,final_price=final,offering_value=value,value_basis='Gross base offering; excludes overallotment' if value else None,filing_price=filing_price,ticker=ticker,source_id=sources[cur],release_id=release,published=False,audience='internal_review',signals='{Reviewed filing snapshot}')))
    if prelim:
        stmts.append(insert('research.preliminary_prices',dict(id=uid('preliminary',offering),offering_id=offering,filing_id=filings[fields['preliminary']['accession']],raw_text=fields['preliminary']['excerpt'],low=prelim.get('low'),high=prelim.get('high'),fixed_price=prelim.get('fixed'),evidence_id=field_ids['preliminary'])))
    for p in people:
        pid=uid('person-in-issuer',packet['cik'],p['name']); bid=uid('biography',pid,documents[cur]); sid=span(p['name']+':biography',p['biography'])
        stmts.extend([insert('research.parties',dict(id=pid,name=p['name'],kind='person')),insert('research.people',dict(id=pid,identity_verified=True)),insert('research.roles',dict(id=uid('role',pid,offering,p['relationship']),person_id=pid,offering_id=offering,title=p['title'],relationship=p['relationship'],evidence_id=sid,verified=True)),insert('research.biographies',dict(id=bid,person_id=pid,span_id=sid,approved=True))])
        # This claim attests only to literal reviewed text, not an inferred affiliation.
        stmts.append(insert('research.claims',dict(id=uid('claim',bid,'biography_text'),biography_id=bid,predicate='biography_text',object_text=flat(p['biography']['excerpt']),evidence_id=sid,verified=True)))
    for checksum in artifacts:
        stmts.append(insert('ops.sec_packet_artifacts',dict(packet_id=packet_id,artifact_sha256=checksum)))
    manifest['offering_id']=offering
    body=canonical(manifest)
    stmts.append(insert('ops.pilot_manifests',dict(release_id=release,review_packet_id=packet_id,manifest=body)))
    tag='$batch_'+digest+'$'
    # Exact replay skips the entire immutable release; divergent data fails instead of overwriting it.
    guard=f"if exists(select 1 from ops.pilot_manifests where release_id='{release}' and manifest={literal(body)}::jsonb) then return; end if;"
    sql='do '+tag+' begin '+guard+'\n'+'\n'.join(stmts)+'\nend '+tag+';\n'
    return dict(offering_id=offering,release_id=release,company=name,people=len(people)),sql,artifacts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('intake','reviews','capture-dir','archive-dir','output-dir'):
        parser.add_argument('--'+k,type=Path,required=True)
    a=parser.parse_args(); intake=json.loads(a.intake.read_text()); reviews=json.loads(a.reviews.read_text());a.output_dir.mkdir(parents=True,exist_ok=True)
    results=[];sql=['begin;'];objects={}
    for review in reviews:
        packet=json.loads((a.capture_dir/review['capture_file']).read_text())
        result,statement,artifacts=build(packet,review,intake,a.archive_dir)
        results.append(result);sql.append(statement);objects.update(artifacts)
        (a.output_dir/(review['capture_file'].replace('.json','.sql'))).write_text('begin;\n'+statement+'commit;')
    sql.append('commit;')
    (a.output_dir/'import.sql').write_text('\n'.join(sql))
    (a.output_dir/'manifest.json').write_text(json.dumps(results,indent=2))
    # Archive original bytes before exposing any referencing research rows.
    chunks=[];current=[];size=0
    for checksum,raw in sorted(objects.items()):
        packed=base64.b64encode(gzip.compress(raw,mtime=0)).decode()
        line=f"insert into ops.sec_artifacts(sha256,raw_bytes,content_gzip) values('{checksum}',{len(raw)},decode('{packed}','base64')) on conflict do nothing;"
        if current and size+len(line)>240000:
            chunks.append(current);current=[];size=0
        current.append(line);size+=len(line)
    if current:chunks.append(current)
    for i,lines in enumerate(chunks):
        (a.output_dir/f'archive-{i:03}.sql').write_text('begin;\n'+'\n'.join(lines)+'\ncommit;')
    print(json.dumps(dict(companies=len(results),people=sum(r['people'] for r in results),artifacts=len(objects),archive_chunks=len(chunks))))


if __name__=='__main__':main()
