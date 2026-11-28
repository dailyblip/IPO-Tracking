"""Account for every block in explicitly reviewed filing roster sections.

This is a private offline coverage check, not an extractor or publication gate
override. A reviewer selects complete section boundaries and partitions every
block into named entries or explained context. Compare that inventory with a
fresh canonical snapshot: a company import or candidate count is never coverage.
Ownership quantities, footnote interpretation and liquidity remain separate.
"""
import argparse
import json
from pathlib import Path

from build_internal_pilot import uid
from capture_sec_evidence import sha, text_blocks
from import_legacy import canonical
from prepare_sec_review import passage, read_object


KINDS = {'management_table', 'management_biographies', 'ownership_table', 'ownership_footnotes'}


def reconcile(packet, review, snapshot, archive):
    if packet['lineage']['status'] != 'metadata_resolved':
        raise ValueError('Resolved filing lineage required')
    current = packet['lineage']['current']
    docs = [d for d in packet['documents'] if d['filing'] == current]
    if len(docs) != 1:
        raise ValueError('Exactly one current document required')
    doc = docs[0]
    source_hash = doc['source']['content_sha256']
    text, blocks = text_blocks(read_object(archive, source_hash))
    if sha(text.encode()) != doc['normalized_text_sha256']:
        raise ValueError('Normalized source mismatch')
    offering = uid('offering', packet['cik'], packet['lineage']['root']['accessionNumber'])
    if any(s.get('offering_id') != offering or s.get('source_sha256') != source_hash for s in (review, snapshot)):
        raise ValueError('Coverage inputs must match exact offering and source')
    if not snapshot.get('observed_at'):
        raise ValueError('Timestamped canonical snapshot required')
    people = {}
    for person in snapshot['people']:
        name = person['name']
        if name in people:
            raise ValueError('Duplicate canonical person; review identity before coverage')
        people[name] = person
    results, seen_kinds, all_blocks = [], set(), set()
    for section in review['sections']:
        kind = section['kind']
        if kind not in KINDS or section.get('boundaries_reviewed') is not True:
            raise ValueError('Explicitly reviewed section boundaries required')
        seen_kinds.add(kind)
        first, last = section['first'], section['last']
        if type(first) is not int or type(last) is not int or not 0 <= first <= last < len(blocks):
            raise ValueError('Invalid section boundaries')
        section_blocks = set(range(first, last + 1))
        if all_blocks & section_blocks:
            raise ValueError('Sections overlap')
        all_blocks |= section_blocks
        accounted, entries = set(), []
        for part in section['parts']:
            evidence = passage(blocks, part['first'], part['last'], text)
            indices = set(range(part['first'], part['last'] + 1))
            if not indices <= section_blocks or indices & accounted:
                raise ValueError('Overlapping or out-of-section entry')
            accounted |= indices
            entry_kind = part['kind']
            if entry_kind == 'context':
                if not part.get('reason'):
                    raise ValueError('Context requires an explicit disposition')
                entries.append(dict(kind=entry_kind, evidence=evidence, reason=part['reason']))
                continue
            if entry_kind not in ('person', 'organization', 'group', 'footnote'):
                raise ValueError('Unrecognized entry kind')
            label = part['label']
            if not label or label not in evidence['excerpt']:
                raise ValueError('Exact source label required')
            result = dict(kind=entry_kind, label=label, evidence=evidence)
            if entry_kind == 'person':
                name = part['canonical_name']
                if not name or part.get('identity_reviewed') is not True:
                    raise ValueError('Explicit person identity review required')
                if name != label and (part.get('alias_reviewed') is not True or not part.get('alias_reason')):
                    raise ValueError('Spelling/credential aliases require explicit review')
                result['canonical_name'] = name
                person = people.get(name)
                result['status'] = 'person_present' if person else 'person_missing'
                if kind == 'management_biographies':
                    if not evidence['excerpt'].startswith(label) or part.get('complete_biography_reviewed') is not True:
                        raise ValueError('Complete subject-specific biography review required')
                    result['status'] = 'biography_missing'
                    if person:
                        matches = [b for b in person.get('biographies', []) if b['source_sha256'] == source_hash and b['excerpt'] == evidence['excerpt']]
                        result['status'] = 'biography_complete' if matches else 'biography_incomplete_or_different_source'
            else:
                result['status'] = 'review_pending'
                result['reason'] = part.get('reason', 'Representation/interpretation not checked by this person-roster audit')
                if entry_kind == 'footnote' and 'named_people' in part:
                    if part.get('named_people_reviewed') is not True:
                        raise ValueError('Named footnote people require explicit review')
                    named_people, seen_names = [], set()
                    for named in part['named_people']:
                        name = named['name']
                        source_name = named.get('source_name', name)
                        if (source_name != name and
                                (named.get('alias_reviewed') is not True or not named.get('alias_reason'))):
                            raise ValueError('Named controller alias requires explicit review')
                        if (not name or name in seen_names or source_name not in evidence['excerpt'] or
                                named.get('attribution_reviewed') is not True or
                                named.get('attribution_kind') not in ('shared_voting_dispositive', 'upstream_control') or
                                not named.get('reason')):
                            raise ValueError('Literal named controller and reviewed attribution required')
                        seen_names.add(name)
                        named_people.append(dict(name=name, source_name=source_name,
                                                 attribution_kind=named['attribution_kind'],
                                                 reason=named['reason'],
                                                 status='person_present' if name in people else 'person_missing'))
                    result['named_people'] = named_people
            entries.append(result)
        if accounted != section_blocks:
            raise ValueError('Unaccounted source blocks: '+','.join(map(str, sorted(section_blocks-accounted))))
        named = [e for e in entries if e['kind'] != 'context']
        if not named:
            raise ValueError('A context-only section does not establish roster coverage')
        results.append(dict(kind=kind, first=first, last=last, entries=entries,
                            source_entries=len(named), pending=sum(e['status'] not in ('person_present', 'biography_complete') for e in named)))
    by_kind = {kind: [s for s in results if s['kind'] == kind] for kind in KINDS}
    if not {'management_table', 'management_biographies'} <= seen_kinds:
        raise ValueError('Both management table and biography sections required')
    # A named management person cannot disappear because discovery found no bio.
    roster = {e['canonical_name'] for section in by_kind['management_table']
              for e in section['entries'] if e['kind']=='person'}
    bios = {e['canonical_name'] for section in by_kind['management_biographies']
            for e in section['entries'] if e['kind']=='person'}
    without_bio = sorted(roster-bios)
    result = dict(version='people-roster-reconciliation/1', offering_id=offering,
                  source_sha256=source_hash, normalized_sha256=doc['normalized_text_sha256'],
                  snapshot_observed_at=snapshot['observed_at'], snapshot_sha256=sha(canonical(snapshot).encode()),
                  sections=results, management_names_without_selected_biography=without_bio,
                  management_complete=not without_bio and all(
                      section['pending']==0 for k in ('management_table','management_biographies')
                      for section in by_kind[k]),
                  ownership_table_status='accounted_for_with_pending_review' if 'ownership_table' in seen_kinds else 'not_reviewed',
                  ownership_footnotes_status='accounted_for_with_pending_review' if 'ownership_footnotes' in seen_kinds else 'not_reviewed',
                  missing_named_footnote_people=sorted({p['name'] for s in results for e in s['entries']
                                                       for p in e.get('named_people', []) if p['status']=='person_missing'}),
                  holdings_coverage='not_assessed', company_complete=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('packet', 'review', 'snapshot', 'archive-dir', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    result = reconcile(json.loads(args.packet.read_text()), json.loads(args.review.read_text()),
                       json.loads(args.snapshot.read_text()), args.archive_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sections',)}))
