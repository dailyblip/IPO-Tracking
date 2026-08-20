from pathlib import Path

# --- edgar_client: reusable business-location enrichment ---
p=Path('src/edgar_client.py'); s=p.read_text()
marker='''def get_primary_ticker(cik: str):\n'''
insert='''def get_business_location(cik: str) -> str:\n    """Return researcher-friendly issuer location from the SEC submissions profile.\n\n    Domestic issuers are rendered as City, ST. Foreign issuers are rendered as\n    country because that is the more useful prospect-research grouping.\n    """\n    headers = _get_headers()\n    padded_cik = str(cik).zfill(10)\n    url = EDGAR_SUBMISSIONS_URL.format(cik=padded_cik)\n    data = _request_json(url, headers)\n    address = data.get("addresses", {}).get("business", {}) or {}\n    country = str(address.get("countryOfIncorporation") or address.get("country") or "").strip()\n    city = str(address.get("city") or "").strip()\n    state = str(address.get("stateOrCountry") or address.get("state") or "").strip()\n    if country in ("", "US"):\n        parts = [part for part in (city, state) if part]\n        return ", ".join(parts)\n    return country\n\n\n'''
if 'def get_business_location' not in s:
    assert marker in s; s=s.replace(marker,insert+marker,1)
p.write_text(s)

# --- main: preserve role + issuer location on output rows ---
p=Path('src/main.py'); s=p.read_text()
marker='''def _mentions_stanford_university(bio_text):\n    return bool(re.search(r"\\bstanford\\s+university\\b", str(bio_text or ""), re.I))\n\n\n'''
insert='''def _role_from_bio(bio_text):\n    """Extract a conservative current title from the holder's filing bio."""\n    text = " ".join(str(bio_text or "").split())\n    patterns = [\n        r"(?:has served|serves) as (?:our|the) ([^.]{2,100}?)(?: since| and|\\.|,)",\n        r"(?:is|is currently) (?:our|the) ([^.]{2,100}?)(?:\\.|,| and)",\n    ]\n    for pattern in patterns:\n        match = re.search(pattern, text, re.I)\n        if match:\n            role = match.group(1).strip(" ,.;")\n            if role and len(role) <= 100:\n                return role\n    return None\n\n\n'''
if '_role_from_bio' not in s:
    assert marker in s; s=s.replace(marker,marker+insert,1)
# Add location once per filing
needle='''        lockup = parsed.get("lockup_info", {})\n        bios = parsed.get("management_bios", {})\n\n        rows = []\n'''
replacement='''        lockup = parsed.get("lockup_info", {})\n        bios = parsed.get("management_bios", {})\n        try:\n            business_location = edgar_client.get_business_location(cik)\n        except Exception as error:\n            print(f"[main] Warning: could not resolve issuer location for {company_name}: {error}")\n            business_location = ""\n\n        rows = []\n'''
if needle in s: s=s.replace(needle,replacement,1)
# Insert role and location in row dict
needle='''                "Current Price": current_price,\n                "Holder Name": holder_name,\n'''
replacement='''                "Current Price": current_price,\n                "Location": business_location,\n                "Holder Name": holder_name,\n                "Role": _role_from_bio(person_bio_text),\n'''
if needle in s: s=s.replace(needle,replacement,1)
p.write_text(s)

# --- dashboard_export: publish location cleanly and remove duplicate realized assignment ---
p=Path('src/dashboard_export.py'); s=p.read_text()
s=s.replace('''    "offering_price", "current_price", "price_updated", "lockup_end_date",\n''','''    "offering_price", "current_price", "price_updated", "location", "lockup_end_date",\n''',1)
s=s.replace('''    "current_price", "price_updated", "lockup_end_date", "holder_name", "shares",\n''','''    "current_price", "price_updated", "location", "lockup_end_date", "holder_name", "shares",\n''',1)
# remove duplicated realized block
s=s.replace('''            realized = _number(row.get("Cash Realized IPO"))\n            if realized is not None:\n                liquidity["cash_realized_ipo"] = realized\n            realized = _number(row.get("Cash Realized IPO"))\n            if realized is not None:\n                liquidity["cash_realized_ipo"] = realized\n''','''            realized = _number(row.get("Cash Realized IPO"))\n            if realized is not None:\n                liquidity["cash_realized_ipo"] = realized\n''')
needle='''            "price_updated": first.get("Last Updated") or None,\n            "lockup_end_date": lockup.get("end"),\n'''
replacement='''            "price_updated": first.get("Last Updated") or None,\n            "location": first.get("Location") or None,\n            "lockup_end_date": lockup.get("end"),\n'''
if needle in s: s=s.replace(needle,replacement,1)
needle='''                "price_updated": filing.get("price_updated"),\n                "lockup_end_date": filing.get("lockup_end_date"),\n'''
replacement='''                "price_updated": filing.get("price_updated"),\n                "location": filing.get("location"),\n                "lockup_end_date": filing.get("lockup_end_date"),\n'''
if needle in s: s=s.replace(needle,replacement,1)
p.write_text(s)

