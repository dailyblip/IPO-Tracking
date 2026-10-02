"""Unapproved biography discovery; never substitutes for a full table/footnote review."""
import re


def discover(blocks):
    """Find unreviewed biography starts without requiring a preexisting owner list.

    These are leads, not a complete roster. Review continuation paragraphs/page
    breaks against the original and reconcile both management and owner tables.
    """
    found = []
    pattern = re.compile(r'^(.{3,100}?)\s+(?:has served|has been|serves|served|is currently|is expected to|will serve|was appointed|is our|is the|joined)\b')
    for block in blocks:
        text = block['text']
        match = pattern.match(text)
        if not match or len(text) < 35:
            continue
        if not re.search(r'\b(?:our|board|chief|president|officer|director|chair|partner|founder)\b', text[match.end():], re.I):
            continue
        name = match[1]
        if not 2 <= len(name.split()) <= 10 or not name[0].isupper():
            continue
        if any(not token.strip('\"“”(),')[0:1].isupper() and token.casefold() not in ('de','del','da','dos','van','von','la') for token in name.split()):
            continue
        if re.search(r'^(?:We|Our|The|Each|This|Mr\.|Ms\.|Mrs\.|Dr\.)\b', name):
            continue
        found.append(dict(name=name, first_block=block['index'],
                          review_status='unreviewed', biography_complete=False))
    return found

