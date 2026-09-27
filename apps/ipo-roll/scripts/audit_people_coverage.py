"""Checkpoint unreviewed biography leads across a canonical offering inventory.

This does not prove complete biography/ownership coverage. Candidates are exact
paragraph starts, not verified people; aliases, footnotes and wrapped text require
source review. Missing local artifacts remain explicit rather than counting zero.
"""
import argparse
import json
from pathlib import Path
from capture_sec_evidence import sha, text_blocks
from discover_people import discover


def audit(inventory, archive_roots):
    wanted = {r['source_sha256'] for r in inventory}
    files = {}
    for root in archive_roots:
        for p in root.glob('**/objects/*'):
            if p.name in wanted and p.is_file():
                files[p.name] = p
    results = []
    for record in inventory:
        result = dict(record)
        p = files.get(record['source_sha256'])
        if not p:
            result['status'] = 'retained_artifact_not_in_local_workspace'
        else:
            raw = p.read_bytes()
            if sha(raw) != record['source_sha256']:
                raise ValueError('Source hash mismatch')
            _, blocks = text_blocks(raw)
            candidates = discover(blocks)
            known = set(record['people'] or [])
            result.update(status='captured_source_scanned',candidates=candidates,
                          unmatched_candidates=[c for c in candidates if c['name'] not in known])
        results.append(result)
    return dict(version='people-coverage-discovery/1',
                scope='Unreviewed biography starts only; not a complete ownership or biography census',
                offerings=results,
                counts=dict(offerings=len(results),
                            sources_scanned=sum(r['status']=='captured_source_scanned' for r in results),
                            sources_unavailable=sum(r['status']!='captured_source_scanned' for r in results),
                            unmatched_candidate_starts=sum(len(r.get('unmatched_candidates',[])) for r in results),
                            offerings_with_unmatched_starts=sum(bool(r.get('unmatched_candidates')) for r in results)))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',type=Path,required=True)
    parser.add_argument('--archive-root',action='append',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(json.loads(args.inventory.read_text()),args.archive_root)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['counts']))