# --- Prospect UI hardening ---
p=Path('docs/prospect-research/index.html'); s=p.read_text()
s=s.replace('placeholder="Search company, ticker, form, or signal"','placeholder="Search company, ticker, person, role, or signal"')
s=s.replace('<th>Stage</th><th>Filed</th><th>IPO size / offering value</th>','<th>Stage</th><th>Filed</th><th>Location</th><th>IPO size / offering value</th>')
s=s.replace('<div id="companyFlags"></div><h3>Beneficial ownership</h3>','<div id="companyFlags"></div><div id="companyResearchSummary" class="callout"></div><div id="companyLockupTerms" class="callout" hidden></div><h3>Beneficial ownership</h3>')
old='''function money(v){const n=Number(v);if(!Number.isFinite(n)||n<=0)return "—";return new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",notation:n>=1e6?"compact":"standard",maximumFractionDigits:n>=1e9?1:0}).format(n)}\nfunction quote(v){const n=Number(v);return Number.isFinite(n)&&n>0?`$${n.toFixed(2)}`:"—"}function shareLabel(v){const n=Number(v);return Number.isFinite(n)?new Intl.NumberFormat("en-US",{maximumFractionDigits:0}).format(n):"—"}function dateLabel(v){'''
new='''function known(v){return v!==null&&v!==undefined&&v!==""}function money(v){if(!known(v))return "Not disclosed";const n=Number(v);if(!Number.isFinite(n))return "Not disclosed";if(n===0)return "$0";if(n<0)return "Not disclosed";return new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",notation:n>=1e6?"compact":"standard",maximumFractionDigits:n>=1e9?1:0}).format(n)}\nfunction quote(v){if(!known(v))return "Not disclosed";const n=Number(v);return Number.isFinite(n)&&n>=0?`$${n.toFixed(2)}`:"Not disclosed"}function shareLabel(v){if(!known(v))return "Not disclosed";const n=Number(v);return Number.isFinite(n)?new Intl.NumberFormat("en-US",{maximumFractionDigits:0}).format(n):"Not disclosed"}function percentLabel(v){if(!known(v))return "Not disclosed";const n=Number(v);return Number.isFinite(n)?`${n.toLocaleString("en-US",{maximumFractionDigits:2})}%`:"Not disclosed"}function dateLabel(v){'''
assert old in s; s=s.replace(old,new,1)
# structured research helper replacements
old='''function daysTo(v){if(!v)return null;const d=new Date(v+"T00:00:00Z"),now=new Date();return Math.ceil((d-now)/86400000)}function hasSelling(f){return (f.signals||[]).some(x=>/selling stockholder|secondary/i.test(x))}function visible(){const q=$("search").value.trim().toLowerCase(),stage=$("stageFilter").value,owner=$("ownerFilter").value,research=$("researchFilter").value;return filings.filter(f=>{const people=Array.isArray(f.people)?f.people:[],hay=[f.company,f.ticker,f.form,f.stage,...(f.signals||[])].join(" ").toLowerCase();const d=daysTo(f.lockup_end_date);const researchOk=!research||(research==="major"&&isMajor(f))||(research==="stanford"&&hasStanford(f))||(research==="lockup90"&&d!==null&&d>=0&&d<=90)||(research==="selling"&&hasSelling(f));return(!q||hay.includes(q))&&(!stage||f.stage===stage)&&(!owner||(owner==="with"?people.length>0:people.length===0))&&researchOk})}'''
new='''function daysTo(v){if(!v)return null;const d=new Date(v+"T00:00:00Z"),now=new Date();return Math.ceil((d-now)/86400000)}function holderLockups(f){return [f.lockup_end_date,...(f.people||[]).map(p=>p.lockup_end_date)].filter(Boolean)}function nearestLockup(f){const future=holderLockups(f).map(v=>({v,d:daysTo(v)})).filter(x=>x.d!==null&&x.d>=0).sort((a,b)=>a.d-b.d);return future[0]||null}function hasSelling(f){return (f.people||[]).some(p=>Number(p.shares_sold_ipo)>0||Number(p.cash_realized_ipo)>0)||(f.signals||[]).some(x=>/selling stockholder|secondary/i.test(x))}function visible(){const q=$("search").value.trim().toLowerCase(),stage=$("stageFilter").value,owner=$("ownerFilter").value,research=$("researchFilter").value;return filings.filter(f=>{const people=Array.isArray(f.people)?f.people:[],personText=people.flatMap(p=>[p.name,p.role,p.stanford_source]).join(" "),hay=[f.company,f.ticker,f.form,f.stage,f.location,personText,...(f.signals||[])].join(" ").toLowerCase();const next=nearestLockup(f),d=next?.d??null;const researchOk=!research||(research==="major"&&isMajor(f))||(research==="stanford"&&hasStanford(f))||(research==="lockup90"&&d!==null&&d<=90)||(research==="selling"&&hasSelling(f));return(!q||hay.includes(q))&&(!stage||f.stage===stage)&&(!owner||(owner==="with"?people.length>0:people.length===0))&&researchOk})}'''
assert old in s; s=s.replace(old,new,1)
# render main row and metric lockups
s=s.replace('''const vals=[f.company,f.ticker||"—",f.stage||"—",dateLabel(f.filed),money(f.ipo_size||f.value),quote(f.offering_price),quote(f.current_price),String((f.people||[]).length),dateLabel(f.lockup_end_date)];''','''const next=nearestLockup(f),vals=[f.company,f.ticker||"—",f.stage||"—",dateLabel(f.filed),f.location||"Not disclosed",money(f.ipo_size||f.value),quote(f.offering_price),quote(f.current_price),String((f.people||[]).length),next?dateLabel(next.v):(f.lockup_text?"Structured terms":"Unknown")];''')
s=s.replace('''$("lockupMetric").textContent=filings.filter(f=>{const d=daysTo(f.lockup_end_date);return d!==null&&d>=0&&d<=90}).length''','''$("lockupMetric").textContent=filings.filter(f=>{const x=nearestLockup(f);return x&&x.d<=90}).length''')
# company meta, counts, research summary and lockup terms
old='''$("companyMeta").textContent=`${f.ticker||"No ticker"} · ${f.form||"SEC filing"} · ${f.stage||""} · filed ${dateLabel(f.filed)}`;$("companyValue").textContent=money(f.ipo_size||f.value);$("companyIpoPrice").textContent=quote(f.offering_price);$("companyCurrentPrice").textContent=quote(f.current_price);$("companyOwners").textContent=(f.people||[]).length;$("companyLockup").textContent=dateLabel(f.lockup_end_date);const flags=$("companyFlags");'''
new='''$("companyMeta").textContent=`${f.ticker||"No ticker"} · ${f.form||"SEC filing"} · ${f.stage||""} · filed ${dateLabel(f.filed)}${f.location?` · ${f.location}`:""}`;$("companyValue").textContent=money(f.ipo_size||f.value);$("companyIpoPrice").textContent=quote(f.offering_price);$("companyCurrentPrice").textContent=quote(f.current_price);const people=f.people||[],individuals=people.filter(p=>p.holder_type==="Individual"),entities=people.length-individuals.length;$("companyOwners").textContent=`${people.length} records · ${individuals.length} people`;const next=nearestLockup(f);$("companyLockup").textContent=next?dateLabel(next.v):(f.lockup_text?"Structured terms":"Unknown");const topIndividual=[...individuals].filter(p=>Number(p.cash_value)>0).sort((a,b)=>Number(b.cash_value)-Number(a.cash_value))[0],topSeller=[...people].filter(p=>Number(p.cash_realized_ipo)>0).sort((a,b)=>Number(b.cash_realized_ipo)-Number(a.cash_realized_ipo))[0],stanfordCount=people.filter(isStanfordPerson).length,sellerCount=people.filter(p=>Number(p.shares_sold_ipo)>0||Number(p.cash_realized_ipo)>0).length;$("companyResearchSummary").innerHTML=`<span class="sub">Research snapshot</span><strong>${individuals.length} individuals · ${entities} entities/funds · ${sellerCount} selling holders · ${stanfordCount} Stanford-linked</strong><div class="sub">Top individual stake: ${topIndividual?`${topIndividual.name} · ${money(topIndividual.cash_value)}`:"Not classified"} · Largest disclosed IPO cash proceeds: ${topSeller?`${topSeller.name} · ${money(topSeller.cash_realized_ipo)}`:"Not disclosed"}</div>`;const lt=$("companyLockupTerms");lt.hidden=!f.lockup_text;if(f.lockup_text)lt.innerHTML=`<span class="sub">Lock-up terms from filing</span><strong>${next?`Next tracked release ${dateLabel(next.v)}`:"Structured terms require holder mapping"}</strong><div class="sub">${f.lockup_text}</div>`;const flags=$("companyFlags");'''
assert old in s; s=s.replace(old,new,1)
# owner grid percent + cash semantics
s=s.replace('''p.ownership_percent_before??"Not disclosed",p.ownership_percent_after??p.ownership_percent??"Not disclosed",money(p.cash_realized_ipo),money(p.cash_value),money(p.liquid_value),money(p.locked_value)''','''percentLabel(p.ownership_percent_before),percentLabel(p.ownership_percent_after??p.ownership_percent),money(p.cash_realized_ipo),money(p.cash_value),money(p.liquid_value),money(p.locked_value)''')
# Person Stanford source precedence and lockup no company fallback masquerading as holder-specific
s=s.replace('''$("lockupEnd").textContent=dateLabel(p.lockup_end_date||selectedCompany.lockup_end_date);''','''$("lockupEnd").textContent=p.lockup_end_date?dateLabel(p.lockup_end_date):(selectedCompany.lockup_text?"See filing terms":"Unknown");''')
s=s.replace('''const so=stanfordSourceFor(p),sp=$("stanfordPerson");sp.hidden=!isStanfordPerson(p);$("stanfordSource").textContent=so?`Confirmed via ${so.source}`:"Confirmed Stanford University affiliation from public-source enrichment.";''','''const so=stanfordSourceFor(p),sp=$("stanfordPerson");sp.hidden=!isStanfordPerson(p);$("stanfordSource").textContent=p.stanford_source|| (so?`Confirmed via ${so.source}`:"Confirmed Stanford University affiliation from public-source enrichment.");''')
p.write_text(s)

