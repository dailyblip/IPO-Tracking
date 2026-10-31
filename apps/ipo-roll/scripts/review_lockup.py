"""Explicit calendar-day arithmetic, not an opinion that securities can be sold."""
import re
from datetime import date, timedelta


def calendar_boundary(trigger, days):
    if type(days) is not int or not 1 <= days <= 730:
        raise ValueError('Unsupported calendar-day duration')
    start = date.fromisoformat(trigger)
    if not 2000 <= start.year <= 2100:
        raise ValueError('Unsupported trigger date')
    return (start + timedelta(days=days)).isoformat()


def review_terms(cover, definition, scope, exceptions, trigger, days):
    """Narrow reviewed final-prospectus grammar; other contracts need review."""
    boundary = calendar_boundary(trigger, days)
    start = date.fromisoformat(trigger)
    literal = start.strftime('%B') + f' {start.day}, {start.year}'
    lines = [s.strip() for s in cover.splitlines()]
    dates = [s for s in lines if re.fullmatch(r'[A-Z][a-z]+ \d{1,2}, \d{4}', s)]
    if dates != [literal] or 'Prospectus' not in lines:
        raise ValueError('Unambiguous dated prospectus cover required')
    flat = lambda s: re.sub(r'\s+', ' ', s).strip()
    definition, scope, exceptions = map(flat, (definition, scope, exceptions))
    duration = f'for a period of {days} days after the date of this prospectus (such period, the “restricted period”)'
    if duration not in definition or 'prior written consent' not in definition:
        raise ValueError('Explicit calendar-day restricted-period definition required')
    required = ('Our directors and executive officers', 'have entered into lock-up agreements',
                'with limited exceptions, for the restricted period', 'prior written consent',
                'securities convertible into or exercisable or exchangeable for our Class A common stock')
    if not all(s in scope for s in required):
        raise ValueError('Executed executive/director scope required')
    if not all(s in exceptions for s in ('subject in certain cases to various conditions',
                                        'would be subject to restrictions similar',
                                        'in their sole discretion, may release',
                                        'in whole or in part at any time')):
        raise ValueError('Complete exception and discretionary-release context required')
    # Do not reduce a graduated, conditional or business-day schedule to one date.
    if re.search(r'business days|trading days|trading price|price exceeds|early release|various intervals|automatically extend', definition+' '+scope, re.I):
        raise ValueError('Unsupported conditional restriction schedule')
    return dict(trigger_date=trigger, day_count=days, boundary_date=boundary,
                method='calendar-days-after/1',
                conditions='Scheduled date-only boundary assuming the disclosed term applies unchanged. Consent, exceptions and discretionary release may alter restrictions. Exact intraday expiry is not established. No present ownership, release, registration/resale eligibility, saleability or cash proceeds are confirmed.')
