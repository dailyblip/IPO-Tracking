from pathlib import Path
import json

# Merge calibration/backfill rows into the live feed without throwing away fresher
# prices or richer automatic fields. Person records merge by normalized name.
p=Path('docs/prospect-research/index.html'); s=p.read_text()
old='''function mergeFilings(primary,backfill){const byKey=new Map();for(const f of [...(primary||[]),...(backfill||[])]){const key=String(f.cik||f.id||f.company);const old=byKey.get(key);if(!old||String(f.form).toUpperCase()==="424B4"||String(old.form).toUpperCase()!=="424B4")byKey.set(key,f)}return [...byKey.values()].sort((a,b)=>String(b.filed||"").localeCompare(String(a.filed||"")))}'''
new='''function mergeKnown(base,extra){const out={...(base||{})};for(const [k,v] of Object.entries(extra||{}))if(v!==null&&v!==undefined&&v!=="")out[k]=v;return out}function mergePeople(base,extra){const by=new Map((base||[]).map(p=>[keyName(p.name),p]));for(const p of (extra||[])){const k=keyName(p.name);by.set(k,mergeKnown(by.get(k),p))}return [...by.values()]}function mergeFilings(primary,backfill){const byKey=new Map();for(const f of [...(primary||[]),...(backfill||[])]){const key=String(f.cik||f.id||f.company),old=byKey.get(key);if(!old){byKey.set(key,f);continue}const merged=mergeKnown(old,f);merged.people=mergePeople(old.people,f.people);merged.people_count=merged.people.length;byKey.set(key,merged)}return [...byKey.values()].sort((a,b)=>String(b.filed||"").localeCompare(String(a.filed||"")))}'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)

p=Path('docs/prospect-research/backfill.json')
data=json.loads(p.read_text())
spacex={
  "id":"backfill-spacex-424b4-2026-06-12",
  "company":"Space Exploration Technologies Corp.",
  "ticker":"SPCX",
  "cik":"0001181412",
  "form":"424B4",
  "filed":"2026-06-12",
  "stage":"Priced",
  "location":"Starbase, TX",
  "ipo_size":74999999925,
  "offering_price":135.0,
  "lockup_end_date":None,
  "lockup_text":"Founder Elon Musk: all owned common shares are subject to a 366-day lock-up from the June 11, 2026 pricing date, with no early release. Certain other shareholders have an extended lock-up through the second full trading day after release of results for the quarter ended June 30, 2027, with staged early releases. Other outstanding shares are generally subject to a 180-day lock-up with staged early releases. Holder class is not inferred unless explicitly mapped.",
  "signals":[
    "555,555,555 Class A shares offered at $135.00 per share (~$75.0B gross offering)",
    "Founder Elon Musk has a 366-day lock-up with no early-release provisions",
    "Other shareholders are covered by either extended staged lock-ups or a 180-day staged lock-up; holder-specific mapping remains conservative",
    "Stanford affiliations confirmed for director Ira Ehrenpreis and director Steve Jurvetson"
  ],
  "sec_url":"https://www.sec.gov/Archives/edgar/data/1181412/000162828026042639/0001628280-26-042639-index.html",
  "people":[
    {"name":"Elon Musk","holder_type":"Individual","role":"Founder, Chief Executive Officer, Chief Technical Officer and Chairman","shares":6068547515,"shares_after_ipo":6068547515,"ipo_value":819253414525,"liquid_shares":0,"locked_shares":6068547515,"lockup_end_date":"2027-06-12","lockup_scope":"holder-specific","liquidity_status":"Founder lock-up","liquidity_confidence":"High — final prospectus/underwriting agreement: founder shares locked for 366 days from June 11, 2026 pricing date with no early release. Share total excludes 350,000,000 Class B shares underlying options and includes 1,302,072,285 restricted Class B shares whose vesting remains performance/condition dependent.","stanford_university_bio":false},
    {"name":"Gwynne Shotwell","holder_type":"Individual","role":"President, Chief Operating Officer and Director","shares":12873160,"shares_after_ipo":12873160,"ipo_value":1737876600,"liquid_shares":null,"locked_shares":null,"lockup_scope":"filing-level","liquidity_status":"Lock-up class not mapped","liquidity_confidence":"Ownership confirmed in offering materials; applicable regular vs extended lock-up class is not inferred.","stanford_university_bio":false},
    {"name":"Bret Johnsen","holder_type":"Individual","role":"Chief Financial Officer","shares":9048565,"shares_after_ipo":9048565,"ipo_value":1221556275,"liquid_shares":null,"locked_shares":null,"lockup_scope":"filing-level","liquidity_status":"Lock-up class not mapped","liquidity_confidence":"Beneficial ownership figure includes options exercisable within 60 days; applicable lock-up class is not inferred.","stanford_university_bio":false},
    {"name":"Ira Ehrenpreis","holder_type":"Individual","role":"Director","shares":1373700,"shares_after_ipo":1373700,"ipo_value":185449500,"liquid_shares":null,"locked_shares":null,"lockup_scope":"filing-level","liquidity_status":"Lock-up class not mapped","liquidity_confidence":"809,050 Class A plus 564,650 Class B shares held by revocable trust; Class B converts 1:1 to Class A. Applicable lock-up class is not inferred.","stanford_university_bio":true,"stanford_source":"SpaceX filing bio states J.D. and M.B.A. from Stanford University and service on the Stanford Precourt Institute for Energy Advisory Council."},
    {"name":"Randy Glein","holder_type":"Individual","role":"Director","shares":277800,"shares_after_ipo":277800,"ipo_value":37503000,"liquid_shares":null,"locked_shares":null,"lockup_scope":"filing-level","liquidity_status":"Lock-up class not mapped","liquidity_confidence":"Ownership confirmed in offering materials; applicable lock-up class is not inferred.","stanford_university_bio":false},
    {"name":"Antonio J. Gracias","holder_type":"Individual","role":"Director","shares":503414530,"shares_after_ipo":503414530,"ipo_value":67960961550,"liquid_shares":null,"locked_shares":null,"lockup_scope":"filing-level","liquidity_status":"Lock-up class not mapped","liquidity_confidence":"Beneficial ownership is held through multiple affiliated entities; applicable lock-up class is not inferred.","stanford_university_bio":false},
    {"name":"Donald Harrison","holder_type":"Individual","role":"Director","shares":0,"shares_after_ipo":0,"ipo_value":0,"liquid_shares":0,"locked_shares":0,"liquidity_status":"No securities beneficially owned in offering table","liquidity_confidence":"High — offering table reports less than one percent/zero securities for this director.","stanford_university_bio":false},
    {"name":"Steve Jurvetson","holder_type":"Individual","role":"Director","shares":0,"shares_after_ipo":0,"ipo_value":0,"liquid_shares":0,"locked_shares":0,"liquidity_status":"No securities beneficially owned","liquidity_confidence":"High — SEC Form 3 explicitly states no securities are beneficially owned.","stanford_university_bio":true,"stanford_source":"Stanford Technology Ventures Program public profile confirms Stanford affiliation."},
    {"name":"Luke Nosek","holder_type":"Individual","role":"Director","shares":32987360,"shares_after_ipo":32987360,"ipo_value":4453293600,"liquid_shares":null,"locked_shares":null,"lockup_scope":"filing-level","liquidity_status":"Lock-up class not mapped","liquidity_confidence":"Ownership confirmed in offering materials; applicable lock-up class is not inferred.","stanford_university_bio":false}
  ]
}
data['filings']=[f for f in data.get('filings',[]) if str(f.get('cik'))!='0001181412']+[spacex]
p.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")

# Protect deep-merge semantics and SpaceX calibration record.
p=Path('src/test_prospect_liquidity_site.py'); s=p.read_text()
marker='''    def test_researcher_workflow_fields_and_filters(self):'''
insert='''    def test_calibration_backfill_preserves_fresh_live_fields(self):\n        self.assertIn('function mergeKnown', self.html)\n        self.assertIn('function mergePeople', self.html)\n        companies = {row["company"]: row for row in self.backfill["filings"]}\n        spacex = companies["Space Exploration Technologies Corp."]\n        self.assertEqual(spacex["ipo_size"], 74_999_999_925)\n        people = {p["name"]: p for p in spacex["people"]}\n        self.assertEqual(people["Elon Musk"]["lockup_end_date"], "2027-06-12")\n        self.assertEqual(people["Elon Musk"]["liquid_shares"], 0)\n        self.assertTrue(people["Ira Ehrenpreis"]["stanford_university_bio"])\n        self.assertEqual(people["Steve Jurvetson"]["shares"], 0)\n\n'''
if 'test_calibration_backfill_preserves_fresh_live_fields' not in s:
    assert marker in s; s=s.replace(marker,insert+marker,1)
p.write_text(s)