# --- Tests: protect researcher-integrity behavior ---
p=Path('src/test_prospect_liquidity_site.py'); s=p.read_text()
marker='''    def test_researcher_workflow_fields_and_filters(self):'''
insert='''    def test_research_integrity_hardening(self):\n        for token in (\n            'Search company, ticker, person, role, or signal',\n            'function percentLabel',\n            'return "Not disclosed"',\n            'personText=people.flatMap',\n            'Number(p.shares_sold_ipo)>0',\n            'Research snapshot',\n            'Lock-up terms from filing',\n            'p.stanford_source||',\n            '<th>Location</th>',\n        ):\n            self.assertIn(token, self.html)\n        self.assertNotIn('dateLabel(p.lockup_end_date||selectedCompany.lockup_end_date)', self.html)\n\n'''
if 'test_research_integrity_hardening' not in s:
    assert marker in s; s=s.replace(marker,insert+marker,1)
p.write_text(s)

# Test location helper without network.
p=Path('src/test_edgar_client.py'); s=p.read_text()
if 'test_business_location_formats_domestic_and_foreign' not in s:
    before='''if __name__ == "__main__":\n    unittest.main()\n'''
    test='''    def test_business_location_formats_domestic_and_foreign(self):\n        with patch.object(edgar_client, "_request_json", return_value={"addresses":{"business":{"city":"Palo Alto","stateOrCountry":"CA","country":"US"}}}):\n            self.assertEqual(edgar_client.get_business_location("1"), "Palo Alto, CA")\n        with patch.object(edgar_client, "_request_json", return_value={"addresses":{"business":{"city":"Milan","stateOrCountry":"","country":"IT"}}}):\n            self.assertEqual(edgar_client.get_business_location("1"), "IT")\n\n'''
    assert before in s; s=s.replace(before,test+before,1)
p.write_text(s)
