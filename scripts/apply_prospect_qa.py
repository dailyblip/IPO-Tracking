from pathlib import Path

# filing_parser.py: strengthen offering-price extraction and filing-first location
p=Path('src/filing_parser.py'); s=p.read_text(encoding='utf-8')
old='''    price_patterns = [\n        r"initial public offering price(?:\\s+per\\s+share)?"\n        r"\\s*(?:is|:)?\\s*\\$\\s*(\\d{1,4}(?:\\.\\d{1,2})?)",\n        r"public offering price(?:\\s+per\\s+share)?"\n        r"\\s*(?:is|:)?\\s*\\$\\s*(\\d{1,4}(?:\\.\\d{1,2})?)",\n        r"\\$\\s*(\\d{1,4}(?:\\.\\d{1,2})?)\\s+per\\s+share",\n    ]\n'''
new='''    price_patterns = [\n        r"initial public offering price(?:\\s+per\\s+share)?"\n        r"\\s*(?:is|:)?\\s*\\$\\s*(\\d{1,4}(?:\\.\\d{1,2})?)",\n        r"public offering price(?:\\s+per\\s+share)?"\n        r"\\s*(?:is|:)?\\s*\\$\\s*(\\d{1,4}(?:\\.\\d{1,2})?)",\n        r"price\\s+to\\s+(?:the\\s+)?public(?:\\s+per\\s+share)?\\s*[:\\-]?\\s*\\$\\s*(\\d{1,4}(?:\\.\\d{1,2})?)",\n        r"offering\\s+price\\s+per\\s+share\\s*[:\\-]?\\s*\\$\\s*(\\d{1,4}(?:\\.\\d{1,2})?)",\n        r"\\$\\s*(\\d{1,4}(?:\\.\\d{1,2})?)\\s+per\\s+(?:ordinary\\s+|class\\s+[ab]\\s+)?share",\n    ]\n'''
assert old in s
s=s.replace(old,new,1)
marker='''\ndef extract_price_range(soup: BeautifulSoup) -> dict:\n'''
insert='''\ndef extract_principal_office_location(soup: BeautifulSoup):\n    """Extract principal executive office location from the filing cover page.\n\n    Prefer filing disclosure to SEC submissions metadata because the latter may\n    reflect a registered/business address that is not the research-relevant HQ.\n    Returns a compact ``City, ST`` for US addresses, otherwise None.\n    """\n    cover_text = soup.get_text(" ", strip=True)[:30000]\n    patterns = [\n        r"principal executive offices? (?:are|is) located at [^.;]{0,220}?\\b([A-Za-z .'-]{2,60}),\\s*([A-Z]{2})\\s+\\d{5}(?:-\\d{4})?",\n        r"principal executive offices?[^.;]{0,220}?\\b([A-Za-z .'-]{2,60}),\\s*([A-Z]{2})\\s+\\d{5}(?:-\\d{4})?",\n        r"address of principal executive offices?[^.;]{0,220}?\\b([A-Za-z .'-]{2,60}),\\s*([A-Z]{2})\\s+\\d{5}(?:-\\d{4})?",\n    ]\n    for pattern in patterns:\n        match = re.search(pattern, cover_text, re.I)\n        if match:\n            city = " ".join(match.group(1).split()).strip(" ,")\n            state = match.group(2).upper()\n            if city and state:\n                return f"{city}, {state}"\n    return None\n\n\n'''
assert marker in s
s=s.replace(marker,insert+marker,1)
p.write_text(s,encoding='utf-8')

