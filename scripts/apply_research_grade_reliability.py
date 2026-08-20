from pathlib import Path
import re

# filing_parser: use the structured lock-up parser against the full prospectus text.
p=Path('src/filing_parser.py'); s=p.read_text(encoding='utf-8')
if 'from lockup_parser import extract_holder_lockup_info' not in s:
    s=s.replace('from ownership_parser import extract_rich_stockholders\n', 'from ownership_parser import extract_rich_stockholders\nfrom lockup_parser import extract_holder_lockup_info\n', 1)
start=s.index('def extract_lockup_info(soup: BeautifulSoup) -> dict:')
end=s.index('\n\ndef parse_filing(', start)
replacement='''def extract_lockup_info(soup: BeautifulSoup) -> dict:\n    """Extract structured holder-facing lock-up terms from the full prospectus."""\n    full_text = soup.get_text(" ", strip=True)\n    return extract_holder_lockup_info(full_text)\n'''
s=s[:start]+replacement+s[end:]
p.write_text(s,encoding='utf-8')

# main: preserve structured lock-up evidence all the way downstream.
p=Path('src/main.py'); s=p.read_text(encoding='utf-8')
if 'import json\n' not in s:
    s=s.replace('import os\n', 'import os\nimport json\n', 1)
old='''                "Lock-Up Expiry": lockup.get("raw_text", "")[:200] if lockup.get("raw_text") else "",\n                "Last Updated": date.today().isoformat(),\n'''
new='''                # Keep legacy Lock-Up Expiry for Sheet compatibility, but structured\n                # fields below are authoritative for the Prospect Research product.\n                "Lock-Up Expiry": "",\n                "Lock-Up Text": lockup.get("raw_text") or "",\n                "Lock-Up Duration Days": lockup.get("duration_days"),\n                "Lock-Up Duration Value": lockup.get("duration_value"),\n                "Lock-Up Duration Unit": lockup.get("duration_unit"),\n                "Lock-Up Scope": lockup.get("scope") or "",\n                "Lock-Up Scope Tags": ",".join(lockup.get("scope_tags") or []),\n                "Lock-Up Terms JSON": json.dumps(lockup.get("terms") or [], ensure_ascii=False),\n                "Lock-Up Confidence": lockup.get("confidence") or "Unresolved",\n                "Lock-Up Structured": bool(lockup.get("structured")),\n                "Lock-Up Language Present": bool(\n                    lockup.get("raw_text")\n                    or parsed.get("diagnostics", {}).get("underwriting_keyword_present")\n                ),\n                "Last Updated": date.today().isoformat(),\n'''
assert old in s, 'main lock-up row snippet changed'
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# dashboard_export: structured dates, conservative holder mapping, public provenance.
p=Path('src/dashboard_export.py'); s=p.read_text(encoding='utf-8')
if 'import calendar\n' not in s:
    s=s.replace('import csv\n', 'import csv\nimport calendar\n', 1)
