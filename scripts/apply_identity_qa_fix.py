from pathlib import Path
import json

# 1) Normalize SEC ownership-table names before merge/dedup.
p=Path('src/ownership_parser.py'); s=p.read_text(encoding='utf-8')
old='''def _clean(text):\n    return " ".join(str(text or "").replace("\\xa0", " ").split())\n'''
new='''def _clean(text):\n    value = " ".join(str(text or "").replace("\\xa0", " ").split())\n    # SEC tables often use dot leaders between holder labels and numeric columns.\n    # They are presentation artifacts, never part of a person's/entity's name.\n    value = re.sub(r"\\s*\\.{3,}\\s*$", "", value)\n    return value.strip()\n\n\ndef canonical_holder_name(value):\n    """Canonical identity key for holder deduplication, without guessing identity."""\n    value = _clean(value)\n    value = re.sub(r"(?:\\s*\\(\\d+[a-z]?\\))+$", "", value, flags=re.I)\n    value = re.sub(r"[†‡*]+$", "", value).strip()\n    value = re.sub(r"\\s*\\.{2,}\\s*", " ", value)\n    return " ".join(value.lower().split())\n'''
assert old in s
s=s.replace(old,new,1)
s=s.replace('''            key = " ".join(holder["name"].lower().split())\n''','''            key = canonical_holder_name(holder["name"])\n''',1)
p.write_text(s,encoding='utf-8')

# 2) Normalize names at dashboard boundary too, so historical/live/backfill variants collapse.
p=Path('src/dashboard_export.py'); s=p.read_text(encoding='utf-8')
old='''    name = " ".join(raw.split())\n    return re.sub(r"(?:\\s*\\(\\d+\\))+$", "", name).strip()\n'''
new='''    name = " ".join(raw.split())\n    name = re.sub(r"\\s*\\.{3,}\\s*$", "", name)\n    name = re.sub(r"(?:\\s*\\(\\d+[a-z]?\\))+$", "", name, flags=re.I)\n    name = re.sub(r"[†‡*]+$", "", name).strip()\n    return name\n\n\ndef _holder_identity_key(value):\n    return " ".join(_clean_holder_name(value).lower().split())\n'''
assert old in s
s=s.replace(old,new,1)
s=s.replace('''            if not name or _is_aggregate_holder(name) or name.lower() in seen:\n                continue\n            seen.add(name.lower())\n''','''            identity_key = _holder_identity_key(name)\n            if not name or _is_aggregate_holder(name) or identity_key in seen:\n                continue\n            seen.add(identity_key)\n''',1)
p.write_text(s,encoding='utf-8')

