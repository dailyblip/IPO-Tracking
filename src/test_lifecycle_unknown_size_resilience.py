import unittest

from lifecycle_reconciler import reconcile_payload


def _final_record(**overrides):
    record = {
        "id": "0001193125-26-356916",
        "company": "Example IPO, Inc.",
        "ticker": "EXAM",
        "cik": "0002132582",
        "accession_no": "0001193125-26-356916",
        "form": "424B4",
        "filed": "2026-08-19",
        "filing_date": "2026-07-01",
        "stage": "Priced",
        "pricing_date": "2026-08-18",
        "offering_price": 17.5,
        "value": None,
        "value_label": None,
        "offering_size_source": None,
        "offering_size_confidence": "Unresolved",
        "people": [],
        "people_count": 0,
        "signals": ["Offering priced at $17.50 per share"],
    }
    record.update(overrides)
    return record


def _final_meta(**overrides):
    meta = {
        "company_name": "Example IPO, Inc.",
        "ticker": "EXAM",
        "cik": "0002132582",
        "accession_no": "0001193125-26-356916",
        "form_type": "424B4",
        "filing_date": "2026-08-19",
    }
    meta.update(overrides)
    return meta


class UnknownSizeFinalLifecycleTests(unittest.TestCase):
    def test_release_grade_unknown_size_survives_transient_sec_refetch_failure(self):
        final = _final_record()

        def unavailable(_):
            raise RuntimeError("temporary SEC failure")

        payload, repaired, removed = reconcile_payload(
            {"filings": [final]},
            [_final_meta()],
            unavailable,
        )

        self.assertEqual(repaired, 0)
        self.assertEqual(removed, 0)
        self.assertEqual(payload["filings"], [final])

    def test_ticker_conflict_remains_release_blocking_when_refetch_fails(self):
        final = _final_record(ticker="OLD")

        def unavailable(_):
            raise RuntimeError("temporary SEC failure")

        payload, repaired, removed = reconcile_payload(
            {"filings": [final]},
            [_final_meta(ticker="EXAM")],
            unavailable,
        )

        self.assertEqual(repaired, 0)
        self.assertEqual(removed, 1)
        self.assertEqual(payload["filings"], [])


if __name__ == "__main__":
    unittest.main()
