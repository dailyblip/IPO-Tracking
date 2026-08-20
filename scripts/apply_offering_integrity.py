from pathlib import Path

# --- filing_parser.py: confidence-ranked offering terms + principal-office provenance ---
p = Path('src/filing_parser.py')
s = p.read_text(encoding='utf-8')
start = s.index('def extract_offering_size(soup: BeautifulSoup) -> int:')
end = s.index('\n\nOWNERSHIP_TABLE_HEADER_KEYWORDS', start)
replacement = r'''def _share_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def extract_offering_terms(soup: BeautifulSoup) -> dict:
    """Extract base IPO share count with source/confidence and primary/secondary split.

    A prospectus contains many share counts (shares outstanding, equity-plan reserves,
    beneficial ownership, greenshoes). Research-grade extraction must never choose a
    generic later share count merely because it matches ``N shares of common stock``.
    We rank only cover/title and explicit offering constructions, and exclude the
    underwriters' option from base IPO size.
    """
    text = soup.get_text(" ", strip=True)
    cover = text[:50000]

    primary = secondary = total = None
    sources = []
    confidence = "Unresolved"
    conflict = False

    # Most explicit construction: issuer block + selling-stockholder block.
    combined_patterns = [
        r"we\s+(?:are|will\s+be)\s+offering\s+([\d,]{4,})\s+shares[^.]{0,1600}?"
        r"selling\s+stockholders?[^.]{0,900}?(?:are\s+offering|are\s+selling|will\s+sell|offer)"
        r"(?:\s+an\s+additional)?\s+([\d,]{4,})\s+shares",
        r"we\s+(?:are|will\s+be)\s+offering\s+([\d,]{4,})\s+shares[^.]{0,1600}?"
        r"selling\s+shareholders?[^.]{0,900}?(?:are\s+offering|are\s+selling|will\s+sell|offer)"
        r"(?:\s+an\s+additional)?\s+([\d,]{4,})\s+shares",
    ]
    for pattern in combined_patterns:
        match = re.search(pattern, cover, re.I)
        if match:
            primary = _share_int(match.group(1))
            secondary = _share_int(match.group(2))
            if primary is not None and secondary is not None:
                total = primary + secondary
                sources.append("explicit issuer + selling-holder cover blocks")
                confidence = "High"
                break

    # Common THE OFFERING table construction. Use only explicit 'offered by' labels.
    if primary is None:
        m = re.search(
            r"(?:common\s+stock|shares?)\s+offered\s+by\s+(?:us|the\s+company)\s*[:|]?\s*([\d,]{4,})\s+shares",
            cover, re.I,
        )
        if m:
            primary = _share_int(m.group(1))
    if secondary is None:
        m = re.search(
            r"(?:common\s+stock|shares?)\s+offered\s+by\s+(?:the\s+)?selling\s+(?:stockholders|shareholders)\s*[:|]?\s*([\d,]{4,})\s+shares",
            cover, re.I,
        )
        if m:
            secondary = _share_int(m.group(1))
    if total is None and primary is not None and secondary is not None:
        total = primary + secondary
        sources.append("THE OFFERING primary + secondary rows")
        confidence = "High"

    # Explicit total statement/title. These are much safer than a generic share-count match.
    total_candidates = []
    explicit_patterns = [
        (r"initial\s+public\s+offering\s+of\s+([\d,]{4,})\s+shares", "explicit initial-public-offering total"),
        (r"(?:preliminary\s+)?prospectus\s+([\d,]{4,})\s+shares\s+(?:of\s+)?(?:class\s+[a-z]\s+)?common\s+stock", "prospectus cover title"),
        (r"\b([\d,]{4,})\s+shares\s+(?:of\s+)?(?:class\s+[a-z]\s+)?common\s+stock\s+this\s+is\b", "cover share title"),
    ]
    for pattern, label in explicit_patterns:
        for match in re.finditer(pattern, cover, re.I):
            value = _share_int(match.group(1))
            if value:
                total_candidates.append((match.start(), value, label))

    # Some EDGAR covers render title and narrative as separate blocks:
    # "17,000,000 Shares Common Stock This is ... initial public offering ..."
    for match in re.finditer(r"\b([\d,]{4,})\s+shares\s+(?:of\s+)?(?:class\s+[a-z]\s+)?common\s+stock\b", cover[:20000], re.I):
        nearby = cover[max(0, match.start()-250):min(len(cover), match.end()+650)].lower()
        if "initial public offering" in nearby and "outstanding" not in nearby:
            value = _share_int(match.group(1))
            if value:
                total_candidates.append((match.start(), value, "cover title adjacent to IPO statement"))

    if total_candidates:
        total_candidates.sort(key=lambda item: item[0])
        _, explicit_total, label = total_candidates[0]
        if total is None:
            total = explicit_total
            sources.append(label)
            confidence = "High"
        elif total != explicit_total:
            conflict = True
            sources.append(f"conflict with {label} ({explicit_total:,} shares)")
        else:
            sources.append(label)

    # Issuer-only offering. Safe only when the cover does not identify selling holders
    # participating in the base offering.
    if total is None:
        issuer_only = re.search(r"\bwe\s+(?:are|will\s+be)\s+offering\s+([\d,]{4,})\s+shares\b", cover[:25000], re.I)
        selling_language = re.search(r"selling\s+(?:stockholders|shareholders)[^.]{0,900}?(?:offering|selling|sell)\s+(?:an\s+additional\s+)?[\d,]{4,}\s+shares", cover[:30000], re.I)
        if issuer_only and not selling_language:
            primary = _share_int(issuer_only.group(1))
            total = primary
            sources.append("explicit issuer-only cover statement")
            confidence = "High"

    # Last-resort pattern is deliberately restricted to the first 15k and requires
    # nearby IPO language. It is flagged Medium so QC can surface it for review.
    if total is None:
        for match in re.finditer(r"\boffering\s+([\d,]{4,})\s+shares\b", cover[:15000], re.I):
            nearby = cover[max(0, match.start()-500):min(len(cover), match.end()+500)].lower()
            if "initial public offering" in nearby and "outstanding" not in nearby:
                total = _share_int(match.group(1))
                sources.append("context-limited offering-share fallback")
                confidence = "Medium"
                break

    return {
        "total_shares": total,
        "primary_shares": primary,
        "secondary_shares": secondary,
        "source": "; ".join(sources) if sources else None,
        "confidence": confidence,
        "conflict": conflict,
    }


def extract_offering_size(soup: BeautifulSoup) -> int:
    """Backward-compatible base-offering share count."""
    return extract_offering_terms(soup).get("total_shares")
'''
s = s[:start] + replacement + s[end:]

