"""Strict footnote grammar for explicitly reviewed common shares / RSUs / options.

Not a general financial-language model. Unsupported clauses fail closed. Every
component is part of one reported total, never an additional aggregate position.
"""
import re


def parse_components(note, marker, name, date_literal, total):
    text = re.sub(r'\s+', ' ', note).strip()
    prefix = f'({marker}) Consists of '
    if not text.startswith(prefix):
        raise ValueError('Complete enumerated footnote required')
    body = text[len(prefix):]
    matches = list(re.finditer(r'\((i|ii|iii|iv)\) ', body))
    if not 2 <= len(matches) <= 4 or matches[0].start() != 0:
        raise ValueError('Unsupported footnote enumeration')
    surname = name.split()[-1]
    aliases = (name, 'Mr. '+surname)
    results = []
    for i, match in enumerate(matches):
        if match.group(1) != ('i','ii','iii','iv')[i]:
            raise ValueError('Duplicate or out-of-order clause')
        clause = body[match.end():matches[i+1].start() if i+1<len(matches) else len(body)]
        clause = re.sub(r'(?:,? and |, )$', '', clause) if i+1<len(matches) else clause.removesuffix('.')
        q = re.fullmatch(r'([1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*) shares of common stock(.*?) directly held by (.+)', clause)
        if not q:
            raise ValueError('Unsupported instrument or clause wording')
        amount, suffix, holder = q.groups()
        instrument = {'':'common_share',' underlying RSUs':'rsu',' underlying stock options':'option'}.get(suffix)
        if instrument is None:
            raise ValueError('Unsupported instrument')
        condition = ''
        if instrument == 'rsu':
            condition = ' that vest and settle within 60 days of '+date_literal
        elif instrument == 'option':
            condition = ' that are currently exercisable or would be exercisable within 60 days of '+date_literal
        if condition:
            if not holder.endswith(condition):
                raise ValueError('Award condition or as-of date mismatch')
            holder = holder[:-len(condition)]
        if holder in aliases:
            attribution = 'direct'
        elif holder in ('a family trust of which '+name+' serves as trustee',
                        'family trusts of which Mr. '+surname+' or his spouse serves as trustee'):
            attribution = 'trust_or_family'
        elif holder == 'the family trust' and any(c['attribution']=='trust_or_family' for c in results):
            attribution = 'trust_or_family'
        else:
            raise ValueError('Unresolved holder attribution')
        quantity = int(amount.replace(',',''))
        if not 0 < quantity <= 9007199254740991:
            raise ValueError('Invalid component quantity')
        results.append(dict(ordinal=i+1,instrument=instrument,quantity=quantity,attribution=attribution,description=clause))
    if sum(c['quantity'] for c in results) != total:
        raise ValueError('Components do not reconcile to the single table total')
    if not any(c['instrument']!='common_share' for c in results):
        raise ValueError('This profile requires a mixed-award disclosure')
    return results
