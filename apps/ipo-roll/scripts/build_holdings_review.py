"""Offline, explicit source-position review; never derives current wealth.

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
from review_components import parse_components
from review_options import parse_pre_options


def flat(value):
    return re.sub(r'\s+', ' ', value).strip()


def build(packet, review, directory):
    current = packet['lineage']['current']
    profile = review.get('profile', 'projected-class-a-trust')
    dated = profile == 'dated-pre-common'
    mixed = profile == 'reviewed-mixed-awards'
    options = profile == 'dated-pre-options'
    component_total = mixed or options
    has_date = dated or component_total
    if profile not in ('projected-class-a-trust', 'dated-pre-common', 'reviewed-mixed-awards', 'dated-pre-options'):
        raise ValueError('Unsupported review profile')
    forms = ('424B4',) if dated or options else ('S-1/A', 'S-1', 'F-1', 'F-1/A')
    if packet['lineage']['status'] != 'metadata_resolved' or current['form'] not in forms:
        raise ValueError('Filing does not match the explicit review profile')
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
    if has_date:
        required_headers = ('Owned Before This Offering', 'Owned After This Offering') if mixed else ('before this offering', 'after this offering', 'Class A', 'Class B')
        if options:
            required_headers = ('SHARES BENEFICIALLY', 'OWNED PRIOR TO OFFERING', 'OWNED AFTER OFFERING', 'NUMBER PERCENTAGE')
        if not all(s in flat(headers['excerpt']) for s in required_headers):
            raise ValueError('Pre/post Class A/B header evidence required')
        as_of = date.fromisoformat(review['holdings_as_of'])
        if as_of > date.fromisoformat(current['filingDate']):
            raise ValueError('Holdings date cannot follow source filing')
        date_literal = as_of.strftime('%B') + f' {as_of.day}, {as_of.year}'
        noun = 'capital stock' if options else 'common stock'
        if f'beneficial ownership of our {noun} as of {date_literal},' not in flat(basis['excerpt']):
            raise ValueError('Explicit holdings as-of evidence required')
        if options:
            if not all(s in flat(basis['excerpt']) for s in ('Applicable percentage ownership before the offering', 'automatic conversion of all outstanding shares of our redeemable convertible preferred stock', 'exercisable within 60 days of '+date_literal, 'does not reflect any potential purchases')):
                raise ValueError('Complete pre/post conversion and option basis required')
            terms = ('our officers, directors', 'have agreed, subject to specified exceptions', '180 days after the date of this prospectus', 'prior written consent', 'upon exercise', 'underlying shares of common stock shall continue to be subject', 'may, in their sole discretion', 'release all or any portion')
        elif mixed:
            if not all(s in flat(basis['excerpt']) for s in ('Preferred Stock Conversion', 'SAFE Conversion', 'RSU Net Settlement')):
                raise ValueError('Adjusted table assumptions required')
            terms = ('all of our directors and executive officers', '180 days from the date of this prospectus', 'various intervals', 'stock price exceeds certain thresholds', 'ability to release')
        else:
            terms = ('180 days after the date of this prospectus', 'Our directors and executive officers', 'have entered into lock-up agreements', 'limited exceptions', 'prior written consent', 'may release')
    else:
        if 'Shares of Common Stock Beneficially Owned After this Offering' not in flat(headers['excerpt']) or 'Shares of Class A Common Stock' not in flat(headers['excerpt']):
            raise ValueError('Projected Class A column evidence required')
        if 'after the offering' not in flat(basis['excerpt']).lower():
            raise ValueError('Projected position assumptions required')
        terms = ('will sign lock-up agreements', 'not less than 180 days', 'prior written consent', 'subject to certain exceptions')
    if not review['restriction_literal'] or review['restriction_literal'] not in flat(restriction['excerpt']):
        raise ValueError('Restriction passage mismatch')
    if not all(term in flat(restriction['excerpt']) for term in terms):
        raise ValueError('Review requires the supported conditional lock-up wording')
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
        row_prefix = name + (' ' if options else '') + '(' + marker + ')'
        if not flat(row['excerpt']).startswith(row_prefix) or not flat(note['excerpt']).startswith('(' + marker + ')'):
            raise ValueError('Row identity or footnote association mismatch')
        if not has_date and 'trust' not in flat(note['excerpt']).lower():
            raise ValueError('This review path requires explicit trust-component evidence')
        n = item['shares']
        if type(n) is not int or not 0 < n <= 9007199254740991:
            raise ValueError('Unsupported share count')
        index = item['share_block']
        if type(index) is not int or not item['row']['first'] <= index <= item['row']['last']:
            raise ValueError('Share cell outside selected row')
        cell = text[blocks[index]['start']:blocks[index]['end']]
        if has_date:
            share_class = 'Common stock underlying options' if options else 'Common stock and underlying awards' if mixed else item['share_class']
            if dated and (share_class not in ('Class A common stock', 'Class B common stock') or flat(note['excerpt']) != f'({marker})Represents {n:,} shares of {share_class}.'):
                raise ValueError('Only an explicit simple common-share footnote is supported; mixed instruments and attribution require separate review')
            counts = re.findall(r'(?<![\d,])\d[\d,]*(?![\d,])', cell)
            if not counts or counts[0] != f'{n:,}':
                raise ValueError('Pre-offering share count does not match row')
            if options:
                # Two explicit NUMBER/PERCENTAGE pairs; no dash/zero/extra cells.
                pair = re.fullmatch(r'([\d,]+) (?:\d+(?:\.\d+)? %|\*) ([\d,]+) (?:\d+(?:\.\d+)? %|\*)', flat(cell))
                if not pair:
                    raise ValueError('Complete pre/post option row required')
                post_total = int(pair[2].replace(',', ''))
                if pair[2] != f'{post_total:,}':
                    raise ValueError('Malformed post-offering quantity')
        elif cell != f'{n:,}':
            raise ValueError('Selected share cell does not match count')
        person = uid('person-in-issuer', cik, name)
        key = 'options-pre' if options else 'mixed-awards-pre' if mixed else 'dated-pre-'+share_class if dated else 'projected-A'
        oid = uid('holding-review', document, person, key)
        position = dict(id=oid,person_id=person,name=name,shares=n,row=span(row),evidence=common+[span(note)],source_row_key=('reviewed-'+key+':' if has_date else 'reviewed-projected-A:')+person)
        if has_date:
            position.update(share_class=share_class,position_basis='pre',holdings_as_of=as_of.isoformat())
        if component_total:
            position['components'] = parse_pre_options(note['excerpt'],marker,name,date_literal,n,post_total) if options else parse_components(note['excerpt'],marker,name,date_literal,n)
            position['quantity_kind'] = 'beneficial_total'
        positions.append(position)
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
        explanation = ('Disclosed pre-offering common-share position as of '+p['holdings_as_of']+'. This historical disclosure does not confirm current ownership, personal economic interest or present saleability.') if dated else 'Projected post-offering position, not confirmed current holdings. The total includes a trust component described in the footnote; personal economic ownership of the entire position is unconfirmed.'
        conditions = ('The filing describes director/executive lock-ups for a restricted period of 180 days after the prospectus date, with consent, exceptions and discretionary release. No current release, resale eligibility or security-matched quote has been verified. Dates remain unclassified pending a separate trigger/date review; Class B shares are not a Class A trading position.') if dated else 'The preliminary filing describes planned lock-ups of not less than 180 days from the prospectus date, subject to underwriter consent and exceptions. No executed lock-up start, release date or present saleability is confirmed. Offering assumptions and ownership footnotes are retained below.'
        if mixed:
            explanation = 'Adjusted pre-offering beneficial-ownership disclosure as of '+p['holdings_as_of']+'. The table gives effect to preferred/SAFE conversions and RSU net settlement. The total includes award-underlying interests; components below are parts of this total, not extra holdings. Trust attribution does not establish personal economic ownership. No current position or saleability is confirmed.'
            conditions = 'The preliminary filing describes graduated lock-up releases, price-based conditions, exceptions and discretionary release. A uniform 180-day sale date is not established. RSU vesting/settlement and option exercise conditions are disclosed as of the source date; exercise price, actual settlement, current ownership and resale eligibility remain unverified. No price or cash proceeds are inferred.'
        if options:
            explanation = 'Pre-offering option-underlying interests disclosed as of '+p['holdings_as_of']+'. The complete footnote separates subsequent LLC distributions and any repurchase conditions; those post-offering interests are not added to this pre-offering total. Preferred-conversion assumptions remain in the table basis. These are not confirmed issued shares or current holdings.'
            conditions = 'The prospectus describes a conditional 180-day restriction, exceptions and discretionary release. Exercise does not remove restrictions on the underlying shares. Actual exercise, vesting, exercise price, personal economic ownership, current holdings and resale eligibility remain unverified. No expiry date, market value, cash proceeds or intrinsic option value is inferred.'
        extra_column = ',holdings_as_of' if has_date else ''
        extra_value = ','+q(p['holdings_as_of']) if has_date else ''
        if component_total:
            extra_column += ',quantity_kind'
            extra_value += ",'beneficial_total'"
        stmts += [f"if not exists(select 1 from research.parties p join research.people pp on pp.id=p.id join research.roles r on r.person_id=p.id where p.id='{pid}' and p.name={q(p['name'])} and pp.identity_verified and r.offering_id='{offering}' and r.verified) then raise exception 'Person identity mismatch'; end if;",
            f"insert into research.ownerships(id,offering_id,party_id,filing_id,share_class,position_basis,shares,source_row_key,evidence_id,approved{extra_column}) values('{oid}','{offering}','{pid}','{filing}',{q(p.get('share_class','Class A common stock'))},{q(p.get('position_basis','post'))},{p['shares']},{q(p['source_row_key'])},'{p['row']}',true{extra_value});",
            f"insert into research.liquidity_assessments(ownership_id,reviewed,assessed_on,valid_through,classification,explanation,conditions,evidence_ids) values('{oid}',true,'{reviewed_on}','{reviewed_on}','unknown',",
            q(explanation)+','+q(conditions)+
            ",array["+','.join(q(e)+'::uuid' for e in p['evidence'])+"]);"]
        for c in p.get('components',[]):
            stmts.append(f"insert into research.ownership_components(ownership_id,ordinal,instrument,quantity,attribution,description,evidence_id,approved) values('{oid}',{c['ordinal']},{q(c['instrument'])},{c['quantity']},{q(c['attribution'])},{q(c['description'])},'{p['evidence'][-1]}',true);")
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
