import unittest

from bs4 import BeautifulSoup

from lifecycle_reconciler import extract_final_offering_terms, reconcile_payload


def _soup(text):
    return BeautifulSoup(f"<html><body>{text}</body></html>", "html.parser")


def _jersey_final_soup():
    return _soup("""
    43,478,261 Shares Jersey Mike's Subs Inc. Class A Common Stock.
    This is the initial public offering of shares of Class A common stock of Jersey Mike's Subs Inc.
    We are selling 13,782,609 shares of our Class A common stock and the selling stockholders
    identified in this prospectus are offering 29,695,652 shares of Class A common stock.
    The initial public offering price is $23.00 per share. symbol: JMW.
    The underwriters have an option to purchase up to an additional 6,521,739 shares.
    """)


def _final_meta():
    return {
        "company_name": "Jersey Mike's Subs Inc.",
        "ticker": "JMW",
        "cik": "0002132582",
        "accession_no": "0001193125-26-356916",
        "form_type": "424B4",
        "filing_date": "2026-08-19",
    }


def _final_record(**overrides):
    record = {
        "id": "0001193125-26-356916",
        "company": "Jersey Mike's Subs Inc.",
        "ticker": "JMW",
        "cik": "0002132582",
        "accession_no": "0001193125-26-356916",
        "form": "424B4",
        "filed": "2026-08-19",
        "filing_date": "2026-07-01",
        "stage": "Priced",
        "pricing_date": "2026-08-19",
        "offering_price": 23.0,
        "value": 1_000_000_003,
        "value_label": "$1.0B",
        "primary_offering_shares": 13_782_609,
        "secondary_offering_shares": None,
        "offering_size_source": "authoritative final offering terms",
        "offering_size_confidence": "High",
        "sec_url": (
            "https://www.sec.gov/Archives/edgar/data/2132582/000119312526356916/"
            "0001193125-26-356916-index.htm"
        ),
        "people": [],
        "people_count": 0,
        "signals": ["Offering priced at $23.00 per share"],
    }
    record.update(overrides)
    return record


class LifecycleSecondaryShareRecoveryTests(unittest.TestCase):
    def test_final_terms_accept_selling_verb_and_secondary_leg(self):
        terms = extract_final_offering_terms(_jersey_final_soup())

        self.assertEqual(terms["primary_shares"], 13_782_609)
        self.assertEqual(terms["secondary_shares"], 29_695_652)
        self.assertEqual(terms["total_shares"], 43_478_261)
        self.assertEqual(terms["confidence"], "High")

    def test_release_grade_aggregate_refetches_when_published_split_is_incomplete(self):
        loads = []

        def loader(meta):
            loads.append(meta["accession_no"])
            return _jersey_final_soup()

        payload, repaired, removed = reconcile_payload(
            {"filings": [_final_record()]},
            [_final_meta()],
            loader,
        )

        self.assertEqual(loads, ["0001193125-26-356916"])
        self.assertEqual(repaired, 1)
        self.assertEqual(removed, 0)
        result = payload["filings"][0]
        self.assertEqual(result["primary_offering_shares"], 13_782_609)
        self.assertEqual(result["secondary_offering_shares"], 29_695_652)
        self.assertEqual(result["value"], 1_000_000_003.0)
        self.assertEqual(result["offering_size_confidence"], "High")

    def test_issuer_only_release_grade_size_keeps_no_refetch_fast_path(self):
        primary = 13_782_609
        final = _final_record(
            value=primary * 23,
            value_label="$317M",
            primary_offering_shares=primary,
            secondary_offering_shares=None,
        )
        payload, repaired, removed = reconcile_payload(
            {"filings": [final]},
            [_final_meta()],
            lambda _: self.fail("supported issuer-only final size should not be refetched"),
        )

        self.assertEqual(repaired, 0)
        self.assertEqual(removed, 0)
        self.assertEqual(payload["filings"], [final])


if __name__ == "__main__":
    unittest.main()