# main.py: filing-first location, deterministic post-IPO share derivation, normalized Stanford confirmation
p=Path('src/main.py'); s=p.read_text(encoding='utf-8')
old='''        try:\n            business_location = edgar_client.get_business_location(cik)\n        except Exception as error:\n            print(f"[main] Warning: could not resolve issuer location for {company_name}: {error}")\n            business_location = ""\n'''
new='''        business_location = filing_parser.extract_principal_office_location(full_text_soup)\n        if not business_location:\n            try:\n                business_location = edgar_client.get_business_location(cik)\n            except Exception as error:\n                print(f"[main] Warning: could not resolve issuer location for {company_name}: {error}")\n                business_location = ""\n'''
assert old in s
s=s.replace(old,new,1)
old='''            shares_after = holder.get("shares_after")\n            shares = shares_after if shares_after is not None else holder.get("shares")\n'''
new='''            shares_after = holder.get("shares_after")\n            if shares_after is None and shares_before is not None and shares_sold is not None:\n                derived_after = shares_before - shares_sold\n                if derived_after >= 0:\n                    shares_after = derived_after\n            shares = shares_after if shares_after is not None else holder.get("shares")\n'''
assert old in s
s=s.replace(old,new,1)
old='''                "Stanford Grade": stanford_result["grade"],\n                "Stanford Justification": stanford_result["justification"],\n                "Stanford University in Bio": stanford_university_in_bio,\n'''
new='''                "Stanford Grade": stanford_result["grade"],\n                "Stanford Justification": stanford_result["justification"],\n                "Stanford University in Bio": stanford_university_in_bio,\n                "Stanford Affiliation Confirmed": bool(stanford_university_in_bio or stanford_result.get("grade") in (1, "1", "Confirmed", "confirmed", True)),\n'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# prospect_research.py: expose normalized Stanford confirmation and equity-class placeholders
p=Path('src/prospect_research.py'); s=p.read_text(encoding='utf-8')
old='''        "stanford_source": first_present(row, "Stanford Justification", "Stanford Source"),\n    }\n'''
new='''        "stanford_source": first_present(row, "Stanford Justification", "Stanford Source"),\n        "stanford_affiliation_confirmed": bool(first_present(row, "Stanford Affiliation Confirmed", "Stanford University in Bio")),\n        "common_shares": first_present(row, "Common Shares"),\n        "restricted_shares": first_present(row, "Restricted Shares", "Unvested Shares"),\n        "options_shares": first_present(row, "Option Shares", "Options Exercisable"),\n    }\n'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# qc_review.py: add cross-field Prospect Research integrity checks
p=Path('src/qc_review.py'); s=p.read_text(encoding='utf-8')
marker='''\ndef check_ticker_resolved(row: dict) -> list:\n'''
insert='''\ndef check_prospect_integrity(row: dict) -> list:\n    """Cross-field checks for researcher-facing ownership/liquidity consistency."""\n    issues = []\n    price = _to_float(row.get("Actual Price"))\n    current = _to_float(row.get("Current Price"))\n    before = _to_int(row.get("Shares Before IPO"))\n    sold = _to_int(row.get("Shares Sold in IPO"))\n    after = _to_int(row.get("Shares After IPO"))\n    shares = _to_int(row.get("Shares"))\n    realized = _to_float(row.get("Cash Realized IPO"))\n    cash_value = _to_float(row.get("Cash Value"))\n    amount = _to_float(row.get("Amount Raised"))\n    offering_shares = _to_int(row.get("IPO Size (Shares)"))\n\n    if price is None and str(row.get("Date of Pricing") or "").strip():\n        issues.append("Priced filing is missing final IPO price")\n    if amount is None and price is not None and offering_shares is not None:\n        issues.append("Offering value missing despite known IPO shares and final price")\n    if before is not None and sold is not None:\n        expected_after = before - sold\n        if expected_after < 0:\n            issues.append("Shares sold exceed shares held before IPO")\n        elif after is None:\n            issues.append("Post-IPO shares missing despite known before/sold values")\n        elif after != expected_after:\n            issues.append(f"Post-IPO shares do not reconcile: {before:,} - {sold:,} != {after:,}")\n    if sold is not None and price is not None:\n        expected_realized = sold * price\n        if realized is None:\n            issues.append("IPO cash proceeds missing despite known shares sold and final price")\n        elif expected_realized and abs(expected_realized-realized)/expected_realized > 0.01:\n            issues.append("IPO cash proceeds do not match shares sold x final price")\n    if current is not None and (after is not None or shares is not None):\n        held = after if after is not None else shares\n        expected_value = held * current\n        if cash_value is None:\n            issues.append("Current holding value missing despite known shares and current price")\n        elif expected_value and abs(expected_value-cash_value)/expected_value > 0.01:\n            issues.append("Current holding value does not match post-IPO shares x current price")\n    if row.get("Stanford Affiliation Confirmed") and not row.get("Stanford Justification"):\n        issues.append("Stanford affiliation confirmed without supporting source/justification")\n    return issues\n\n\n'''
assert marker in s
s=s.replace(marker,insert+marker,1)
old='''    issues.extend(check_numeric_plausibility(row))\n    issues.extend(check_ticker_resolved(row))\n'''
new='''    issues.extend(check_numeric_plausibility(row))\n    issues.extend(check_prospect_integrity(row))\n    issues.extend(check_ticker_resolved(row))\n'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# dashboard_export.py: carry normalized Stanford confirmation to person records
p=Path('src/dashboard_export.py'); s=p.read_text(encoding='utf-8')
needle='''                "stanford_university_bio": _truthy(row.get("Stanford University in Bio")),\n'''
if needle in s and 'stanford_affiliation_confirmed' not in s:
    s=s.replace(needle,needle+'                "stanford_affiliation_confirmed": _truthy(row.get("Stanford Affiliation Confirmed")) or _truthy(row.get("Stanford University in Bio")),\n',1)
p.write_text(s,encoding='utf-8')

# UI uses normalized Stanford confirmation too
p=Path('docs/prospect-research/index.html'); s=p.read_text(encoding='utf-8')
s=s.replace('function isStanfordPerson(p){return p?.stanford_university_bio===true||stanfordOverrides.has(keyName(p?.name))}', 'function isStanfordPerson(p){return p?.stanford_affiliation_confirmed===true||p?.stanford_university_bio===true||stanfordOverrides.has(keyName(p?.name))}')
p.write_text(s,encoding='utf-8')

# tests
p=Path('src/test_filing_parser.py'); s=p.read_text(encoding='utf-8')
append='''\n\nclass ProspectQaParserTests(unittest.TestCase):\n    def test_cover_price_parses_price_to_public(self):\n        from bs4 import BeautifulSoup\n        soup=BeautifulSoup("<html><body>Price to public per share $17.50</body></html>", "html.parser")\n        self.assertEqual(filing_parser.extract_cover_page_data(soup)["offering_price"], 17.50)\n\n    def test_principal_office_location_prefers_cover_disclosure(self):\n        from bs4 import BeautifulSoup\n        soup=BeautifulSoup("<html><body>Our principal executive offices are located at 123 Main Street, Falls Church, VA 22042.</body></html>", "html.parser")\n        self.assertEqual(filing_parser.extract_principal_office_location(soup), "Falls Church, VA")\n'''
if 'class ProspectQaParserTests' not in s:
    s += append
p.write_text(s,encoding='utf-8')

p=Path('src/test_research_alerts.py')
# leave unrelated tests untouched

p=Path('src/test_main.py'); s=p.read_text(encoding='utf-8')
if 'test_process_filing_derives_after_shares' not in s:
    s += '''\n\n# QA arithmetic behavior is covered deterministically without live SEC calls.\nclass ProspectQaArithmeticTests(unittest.TestCase):\n    def test_qc_flags_cross_field_inconsistencies(self):\n        import qc_review\n        row={"Company Name":"X","Ticker":"X","Date of Pricing":"2026-01-01","Actual Price":10,"Current Price":12,"Holder Name":"Jane Doe","Shares Before IPO":1000,"Shares Sold in IPO":100,"Shares After IPO":800,"Shares":800,"Cash Realized IPO":900,"Cash Value":9000,"IPO Size (Shares)":10000,"Amount Raised":None}\n        issues=qc_review.check_prospect_integrity(row)\n        self.assertTrue(any("reconcile" in x for x in issues))\n        self.assertTrue(any("cash proceeds" in x for x in issues))\n        self.assertTrue(any("Offering value" in x for x in issues))\n'''
p.write_text(s,encoding='utf-8')
