"""Strict dated voting-common / option footnotes from a final prospectus.

This is intentionally not a general financial-language parser. It accepts the
two exact reviewed shapes below and fails closed for trusts, funds, conversion
interests, awards, extra clauses, or a total that does not reconcile. Returned
components are parts of one beneficial-ownership total, never additive rows.
"""
import re

from review_components import require_reconciled_total


def _quantity(value):
    if not re.fullmatch(r'[1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*', value):
        raise ValueError('Invalid component quantity')
    amount = int(value.replace(',', ''))
    if amount > 9007199254740991:
        raise ValueError('Invalid component quantity')
    return amount


def parse_voting_options(note, marker, date_literal, total):
    text = re.sub(r'\s+', ' ', note).strip()
    prefix = f'({marker}) Consists of '
    if not text.startswith(prefix):
        raise ValueError('Complete dated voting-common footnote required')
    body = text[len(prefix):]
    common_and_option = re.fullmatch(
        r'\(i\) ([1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*) shares of common stock and '
        r'\(ii\) ([1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*) shares of common stock underlying '
        r'outstanding stock options exercisable within 60 days of '
        + re.escape(date_literal) + r'\.', body)
    option_only = re.fullmatch(
        r'([1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*) shares of common stock underlying '
        r'outstanding stock options exercisable within 60 days of '
        + re.escape(date_literal) + r'\.', body)
    if common_and_option:
        common, option = map(_quantity, common_and_option.groups())
        components = [
            dict(ordinal=1, instrument='common_share', quantity=common,
                 attribution='unknown',
                 description=(f'{common:,} voting-common shares. Part of the disclosed total; '
                              'current ownership, personal economic interest and saleability are unconfirmed.')),
            dict(ordinal=2, instrument='option', quantity=option,
                 attribution='unknown',
                 description=(f'{option:,} voting-common share interests underlying outstanding options '
                              f'exercisable within 60 days of {date_literal}. Part of the disclosed total; '
                              'current ownership, personal economic interest and saleability are unconfirmed.')),
        ]
    elif option_only:
        option = _quantity(option_only.group(1))
        components = [
            dict(ordinal=1, instrument='option', quantity=option,
                 attribution='unknown',
                 description=(f'{option:,} voting-common share interests underlying outstanding options '
                              f'exercisable within 60 days of {date_literal}. Part of the disclosed total; '
                              'current ownership, personal economic interest and saleability are unconfirmed.')),
        ]
    else:
        raise ValueError('Unsupported voting-common or option footnote wording')
    require_reconciled_total(total, components)
    return components