# Expand public filing/person fields.
s=s.replace('''    "lockup_duration_days", "lockup_text",\n}''','''    "lockup_duration_days", "lockup_duration_value", "lockup_duration_unit",\n    "lockup_text", "lockup_scope", "lockup_terms", "lockup_confidence",\n}''',1)
s=s.replace('''    "lockup_end_date", "lockup_scope", "valuation_as_of",\n}''','''    "lockup_end_date", "lockup_scope", "lockup_duration_days", "lockup_duration_value",\n    "lockup_duration_unit", "lockup_schedule", "lockup_text", "valuation_as_of",\n}''',1)
start=s.index('def _lockup_metadata(rows):')
end=s.index('\n\ndef _signals(', start)
replacement=r'''def _add_duration(start_date, value, unit):
    if not start_date or value in (None, "") or not unit:
        return None
    try:
        base = datetime.fromisoformat(str(start_date)).date()
        value = int(value)
    except (TypeError, ValueError):
        return None
    unit = str(unit).lower()
    if unit == "days":
        return (base + timedelta(days=value)).isoformat()
    if unit == "months":
        month_index = base.month - 1 + value
        year = base.year + month_index // 12
        month = month_index % 12 + 1
        day = min(base.day, calendar.monthrange(year, month)[1])
        return base.replace(year=year, month=month, day=day).isoformat()
    if unit == "years":
        try:
            return base.replace(year=base.year + value).isoformat()
        except ValueError:
            return base.replace(month=2, day=28, year=base.year + value).isoformat()
    return None


def _parse_terms(value):
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _lockup_metadata(rows):
    text = next((str(row.get("Lock-Up Text") or "") for row in rows if row.get("Lock-Up Text")), "")
    value = next((row.get("Lock-Up Duration Value") for row in rows if row.get("Lock-Up Duration Value") not in (None, "")), None)
    unit = next((row.get("Lock-Up Duration Unit") for row in rows if row.get("Lock-Up Duration Unit")), None)
    days = next((row.get("Lock-Up Duration Days") for row in rows if row.get("Lock-Up Duration Days") not in (None, "")), None)
    scope = next((row.get("Lock-Up Scope") for row in rows if row.get("Lock-Up Scope")), None)
    tags_raw = next((row.get("Lock-Up Scope Tags") for row in rows if row.get("Lock-Up Scope Tags")), "")
    tags = [tag.strip() for tag in str(tags_raw).split(",") if tag.strip()]
    terms = _parse_terms(next((row.get("Lock-Up Terms JSON") for row in rows if row.get("Lock-Up Terms JSON")), "[]"))
    confidence = next((row.get("Lock-Up Confidence") for row in rows if row.get("Lock-Up Confidence")), None)

    # Backward compatibility for historical rows generated before structured fields.
    if not text:
        legacy = next((str(row.get("Lock-Up Expiry") or "") for row in rows if row.get("Lock-Up Expiry")), "")
        if legacy and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", legacy):
            text = legacy
    if value is None and text:
        match = re.search(r"(\d{2,3})\s+days", text, re.I)
        if match:
            value, unit, days = int(match.group(1)), "days", int(match.group(1))

    pricing = next((str(row.get("Date of Pricing") or "") for row in rows if row.get("Date of Pricing")), "")
    end = _add_duration(pricing, value, unit)
    enriched_terms = []
    for term in terms:
        if not isinstance(term, dict):
            continue
        item = dict(term)
        item["end_date"] = _add_duration(pricing, item.get("duration_value"), item.get("duration_unit"))
        enriched_terms.append(item)
    return {
        "text": text or None, "days": int(days) if str(days or "").isdigit() else None,
        "value": int(value) if str(value or "").isdigit() else value, "unit": unit,
        "scope": scope, "scope_tags": tags, "terms": enriched_terms,
        "confidence": confidence, "end": end,
    }


def _role_matches_scope(role, tags, shares_sold=None):
    role = str(role or "").lower()
    tags = set(tags or [])
    if tags & {"substantially_all_holders", "all_other_holders"}:
        return True
    if "directors" in tags and any(word in role for word in ("director", "chair")):
        return True
    if "executive_officers" in tags and any(word in role for word in ("chief", "president", "officer", "general counsel", "treasurer")):
        return True
    if "selling_stockholders" in tags and (_number(shares_sold) or 0) > 0:
        return True
    return False


def _applicable_lockup(lockup, name, metadata, row):
    name_key = _holder_identity_key(name)
    special = []
    for term in lockup.get("terms") or []:
        holder = term.get("special_holder")
        if holder and _holder_identity_key(holder) in {name_key, _holder_identity_key(name).replace("entities affiliated with ", "")}:
            special.append(term)
        elif holder and name_key and (_holder_identity_key(holder) in name_key or name_key in _holder_identity_key(holder)):
            special.append(term)
    if special:
        return {"terms": special, "special": True}
    if _role_matches_scope(metadata.get("role"), lockup.get("scope_tags"), row.get("Shares Sold in IPO")):
        primary = {
            "duration_value": lockup.get("value"), "duration_unit": lockup.get("unit"),
            "duration_days": lockup.get("days"), "end_date": lockup.get("end"),
            "scope": lockup.get("scope"), "scope_tags": lockup.get("scope_tags"),
            "source_text": lockup.get("text"), "has_staggered_releases": False,
        }
        return {"terms": [primary] if lockup.get("value") else [], "special": False}
    return {"terms": [], "special": False}


def _person_liquidity(shares, current_value, ipo_price, lockup, name, metadata, row):
    shares = _number(shares); current_value = _number(current_value); ipo_price = _number(ipo_price)
    ipo_value = shares * ipo_price if shares is not None and ipo_price else None
    base = {"ipo_value": ipo_value, "cash_realized_ipo": None}
    if shares is None:
        return {**base, "liquid_shares": None, "liquid_value": None, "locked_shares": None, "locked_value": None, "liquidity_status": "Unknown", "liquidity_confidence": "Unknown — share count unavailable", "lockup_schedule": []}

    applicable = _applicable_lockup(lockup, name, metadata, row)
    terms = applicable.get("terms") or []
    schedule = [
        {k: term.get(k) for k in ("duration_value", "duration_unit", "end_date", "scope", "special_holder", "source_text", "has_staggered_releases")}
        for term in terms if term.get("duration_value")
    ]
    if not schedule:
        return {**base, "liquid_shares": None, "liquid_value": None, "locked_shares": None, "locked_value": None, "liquidity_status": "Unclassified", "liquidity_confidence": "Unknown — filing has no defensible holder-specific lock-up mapping", "lockup_schedule": []}

    end_dates = [item.get("end_date") for item in schedule if item.get("end_date")]
    final_end = max(end_dates) if end_dates else None
    staged = len(schedule) > 1 or any(item.get("has_staggered_releases") for item in schedule)
    if staged:
        return {**base, "liquid_shares": None, "liquid_value": None, "locked_shares": None, "locked_value": None, "liquidity_status": "Staggered lock-up — tranche mapping pending", "liquidity_confidence": "High-confidence lock-up schedule found; tranche quantities are not inferred", "lockup_schedule": schedule, "lockup_end_date": final_end}

    end = final_end
    try:
        active = bool(end) and datetime.fromisoformat(end).date() > datetime.now(timezone.utc).date()
    except ValueError:
        active = False
    if end:
        return {**base, "liquid_shares": 0 if active else shares, "liquid_value": 0 if active else current_value, "locked_shares": shares if active else 0, "locked_value": current_value if active else 0, "liquidity_status": "Locked" if active else "Lock-up expired", "liquidity_confidence": "High-confidence holder class mapping from final prospectus; disclosed exceptions may still apply", "lockup_schedule": schedule, "lockup_end_date": end}
    return {**base, "liquid_shares": None, "liquid_value": None, "locked_shares": None, "locked_value": None, "liquidity_status": "Lock-up terms found; date unresolved", "liquidity_confidence": "Lock-up coverage found but release date could not be calculated", "lockup_schedule": schedule}
'''
s=s[:start]+replacement+s[end:]
# Build people: calculate metadata before liquidity and expose structured fields.
old='''            shares = _number(row.get("Shares")); cash_value = _number(row.get("Cash Value"))\n            liquidity = _person_liquidity(shares, cash_value, _number(first.get("Actual Price")), lockup)\n            metadata = prospect_person_metadata(row, name)\n            realized = _number(row.get("Cash Realized IPO"))\n'''
new='''            shares = _number(row.get("Shares After IPO"))\n            if shares is None:\n                shares = _number(row.get("Shares"))\n            cash_value = _number(row.get("Cash Value"))\n            metadata = prospect_person_metadata(row, name)\n            liquidity = _person_liquidity(shares, cash_value, _number(first.get("Actual Price")), lockup, name, metadata, row)\n            realized = _number(row.get("Cash Realized IPO"))\n'''
assert old in s, 'dashboard people snippet changed'
s=s.replace(old,new,1)
old='''            people.append({"name": name, "shares": shares, "cash_value": cash_value, "stanford_university_bio": _boolean(row.get("Stanford University in Bio")), "lockup_end_date": lockup.get("end"), "lockup_scope": "filing-level" if lockup.get("text") else None, "valuation_as_of": first.get("Last Updated") or None, **metadata, **liquidity})\n'''
new='''            person_lockup_end = liquidity.get("lockup_end_date")\n            people.append({"name": name, "shares": shares, "cash_value": cash_value, "stanford_university_bio": _boolean(row.get("Stanford University in Bio")), "lockup_end_date": person_lockup_end, "lockup_scope": "holder-mapped" if person_lockup_end or liquidity.get("lockup_schedule") else ("filing-level-unmapped" if lockup.get("text") else None), "lockup_duration_days": lockup.get("days"), "lockup_duration_value": lockup.get("value"), "lockup_duration_unit": lockup.get("unit"), "lockup_text": lockup.get("text"), "valuation_as_of": first.get("Last Updated") or None, **metadata, **liquidity})\n'''
assert old in s, 'dashboard people append snippet changed'
s=s.replace(old,new,1)
old='''            "lockup_end_date": lockup.get("end"),\n            "lockup_duration_days": lockup.get("days"),\n            "lockup_text": lockup.get("text"),\n'''
new='''            "lockup_end_date": lockup.get("end"),\n            "lockup_duration_days": lockup.get("days"),\n            "lockup_duration_value": lockup.get("value"),\n            "lockup_duration_unit": lockup.get("unit"),\n            "lockup_text": lockup.get("text"),\n            "lockup_scope": lockup.get("scope"),\n            "lockup_terms": lockup.get("terms"),\n            "lockup_confidence": lockup.get("confidence"),\n'''
assert old in s, 'dashboard filing lockup snippet changed'
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# QC: stop treating raw lock-up prose as an ISO date; make missing structure a hard QA issue.
p=Path('src/qc_review.py'); s=p.read_text(encoding='utf-8')
s=s.replace('MAX_LOCKUP_DAYS = 365', 'MAX_LOCKUP_DAYS = 730', 1)
start=s.index('def check_lockup_date(row: dict, ipo_date: str = None) -> list:')
end=s.index('\n\ndef check_against_previous(', start)
replacement='''def check_lockup_date(row: dict, ipo_date: str = None) -> list:\n    """Validate structured lock-up extraction without mistaking source prose for a date."""\n    issues = []\n    language_present = bool(row.get("Lock-Up Language Present"))\n    text = str(row.get("Lock-Up Text") or "").strip()\n    value = _to_int(row.get("Lock-Up Duration Value"))\n    unit = str(row.get("Lock-Up Duration Unit") or "").strip().lower()\n    terms_raw = row.get("Lock-Up Terms JSON") or "[]"\n    try:\n        terms = json.loads(terms_raw) if isinstance(terms_raw, str) else terms_raw\n    except json.JSONDecodeError:\n        terms = []\n        issues.append("Lock-up terms JSON is invalid")\n\n    if language_present and not text and not terms:\n        issues.append("Prospectus contains lock-up language but no holder lock-up terms were structured")\n    if text and not terms and value is None:\n        issues.append("Lock-up source text captured but duration/schedule was not structured")\n    if value is not None and unit not in {"days", "months", "years"}:\n        issues.append("Lock-up duration has an invalid or missing unit")\n    if unit == "days" and value is not None and not (MIN_LOCKUP_DAYS <= value <= MAX_LOCKUP_DAYS):\n        issues.append(f"Lock-up duration ({value} days) outside plausible {MIN_LOCKUP_DAYS}-{MAX_LOCKUP_DAYS} day range")\n    if unit == "months" and value is not None and not (1 <= value <= 24):\n        issues.append(f"Lock-up duration ({value} months) outside plausible range")\n    if unit == "years" and value is not None and not (1 <= value <= 3):\n        issues.append(f"Lock-up duration ({value} years) outside plausible range")\n    return issues\n'''
s=s[:start]+replacement+s[end:]
p.write_text(s,encoding='utf-8')

