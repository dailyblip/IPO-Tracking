"""Narrow pre-offering option-only footnotes with a separate LLC distribution.

The distribution is reconciled against the post column, never added to the
pre-offering position. This parser does not establish exercise, vesting, cost,
economic ownership, or saleability. Unsupported wording fails closed.
"""
import re


def parse_pre_options(note, marker, name, date_literal, total, post_total):
    text = re.sub(r'\s+', ' ', note).strip()
    surname = name.split(',')[0].split()[-1]
    if not re.fullmatch(r'[A-Za-z-]+', surname):
        raise ValueError('Unsupported person alias')
    alias = 'Dr. ' + surname
    prefix = (f'({marker}) The number of shares beneficially owned prior to the offering consists of '
              f'{total:,} shares of common stock subject to options that are exercisable within 60 days of '
              f'{date_literal}, but excludes any shares distributed to {alias} in connection with the LLC Distribution. '
              f'In connection with the LLC Distribution, {alias} received ')
    if not text.startswith(prefix):
        raise ValueError('Complete dated option-only pre-offering footnote required')
    tail = re.fullmatch(
        r'([1-9]\d{0,2}(?:,\d{3})*) shares of common stock issuable upon conversion of our Series A redeemable convertible preferred stock'
        r'(?:, of which ([1-9]\d{0,2}(?:,\d{3})*) shares of Series A redeemable convertible preferred stock remain subject to a right of repurchase in our favor)?'
        r'\. The shares received upon the LLC Distribution are included in the number of shares beneficially owned after the offering\.',
        text[len(prefix):])
    if not tail:
        raise ValueError('Unsupported distribution or repurchase conditions')
    distributed = int(tail[1].replace(',', ''))
    repurchase = int(tail[2].replace(',', '')) if tail[2] else 0
    if repurchase > distributed or total + distributed != post_total:
        raise ValueError('Pre/post distribution reconciliation failed')
    if any(type(n) is not int or not 0 < n <= 9007199254740991 for n in (total, post_total)):
        raise ValueError('Invalid option total')
    return [dict(ordinal=1, instrument='option', quantity=total, attribution='unknown',
                 description=f'{total:,} common-share interests subject to options exercisable within 60 days of {date_literal}, as disclosed in the pre-offering column. Separate LLC-distribution interests are excluded. Actual exercise, vesting, personal economic ownership and present saleability are unconfirmed.')]
