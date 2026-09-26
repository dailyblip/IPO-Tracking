"""Prepare an atomic internal-review pilot. Never approves commercial publication.

A curated field review is required. Facts retain exact captured passages. The SQL
is executed administratively in staging; it grants no accounts access.
"""
import argparse
import json
import re
import uuid
from pathlib import Path
from import_legacy import canonical
from prepare_sec_review import read_object, passage, literal
from capture_sec_evidence import sha, text_blocks


def uid(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'ipo-roll:pilot:' + ':'.join(parts)))


def build(review, fields, directory):
    expected = sha(canonical({k:v for k,v in review.items() if k not in ('id','sha256','intake_run_id')}).encode())
    if review.get('sha256') != expected:
        raise ValueError('Review packet checksum mismatch')
    capture = review['capture']
    current = capture['lineage']['current']
    root = capture['lineage']['root']
    doc = next(d for d in capture['documents'] if d['filing']['accessionNumber'] == current['accessionNumber'])
    text, blocks = text_blocks(read_object(directory, doc['source']['content_sha256']))
    if sha(text.encode()) != doc['normalized_text_sha256']:
        raise ValueError('Snapshot mismatch')
    if current['form'] not in ('S-1', 'S-1/A', 'F-1', 'F-1/A'):
        raise ValueError('This pilot builder only supports preliminary offerings')
    for person in review['people']:
        if person['source']['content_sha256'] != doc['source']['content_sha256']:
            raise ValueError('Person source mismatch')
        for key in ('biography','relationship_evidence'):
            selected_span = person[key]
            loc = selected_span['locator']
            if text[loc['start']:loc['end']] != selected_span['excerpt']:
                raise ValueError('Person passage mismatch')
        if person['name'] not in person['relationship_evidence']['excerpt']:
            raise ValueError('Relationship identity missing')
    selected = {k: passage(blocks, v['first_block'], v['last_block'], text) for k, v in fields.items()}
    for key, spec in fields.items():
        flat = re.sub(r'\s+', ' ', selected[key]['excerpt'])
        if not isinstance(spec['literal'], str) or spec['literal'] not in flat:
            raise ValueError('Field literal not found: ' + key)
    if set(fields) != {'company', 'ticker', 'filing_price', 'operating_business', 'initial_offering'}:
        raise ValueError('Complete explicit field review required')
    company = fields['company']['literal']
    ticker = fields['ticker']['literal']
    if not re.fullmatch(r'[A-Z]{1,8}', ticker):
        raise ValueError('Invalid proposed ticker')
    low, high = fields['filing_price']['low'], fields['filing_price']['high']
    if type(low) not in (int,float) or type(high) not in (int,float) or not 0 < low <= high:
        raise ValueError('Invalid preliminary range')
    if f'between ${low:.2f} and ${high:.2f}' not in selected['filing_price']['excerpt']:
        raise ValueError('Range does not match explicit source text')
    if 'initial public offering' not in selected['initial_offering']['excerpt'].lower():
        raise ValueError('Initial offering evidence required')
    # The operating-business selection is a recorded review decision, not automatic classification.
    manifest = {'review_packet_id':review['id'], 'source_sha256':doc['source']['content_sha256'],
                'normalized_sha256':doc['normalized_text_sha256'], 'fields':selected,
                'audience':'internal_review','published':False,'review_method':'explicit_source_selection',
                'null_fields':['final_price','pricing_date','offering_value','current_price']}
    digest = sha(canonical(manifest).encode())
    release = uid('release', digest)
    cik = capture['cik']
    company_id = uid('company', cik)
    offering = uid('offering', cik, root['accessionNumber'])
    source = uid('source', doc['source']['url'])
    document = uid('document', doc['source']['content_sha256'])
    stmts = ['begin;']
    def insert(table, values):
        def sql(v):
            if v is None:return 'null'
            if isinstance(v,bool):return 'true' if v else 'false'
            if isinstance(v,(int,float)):return str(v)
            return literal(v)
        stmts.append('insert into '+table+'('+','.join(values)+') values('+','.join(sql(v) for v in values.values())+');')
    insert('ops.releases', {'id':release,'run_id':fields_run_id(review),'published_at':None})
    insert('research.companies',dict(id=company_id,cik=cik,name=company,classification='operating_company',eligible=True,audience='internal_review'))
    filing_ids={}
    for f in {r['accessionNumber']:r for r in (root,current)}.values():
        fid=uid('filing',f['accessionNumber']);filing_ids[f['accessionNumber']]=fid
        insert('research.filings',dict(id=fid,company_id=company_id,accession=f['accessionNumber'],form=f['form'],filed_on=f['filingDate'],file_number=f['fileNumber'],index_url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{f['accessionNumber'].replace('-','')}/{f['accessionNumber']}-index.htm"))
    insert('evidence.sources',dict(id=source,filing_id=filing_ids[current['accessionNumber']],title=company+' — '+current['form'],url=doc['source']['url'],published_on=current['filingDate'],rights_status='internal_review'))
    insert('evidence.documents',dict(id=document,source_id=source,content_sha256=doc['source']['content_sha256'],retrieved_at=doc['source']['retrieved_at'],parser_version=doc['normalizer']))
    insert('research.offerings',dict(id=offering,company_id=company_id,root_filing_id=filing_ids[root['accessionNumber']],current_filing_id=filing_ids[current['accessionNumber']],registration_file_number=current['fileNumber'],stage='Pre-pricing',filed_on=root['filingDate'],filing_price=f'${low:.2f}–${high:.2f}',ticker=ticker,source_id=source,release_id=release,published=False,audience='internal_review'))
    def span(key,data):
        sid=uid('span',document,key)
        insert('evidence.spans',dict(id=sid,document_id=document,excerpt=data['excerpt'],locator=canonical(data['locator']),approved=True))
        return sid
    evidence_ids={k:span(k,v) for k,v in selected.items()}
    insert('research.preliminary_prices',dict(id=uid('preliminary',offering),offering_id=offering,filing_id=filing_ids[current['accessionNumber']],raw_text=selected['filing_price']['excerpt'],low=low,high=high,evidence_id=evidence_ids['filing_price']))
    for person in review['people']:
        pid=uid('person-in-issuer',cik,person['name'])
        bioid=uid('biography',pid,document)
        rel=span(person['name']+':relationship',person['relationship_evidence'])
        bio=span(person['name']+':biography',person['biography'])
        insert('research.parties',dict(id=pid,name=person['name'],kind='person'))
        insert('research.people',dict(id=pid,identity_verified=True))
        insert('research.roles',dict(id=uid('role',pid,offering,person['relationship']),person_id=pid,offering_id=offering,title=person['title'],relationship=person['relationship'],evidence_id=rel,verified=True))
        insert('research.biographies',dict(id=bioid,person_id=pid,span_id=bio,approved=True))
        # Each curated education term must have an explicit degree statement, not merely co-occurrence.
        flat=re.sub(r'\s+',' ',person['biography']['excerpt'])
        for term in person['literal_search_terms']:
            if not re.search(r'(?:MBA|BS|Master’s|Bachelor’s|degree).{0,100}?'+re.escape(term),flat):
                raise ValueError('Education term needs explicit degree evidence: '+term)
            insert('research.claims',dict(id=uid('claim',bioid,term),biography_id=bioid,predicate='education',object_text=term,evidence_id=bio,verified=True))
    manifest['offering_id']=offering
    insert('ops.pilot_manifests',dict(release_id=release,review_packet_id=review['id'],manifest=canonical(manifest)))
    stmts.append('commit;')
    return {'release_id':release,'offering_id':offering,'manifest':manifest}, '\n'.join(stmts)+'\n'


def fields_run_id(review):
    # The parent run is supplied from the immutable intake, never fabricated from a company name.
    return review['intake_run_id']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('review','intake','fields','archive-dir','output-dir'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();review=json.loads(a.review.read_text());intake=json.loads(a.intake.read_text())
    if review['capture']['intake_record_id'] not in {r['id'] for r in intake['records']}:raise ValueError('Intake mismatch')
    review['intake_run_id']=intake['run_id']
    result,sql=build(review,json.loads(a.fields.read_text()),a.archive_dir)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    (a.output_dir/'pilot.sql').write_text(sql);(a.output_dir/'pilot.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'release_id':result['release_id'],'offering_id':result['offering_id'],'published':False}))