# Prospect UI: restore researcher controls/provenance and show structured schedules explicitly.
p=Path('docs/prospect-research/index.html'); s=p.read_text(encoding='utf-8')
s=s.replace('''<select class="control" id="researchFilter"><option value="">All research signals</option><option value="major">$500M+ IPO</option><option value="stanford">Stanford connection</option><option value="lockup90">Lock-up ≤90 days</option><option value="selling">Selling shareholders</option></select></div>''','''<select class="control" id="researchFilter"><option value="">All research signals</option><option value="major">$500M+ IPO</option><option value="stanford">Stanford connection</option><option value="lockup90">Lock-up ≤90 days</option><option value="selling">Selling shareholders</option></select><button class="secondary" id="clearFilters">Clear filters</button></div>''',1)
s=s.replace('grid-template-columns:minmax(260px,1fr) 170px 170px 190px;', 'grid-template-columns:minmax(260px,1fr) 150px 170px 190px 120px;', 1)
s=s.replace('''<div id="companyFlags"></div><div id="companyResearchSummary" class="callout"></div><div id="companyLockupTerms" class="callout" hidden></div><h3>Beneficial ownership</h3>''','''<div id="companyFlags"></div><div id="companyResearchSummary" class="callout"></div><div id="companyLockupTerms" class="callout" hidden></div><div id="companySignals" class="callout" hidden></div><div class="callout"><span class="sub">Primary SEC source</span><strong><a id="companySecSource" target="_blank" rel="noopener">Open final prospectus</a></strong></div><h3>Beneficial ownership</h3>''',1)
# Add person role/ownership context and lock-up schedule callout.
s=s.replace('''<div id="stanfordPerson" class="callout" hidden>''','''<div id="personResearchContext" class="callout"></div><div id="stanfordPerson" class="callout" hidden>''',1)
s=s.replace('''<div class="callout"><span class="sub">Classification confidence</span><strong id="confidence">Unknown</strong></div>''','''<div id="personLockupSchedule" class="callout" hidden></div><div class="callout"><span class="sub">Classification confidence</span><strong id="confidence">Unknown</strong></div>''',1)
# Company structured display/provenance.
needle='''const lt=$("companyLockupTerms");lt.hidden=!f.lockup_text;if(f.lockup_text)lt.innerHTML=`<span class="sub">Lock-up terms from filing</span><strong>${next?`Next tracked release ${dateLabel(next.v)}`:"Structured terms require holder mapping"}</strong><div class="sub">${f.lockup_text}</div>`;const flags=$("companyFlags");'''
repl='''const lt=$("companyLockupTerms"),terms=Array.isArray(f.lockup_terms)?f.lockup_terms:[];lt.hidden=!(f.lockup_text||terms.length);if(!lt.hidden){const termText=terms.length?terms.map(t=>`${t.special_holder?`${t.special_holder}: `:""}${t.duration_value||"?"} ${t.duration_unit||""}${t.end_date?` · ${dateLabel(t.end_date)}`:""}${t.scope?` · ${t.scope}`:""}`).join(" | "):"";lt.innerHTML=`<span class="sub">Lock-up terms from filing</span><strong>${next?`Next tracked release ${dateLabel(next.v)}`:(f.lockup_duration_value?`${f.lockup_duration_value} ${f.lockup_duration_unit||""}`:"Structured terms require holder mapping")}</strong><div class="sub">${termText||f.lockup_text||"No structured source excerpt"}</div>`}const sig=$("companySignals");sig.hidden=!(f.signals||[]).length;if(!sig.hidden)sig.innerHTML=`<span class="sub">Research signals</span><strong>${(f.signals||[]).join(" · ")}</strong>`;$("companySecSource").href=f.sec_url||"https://www.sec.gov/edgar/search/";const flags=$("companyFlags");'''
assert needle in s, 'company lockup UI snippet changed'
s=s.replace(needle,repl,1)
# Person context, schedule, and total shares use post-IPO shares consistently.
s=s.replace('''$("personMeta").textContent=`${selectedCompany.company}${selectedCompany.ticker?` · ${selectedCompany.ticker}`:""}`;''','''$("personMeta").textContent=`${selectedCompany.company}${selectedCompany.ticker?` · ${selectedCompany.ticker}`:""}${p.role?` · ${p.role}`:""}`;$("personResearchContext").innerHTML=`<span class="sub">Research context</span><strong>${p.holder_type||"Unknown holder type"}${p.role?` · ${p.role}`:""}${known(p.ownership_percent_after??p.ownership_percent)?` · ${percentLabel(p.ownership_percent_after??p.ownership_percent)} post-IPO ownership`:""}</strong>`;''',1)
s=s.replace('''const total=Number(p.shares)||0,liquid=''', '''const total=Number(p.shares_after_ipo??p.shares)||0,liquid=''',1)
needle='''$("valuationAsOf").textContent=p.valuation_as_of?`Current-value estimate as of ${dateLabel(p.valuation_as_of)}`:"Current valuation date not available";$("confidence").textContent=p.liquidity_confidence||"Unknown";personDetail.showModal()}'''
repl='''$("valuationAsOf").textContent=p.valuation_as_of?`Current-value estimate as of ${dateLabel(p.valuation_as_of)}`:"Current valuation date not available";const ps=$("personLockupSchedule"),schedule=Array.isArray(p.lockup_schedule)?p.lockup_schedule:[];ps.hidden=!schedule.length;if(schedule.length)ps.innerHTML=`<span class="sub">Holder lock-up schedule</span><strong>${schedule.map(x=>`${x.duration_value||"?"} ${x.duration_unit||""}${x.end_date?` · ${dateLabel(x.end_date)}`:""}`).join(" | ")}</strong><div class="sub">Only terms mapped to this holder are shown; staged tranche quantities remain unclassified unless explicitly disclosed.</div>`;$("confidence").textContent=p.liquidity_confidence||"Unknown";personDetail.showModal()}'''
assert needle in s, 'person schedule UI snippet changed'
s=s.replace(needle,repl,1)
# Clear filters behavior.
s=s.replace('''$("search").addEventListener("input",render);''','''$("search").addEventListener("input",render);$("clearFilters").addEventListener("click",()=>{$("search").value="";$("stageFilter").value="";$("ownerFilter").value="";$("researchFilter").value="";render()});''',1)
p.write_text(s,encoding='utf-8')