# parse_filing should expose authoritative terms and location once, not make callers re-parse.
old = '''    cover_page_data = extract_cover_page_data(soup)\n    cover_page_data["offering_size_shares"] = extract_offering_size(soup)\n\n    result = {\n'''
new = '''    cover_page_data = extract_cover_page_data(soup)\n    offering_terms = extract_offering_terms(soup)\n    cover_page_data["offering_size_shares"] = offering_terms.get("total_shares")\n    cover_page_data["primary_offering_shares"] = offering_terms.get("primary_shares")\n    cover_page_data["secondary_offering_shares"] = offering_terms.get("secondary_shares")\n    cover_page_data["offering_size_source"] = offering_terms.get("source")\n    cover_page_data["offering_size_confidence"] = offering_terms.get("confidence")\n    cover_page_data["offering_size_conflict"] = offering_terms.get("conflict", False)\n\n    result = {\n'''
assert old in s
s = s.replace(old, new, 1)
old = '''        "cover_page": cover_page_data,\n        "principal_stockholders":'''
new = '''        "cover_page": cover_page_data,\n        "principal_office_location": extract_principal_office_location(soup),\n        "principal_stockholders":'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# --- main.py: carry offering provenance and use S-1 address as authoritative fallback ---
p = Path('src/main.py')
s = p.read_text(encoding='utf-8')
s = s.replace('''        filing_price = None\n        date_of_filing = s1_meta.get("filing_date") if s1_meta else None\n''','''        filing_price = None\n        s1_location = None\n        date_of_filing = s1_meta.get("filing_date") if s1_meta else None\n''',1)
s = s.replace('''                s1_parsed = filing_parser.parse_filing(s1_document_url, is_range_filing=True)\n                price_range = s1_parsed.get("price_range", {})\n''','''                s1_parsed = filing_parser.parse_filing(s1_document_url, is_range_filing=True)\n                s1_location = s1_parsed.get("principal_office_location")\n                price_range = s1_parsed.get("price_range", {})\n''',1)
s = s.replace('''        offering_size = cover.get("offering_size_shares")\n        amount_raised = (\n''','''        offering_size = cover.get("offering_size_shares")\n        primary_offering_shares = cover.get("primary_offering_shares")\n        secondary_offering_shares = cover.get("secondary_offering_shares")\n        offering_size_source = cover.get("offering_size_source")\n        offering_size_confidence = cover.get("offering_size_confidence")\n        offering_size_conflict = bool(cover.get("offering_size_conflict"))\n        amount_raised = (\n''',1)
old = '''        business_location = filing_parser.extract_principal_office_location(full_text_soup)\n        if not business_location:\n            try:\n                business_location = edgar_client.get_business_location(cik)\n            except Exception as error:\n                print(f"[main] Warning: could not resolve issuer location for {company_name}: {error}")\n                business_location = ""\n'''
new = '''        business_location = parsed.get("principal_office_location") or s1_location\n        location_source = (\n            "424B4 principal executive office" if parsed.get("principal_office_location")\n            else ("S-1 principal executive office" if s1_location else None)\n        )\n        if not business_location:\n            try:\n                business_location = edgar_client.get_business_location(cik)\n                location_source = "SEC submissions metadata" if business_location else None\n            except Exception as error:\n                print(f"[main] Warning: could not resolve issuer location for {company_name}: {error}")\n                business_location = ""\n                location_source = None\n'''
assert old in s
s = s.replace(old, new, 1)
old = '''                "IPO Size (Shares)": offering_size,\n                "Amount Raised": amount_raised,\n                "Current Price": current_price,\n                "Location": business_location,\n'''
new = '''                "IPO Size (Shares)": offering_size,\n                "Primary Offering Shares": primary_offering_shares,\n                "Secondary Offering Shares": secondary_offering_shares,\n                "Offering Size Source": offering_size_source,\n                "Offering Size Confidence": offering_size_confidence,\n                "Offering Size Conflict": offering_size_conflict,\n                "Amount Raised": amount_raised,\n                "Current Price": current_price,\n                "Location": business_location,\n                "Location Source": location_source,\n'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# --- dashboard_export.py: preserve offering breakdown/provenance in JSON and CSV ---
p = Path('src/dashboard_export.py')
s = p.read_text(encoding='utf-8')
s = s.replace('''    "offering_price", "current_price", "price_updated", "location", "lockup_end_date",\n''','''    "offering_price", "current_price", "price_updated", "location", "location_source",\n    "primary_offering_shares", "secondary_offering_shares", "offering_size_source",\n    "offering_size_confidence", "lockup_end_date",\n''',1)
s = s.replace('''    "priority", "status", "offering_value", "filing_price", "offering_price",\n    "current_price", "price_updated", "location", "lockup_end_date", "holder_name", "shares",\n''','''    "priority", "status", "offering_value", "primary_offering_shares", "secondary_offering_shares",\n    "offering_size_source", "offering_size_confidence", "filing_price", "offering_price",\n    "current_price", "price_updated", "location", "location_source", "lockup_end_date", "holder_name", "shares",\n''',1)
old = '''            "value": amount or None,\n            "value_label": _money(amount),\n            "filing_price": first.get("Filing Price") or None,\n'''
new = '''            "value": amount or None,\n            "value_label": _money(amount),\n            "primary_offering_shares": _number(first.get("Primary Offering Shares")),\n            "secondary_offering_shares": _number(first.get("Secondary Offering Shares")),\n            "offering_size_source": first.get("Offering Size Source") or None,\n            "offering_size_confidence": first.get("Offering Size Confidence") or None,\n            "filing_price": first.get("Filing Price") or None,\n'''
assert old in s
s = s.replace(old, new, 1)
s = s.replace('''            "location": first.get("Location") or None,\n            "lockup_end_date": lockup.get("end"),\n''','''            "location": first.get("Location") or None,\n            "location_source": first.get("Location Source") or None,\n            "lockup_end_date": lockup.get("end"),\n''',1)
s = s.replace('''                "offering_value": filing.get("value"),\n                "filing_price": filing.get("price_range") or filing.get("filing_price"),\n''','''                "offering_value": filing.get("value"),\n                "primary_offering_shares": filing.get("primary_offering_shares"),\n                "secondary_offering_shares": filing.get("secondary_offering_shares"),\n                "offering_size_source": filing.get("offering_size_source"),\n                "offering_size_confidence": filing.get("offering_size_confidence"),\n                "filing_price": filing.get("price_range") or filing.get("filing_price"),\n''',1)
s = s.replace('''                "location": filing.get("location"),\n                "lockup_end_date": filing.get("lockup_end_date"),\n''','''                "location": filing.get("location"),\n                "location_source": filing.get("location_source"),\n                "lockup_end_date": filing.get("lockup_end_date"),\n''',1)
p.write_text(s, encoding='utf-8')

# --- qc_review.py: hard checks for offer-size conflicts and low-confidence fallback ---
p = Path('src/qc_review.py')
s = p.read_text(encoding='utf-8')
needle = '''    offering_shares = _to_int(row.get("IPO Size (Shares)"))\n\n    if price is None'''
replacement = '''    offering_shares = _to_int(row.get("IPO Size (Shares)"))\n    primary_offering = _to_int(row.get("Primary Offering Shares"))\n    secondary_offering = _to_int(row.get("Secondary Offering Shares"))\n    offering_confidence = str(row.get("Offering Size Confidence") or "")\n\n    if row.get("Offering Size Conflict"):\n        issues.append("Conflicting base-offering share counts found on prospectus cover")\n    if offering_confidence.lower() == "medium":\n        issues.append("IPO share count came from medium-confidence fallback and needs review")\n    if primary_offering is not None and secondary_offering is not None:\n        expected_total = primary_offering + secondary_offering\n        if offering_shares is None:\n            issues.append("Total IPO shares missing despite known primary and secondary blocks")\n        elif offering_shares != expected_total:\n            issues.append(f"IPO shares do not reconcile: {primary_offering:,} + {secondary_offering:,} != {offering_shares:,}")\n\n    if price is None'''
assert needle in s
s = s.replace(needle, replacement, 1)
# Batch secondary-share reconciliation against holder sale rows.
marker = '''    # Batch-level identity QA: two presentation variants of the same holder in\n'''
insert = '''    # Filing-level secondary-share QA: when the cover discloses a base secondary\n    # block and the beneficial-ownership table gives holder sale counts, they should\n    # reconcile. Do not silently publish a partial or duplicated selling grid.\n    secondary_totals = {}\n    secondary_expected = {}\n    for row in rows:\n        filing_key = (str(row.get("Ticker", "")).upper(), str(row.get("Date of Pricing") or row.get("Date of Filing") or ""))\n        expected = _to_int(row.get("Secondary Offering Shares"))\n        if expected is not None:\n            secondary_expected[filing_key] = expected\n        name = str(row.get("Holder Name") or "").lower()\n        sold = _to_int(row.get("Shares Sold in IPO"))\n        if sold is not None and "as a group" not in name:\n            secondary_totals[filing_key] = secondary_totals.get(filing_key, 0) + sold\n\n'''
assert marker in s
s = s.replace(marker, insert + marker, 1)
needle = '''        if holder_key and identity_counts.get((filing_key, holder_key), 0) > 1:\n            issue = f"Duplicate holder identity after normalization: {row.get('Holder Name', '')}"\n            notes = reviewed_row.get("QC Notes", "")\n            reviewed_row["QC Status"] = "Needs Review"\n            reviewed_row["QC Notes"] = "; ".join(x for x in (notes, issue) if x)\n        reviewed.append(reviewed_row)\n'''
replacement = '''        if holder_key and identity_counts.get((filing_key, holder_key), 0) > 1:\n            issue = f"Duplicate holder identity after normalization: {row.get('Holder Name', '')}"\n            notes = reviewed_row.get("QC Notes", "")\n            reviewed_row["QC Status"] = "Needs Review"\n            reviewed_row["QC Notes"] = "; ".join(x for x in (notes, issue) if x)\n        expected_secondary = secondary_expected.get(filing_key)\n        observed_secondary = secondary_totals.get(filing_key)\n        if expected_secondary is not None and observed_secondary is not None:\n            tolerance = max(10, int(expected_secondary * 0.001))\n            if abs(expected_secondary - observed_secondary) > tolerance:\n                issue = f"Selling-holder shares do not reconcile to cover: {observed_secondary:,} parsed vs {expected_secondary:,} offered"\n                notes = reviewed_row.get("QC Notes", "")\n                reviewed_row["QC Status"] = "Needs Review"\n                reviewed_row["QC Notes"] = "; ".join(x for x in (notes, issue) if x)\n        reviewed.append(reviewed_row)\n'''
assert needle in s
s = s.replace(needle, replacement, 1)
p.write_text(s, encoding='utf-8')

# --- tests: reproduce the real Lyntris failure and protect location fallback semantics ---
p = Path('src/test_filing_parser.py')
s = p.read_text(encoding='utf-8')
if 'test_lyntris_does_not_mistake_shares_outstanding_for_ipo_size' not in s:
    s += '''\n\nclass ResearchGradeOfferingTermsTests(unittest.TestCase):\n    def test_lyntris_does_not_mistake_shares_outstanding_for_ipo_size(self):\n        import filing_parser\n        html = """<html><body>\n        PROSPECTUS 17,000,000 Shares Common Stock\n        This is Lyntris Inc.'s initial public offering of our common stock.\n        We are offering 5,714,286 shares of common stock and the selling stockholders identified in this prospectus are offering an additional 11,285,714 shares of common stock.\n        Common stock to be outstanding immediately after this offering 115,949,384 shares of common stock.\n        The initial public offering price is $17.50 per share.\n        </body></html>"""\n        soup = _soup(html)\n        terms = filing_parser.extract_offering_terms(soup)\n        self.assertEqual(terms["total_shares"], 17_000_000)\n        self.assertEqual(terms["primary_shares"], 5_714_286)\n        self.assertEqual(terms["secondary_shares"], 11_285_714)\n        self.assertEqual(terms["confidence"], "High")\n        self.assertFalse(terms["conflict"])\n\n    def test_offering_table_primary_secondary_rows_are_summed(self):\n        import filing_parser\n        soup = _soup("""<html><body>This is our initial public offering. THE OFFERING\n        Common stock offered by us | 4,878,049 shares of common stock.\n        Common stock offered by the selling stockholders | 19,121,951 shares of common stock.\n        Common stock to be outstanding immediately after this offering | 115,113,147 shares.\n        </body></html>""")\n        terms = filing_parser.extract_offering_terms(soup)\n        self.assertEqual(terms["total_shares"], 24_000_000)\n        self.assertEqual(terms["primary_shares"], 4_878_049)\n        self.assertEqual(terms["secondary_shares"], 19_121_951)\n\n    def test_parse_filing_exposes_principal_office_location(self):\n        import filing_parser\n        soup = _soup("""<html><body>Brian Morrison Chief Executive Officer Lyntris Inc.\n        3130 Fairview Park Dr., Suite 230 Falls Church, VA 22042\n        (Address, including zip code, and telephone number, including area code, of registrant's principal executive offices)\n        </body></html>""")\n        self.assertEqual(filing_parser.extract_principal_office_location(soup), "Falls Church, VA")\n'''
p.write_text(s, encoding='utf-8')

# Test feed schema retention and group QC.
p = Path('src/test_main.py')
s = p.read_text(encoding='utf-8')
if 'test_secondary_offering_must_reconcile_to_selling_holder_rows' not in s:
    s += '''\n\nclass OfferingIntegrityQaTests(unittest.TestCase):\n    def test_secondary_offering_must_reconcile_to_selling_holder_rows(self):\n        import qc_review\n        from unittest.mock import patch\n        rows = [\n            {"Ticker":"LYNX","Date of Pricing":"2026-08-19","Company Name":"Lyntris Inc.","Actual Price":17.5,"Current Price":15.2,"Holder Name":"Seller A","Shares":100,"Secondary Offering Shares":300,"Shares Sold in IPO":100},\n            {"Ticker":"LYNX","Date of Pricing":"2026-08-19","Company Name":"Lyntris Inc.","Actual Price":17.5,"Current Price":15.2,"Holder Name":"Seller B","Shares":100,"Secondary Offering Shares":300,"Shares Sold in IPO":100},\n        ]\n        with patch.object(qc_review, "llm_consistency_check", return_value=[]):\n            reviewed = qc_review.review_rows(rows)\n        self.assertTrue(all(r["QC Status"] == "Needs Review" for r in reviewed))\n        self.assertTrue(all("Selling-holder shares do not reconcile" in r["QC Notes"] for r in reviewed))\n'''
p.write_text(s, encoding='utf-8')