# 3) UI canonical merge: dot-leader variants must not create duplicate people.
p=Path('docs/prospect-research/index.html'); s=p.read_text(encoding='utf-8')
old='''function keyName(v){return String(v||"").trim().toLowerCase()}'''
new='''function keyName(v){return String(v||"").replace(/\\s*\\.{3,}\\s*$/g,"").replace(/(?:\\s*\\(\\d+[a-z]?\\))+$/gi,"").replace(/[†‡*]+$/g,"").trim().replace(/\\s+/g," ").toLowerCase()}'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# 4) Fix the known Neutron calibration record using direct evidence in the final 424B4.
p=Path('docs/prospect-research/backfill.json'); data=json.loads(p.read_text(encoding='utf-8'))
for filing in data.get('filings',[]):
    if filing.get('cik')=='0001699963':
        signals=filing.setdefault('signals',[])
        signal='Stanford affiliation confirmed for former President Joseph Kraus from the final prospectus bio'
        if signal not in signals: signals.append(signal)
        for person in filing.get('people',[]):
            if person.get('name')=='Joseph Kraus':
                person['stanford_university_bio']=True
                person['stanford_affiliation_confirmed']=True
                person['stanford_source']='Neutron Holdings final 424B4 bio states that Joseph Kraus holds a B.A. in Political Science from Stanford University.'
p.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

# 5) QA must reject duplicate canonical holder identities, not merely render around them.
p=Path('src/qc_review.py'); s=p.read_text(encoding='utf-8')
marker='''def check_ticker_resolved(row: dict) -> list:\n'''
insert='''def canonical_holder_identity(value):\n    value = " ".join(str(value or "").split())\n    value = re.sub(r"\\s*\\.{3,}\\s*$", "", value)\n    value = re.sub(r"(?:\\s*\\(\\d+[a-z]?\\))+$", "", value, flags=re.I)\n    value = re.sub(r"[†‡*]+$", "", value).strip()\n    return value.lower()\n\n\ndef check_duplicate_holder_identities(rows: list) -> list:\n    """Flag duplicate people/entities after removing SEC presentation artifacts."""\n    seen = {}\n    issues = []\n    for row in rows or []:\n        name = row.get("Holder Name") or row.get("name")\n        key = canonical_holder_identity(name)\n        if not key:\n            continue\n        if key in seen:\n            issues.append(f"Duplicate holder identity after normalization: {seen[key]} / {name}")\n        else:\n            seen[key] = name\n    return issues\n\n\n'''
assert marker in s
s=s.replace(marker,insert+marker,1)
p.write_text(s,encoding='utf-8')

# 6) Regression coverage: dot leaders collapse; direct Stanford calibration stays visible.
p=Path('src/test_ownership_parser.py'); s=p.read_text(encoding='utf-8')
if 'test_canonical_holder_name_strips_sec_dot_leaders' not in s:
    s += '''\n\nclass HolderIdentityQaTests(unittest.TestCase):\n    def test_canonical_holder_name_strips_sec_dot_leaders(self):\n        import ownership_parser\n        self.assertEqual(ownership_parser.canonical_holder_name("Gwynne Shotwell..................."), "gwynne shotwell")\n        self.assertEqual(ownership_parser.canonical_holder_name("Gwynne Shotwell (12)"), "gwynne shotwell")\n'''
p.write_text(s,encoding='utf-8')

p=Path('src/test_dashboard_export.py'); s=p.read_text(encoding='utf-8')
if 'test_holder_cleaner_strips_dot_leaders' not in s:
    s += '''\n\nclass HolderIdentityExportQaTests(unittest.TestCase):\n    def test_holder_cleaner_strips_dot_leaders(self):\n        import dashboard_export\n        self.assertEqual(dashboard_export._clean_holder_name("Gwynne Shotwell..................."), "Gwynne Shotwell")\n        self.assertEqual(dashboard_export._holder_identity_key("Gwynne Shotwell..................."), dashboard_export._holder_identity_key("Gwynne Shotwell"))\n'''
p.write_text(s,encoding='utf-8')

p=Path('src/test_prospect_liquidity_site.py'); s=p.read_text(encoding='utf-8')
if 'test_neutron_stanford_connection_is_explicit' not in s:
    s += '''\n\nclass ProspectIdentityQaTests(unittest.TestCase):\n    def test_neutron_stanford_connection_is_explicit(self):\n        import json\n        from pathlib import Path\n        data=json.loads((Path(__file__).parents[1]/"docs/prospect-research/backfill.json").read_text(encoding="utf-8"))\n        neutron=next(f for f in data["filings"] if f.get("cik")=="0001699963")\n        kraus=next(p for p in neutron["people"] if p.get("name")=="Joseph Kraus")\n        self.assertTrue(kraus.get("stanford_university_bio"))\n        self.assertTrue(kraus.get("stanford_affiliation_confirmed"))\n        self.assertIn("Stanford University", kraus.get("stanford_source", ""))\n\n    def test_ui_identity_key_strips_sec_dot_leaders(self):\n        from pathlib import Path\n        html=(Path(__file__).parents[1]/"docs/prospect-research/index.html").read_text(encoding="utf-8")\n        self.assertIn('replace(/\\\\s*\\\\.{3,}\\\\s*$/g', html)\n'''
p.write_text(s,encoding='utf-8')