# Tests for real failure modes and feature regression protection.
p=Path('src/test_lockup_parser.py')
p.write_text(r'''import unittest
from lockup_parser import extract_holder_lockup_info


class LockupParserResearchGradeTests(unittest.TestCase):
    def test_neutron_prefers_160_day_holder_lockup_over_registration_rights_180_days(self):
        text = """
        Registration Rights. At any time beginning 180 days after the effective date, holders may request Form S-1 registration.
        Lock-Up and Market Standoff Agreements. We and all of our directors, executive officers, the selling stockholders,
        and certain other record holders are subject to lock-up agreements with the underwriters and will not transfer
        Lock-Up Securities during the period ending on 160 days after the date of this prospectus (the Lock-Up Period).
        """
        info = extract_holder_lockup_info(text)
        self.assertEqual(info["duration_value"], 160)
        self.assertEqual(info["duration_unit"], "days")
        self.assertIn("directors", info["scope_tags"])
        self.assertIn("selling_stockholders", info["scope_tags"])

    def test_space_x_keeps_founder_schedule_separate_from_general_lockup(self):
        text = """
        LOCK-UP PERIOD (i) 366-day lock-up for Elon Musk; (ii) staggered lock-up release for a portion of shares held by
        select investors, officers, and directors starting after Q4 26 earnings through Q2 27 earnings; and
        (iii) staggered early lock-up release for all other shares starting after Q2 26 earnings through 180 days after the IPO date.
        """
        info = extract_holder_lockup_info(text)
        self.assertTrue(info["structured"])
        self.assertEqual(info["duration_value"], 180)
        self.assertTrue(any(t.get("special_holder") == "Elon Musk" and t["duration_value"] == 366 for t in info["terms"]))

    def test_holder_six_month_term_beats_issuer_only_90_day_term(self):
        text = """
        Lock-Up Agreements. We have agreed for a period of 90 days after the offering not to issue additional securities.
        Furthermore, each of our directors and executive officers and all holders of 5% or more of our shares have agreed,
        subject to certain exceptions, not to dispose of their shares for a period of six (6) months after this offering is completed
        without the prior written consent of the underwriter.
        """
        info = extract_holder_lockup_info(text)
        self.assertEqual(info["duration_value"], 6)
        self.assertEqual(info["duration_unit"], "months")
        self.assertIn("directors", info["scope_tags"])

    def test_no_lockup_language_stays_unresolved(self):
        info = extract_holder_lockup_info("This prospectus discusses revenue and customers only.")
        self.assertIsNone(info["duration_value"])
        self.assertEqual(info["terms"], [])

if __name__ == "__main__":
    unittest.main()
''', encoding='utf-8')

p=Path('src/test_prospect_liquidity_site.py'); s=p.read_text(encoding='utf-8')
if 'test_research_grade_feature_regression_contract' not in s:
    s += r'''\n\nclass ProspectResearchGradeRegressionTests(unittest.TestCase):\n    def test_research_grade_feature_regression_contract(self):\n        from pathlib import Path\n        html=(Path(__file__).parents[1]/"docs/prospect-research/index.html").read_text(encoding="utf-8")\n        for required in (\n            'id="clearFilters"', 'id="companySignals"', 'id="companySecSource"',\n            'id="personResearchContext"', 'id="personLockupSchedule"',\n            'Stanford connection', '$500M+ IPO', 'Selling shareholders',\n            'Before IPO', 'Sold in IPO', 'IPO Cash Proceeds', 'Current Value',\n            'Liquid Now', 'Locked / Restricted', 'Classification confidence',\n        ):\n            self.assertIn(required, html)\n'''
p.write_text(s,encoding='utf-8')
