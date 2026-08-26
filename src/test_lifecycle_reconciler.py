import unittest

from bs4 import BeautifulSoup

from lifecycle_reconciler import (
    _promote_prepricing_record,
    extract_final_offering_terms,
    reconcile_payload,
)


def _soup(body: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><body>{body}</body></html>", "html.parser")


def _stale_record(**overrides):
    record = {
        "id": "s1:0002132582",
        "company": "Lyntris Inc.",
        "ticker": "LYNX",
        "cik": "0002132582",
        "accession_no": "0001193125-26-346328",
        "form": "S-1/A",
        "filed": "2026-08-12",
        "filing_date": "2026-07-01",
        "stage": "Pre-pricing",
        "value": 492_000_000,
        "value_label": "$492M",
        "offering_size_source": "preliminary primary offering",
        "offering_size_confidence": "High",
        "people": [{"name": "Preliminary Holder", "shares": 1_000_000}],
        "people_count": 1,
        "signals": ["Registration statement amended — IPO remains pre-pricing"],
    }
    record.update(overrides)
    return record


def _final_meta(**overrides):
    meta = {
        "company_name": "Lyntris Inc.",
        "ticker": "LYNX",
        "cik": "0002132582",
        "accession_no": "0001193125-26-356916",
        "form_type": "424B4",
        "filing_date": "2026-08-19",
    }
    meta.update(overrides)
    return meta


def _lyntris_final_soup(prefix=""):
    return _soup(
        prefix
        + " symbol: LYNX. The initial public offering price is $17.50 per share. "
        + "THE OFFERING Common stock offered by us 5,714,286 shares. "
        + "Common stock offered by the selling stockholders 11,285,714 shares. "
        + "Common stock to be outstanding immediately after this offering 115,949,384 shares."
    )


class LifecycleReconcilerTests(unittest.TestCase):
    def test_reads_explicit_final_terms_beyond_cover_window(self):
        soup = _lyntris_final_soup("x" * 60_000)
        terms = extract_final_offering_terms(soup)

        self.assertEqual(terms["primary_shares"], 5_714_286)
        self.assertEqual(terms["secondary_shares"], 11_285_714)
        self.assertEqual(terms["total_shares"], 17_000_000)
        self.assertEqual(terms["confidence"], "High")

    def test_promotes_stale_prepricing_record_from_final_424b4(self):
        promoted = _promote_prepricing_record(
            _stale_record(),
            _final_meta(),
            _lyntris_final_soup(),
        )

        self.assertIsNotNone(promoted)
        self.assertEqual(promoted["id"], "0001193125-26-356916")
        self.assertEqual(promoted["form"], "424B4")
        self.assertEqual(promoted["stage"], "Priced")
        self.assertEqual(promoted["pricing_date"], "2026-08-19")
        self.assertEqual(promoted["offering_price"], 17.5)
        self.assertEqual(promoted["primary_offering_shares"], 5_714_286)
        self.assertEqual(promoted["secondary_offering_shares"], 11_285_714)
        self.assertEqual(promoted["value"], 297_500_000.0)
        self.assertEqual(promoted["offering_size_confidence"], "High")
        self.assertEqual(promoted["people"], [])
        self.assertEqual(promoted["people_count"], 0)
        self.assertIn("0001193125-26-356916", promoted["sec_url"])

    def test_existing_priced_record_replaces_same_cik_prepricing_record(self):
        final = {
            "id": "0001193125-26-356916",
            "company": "Lyntris Inc.",
            "ticker": "LYNX",
            "cik": "0002132582",
            "form": "424B4",
            "stage": "Priced",
            "pricing_date": "2026-08-19",
            "offering_price": 17.5,
        }
        payload, promoted, removed = reconcile_payload(
            {"filings": [_stale_record(), final]},
            [_final_meta()],
            lambda _: self.fail("final filing should not be refetched when priced record exists"),
        )

        self.assertEqual(promoted, 0)
        self.assertEqual(removed, 1)
        self.assertEqual(payload["filings"], [final])

    def test_final_424b4_with_unresolved_exact_size_drops_stale_prepricing(self):
        unresolved = _soup(
            "symbol: LYNX. The initial public offering price is $17.50 per share. "
            "Final prospectus without an exact base-offering share disclosure in this fixture."
        )
        payload, promoted, removed = reconcile_payload(
            {"filings": [_stale_record()]},
            [_final_meta()],
            lambda _: unresolved,
        )

        self.assertEqual(promoted, 0)
        self.assertEqual(removed, 1)
        self.assertEqual(payload["filings"], [])

    def test_sub_100m_final_offering_does_not_survive_100m_gate(self):
        small = _soup(
            "symbol: SMALL. The initial public offering price is $10.00 per share. "
            "THE OFFERING Common stock offered by us 5,000,000 shares."
        )
        record = _stale_record(ticker="SMALL")
        meta = _final_meta(ticker="SMALL")

        self.assertIsNone(_promote_prepricing_record(record, meta, small))

    def test_ticker_mismatch_drops_stale_market_quote(self):
        record = _stale_record(
            ticker="OLD",
            current_price=22.0,
            price_updated="2026-08-19T15:00:00+00:00",
        )
        promoted = _promote_prepricing_record(record, _final_meta(), _lyntris_final_soup())

        self.assertIsNotNone(promoted)
        self.assertEqual(promoted["ticker"], "LYNX")
        self.assertNotIn("current_price", promoted)
        self.assertNotIn("price_updated", promoted)


if __name__ == "__main__":
    unittest.main()
