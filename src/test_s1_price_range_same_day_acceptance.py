import unittest

import s1_price_range_history as history


CURRENT_ACCESSION = "0001234567-26-000003"
CANDIDATE_ACCESSION = "0001234567-26-000002"


def _row(accession, acceptance):
    return {
        "form_type": "S-1/A",
        "accession_no": accession,
        "filing_date": "2026-09-16",
        "file_number": "333-300001",
        "acceptance_datetime": acceptance,
    }


def _filing():
    return {
        "id": CURRENT_ACCESSION,
        "company": "Example Biotech, Inc.",
        "ticker": "EXBI",
        "cik": "0001234567",
        "accession_no": CURRENT_ACCESSION,
        "form": "S-1/A",
        "filed": "2026-09-16",
        "stage": "Pre-pricing",
        "priority": "Medium",
        "price_range": None,
        "filing_price": None,
        "signals": [
            "Registration statement amended — IPO remains pre-pricing",
            "No preliminary price range or fixed offering price detected yet",
        ],
    }


def _sec_index(accession):
    digits = accession.replace("-", "")
    return (
        "https://www.sec.gov/Archives/edgar/data/1234567/"
        f"{digits}/{accession}-index.htm"
    )


def _registration_loader(cik, metadata):
    if metadata["accession_no"] == CURRENT_ACCESSION:
        return (
            {"price_range": {"range_low": None, "range_high": None}},
            _sec_index(CURRENT_ACCESSION),
        )
    return (
        {"price_range": {"range_low": 9, "range_high": 11}},
        _sec_index(CANDIDATE_ACCESSION),
    )


class SameDayAcceptancePriceRangeTests(unittest.TestCase):
    def _recover(self, current_acceptance, candidate_acceptance):
        current = _row(CURRENT_ACCESSION, current_acceptance)
        candidate = _row(CANDIDATE_ACCESSION, candidate_acceptance)
        return history.recover_payload_prepricing_ranges(
            {"filings": [_filing()]},
            history_loader=lambda cik, filed: [current, candidate],
            registration_loader=_registration_loader,
        )

    def test_compact_edgar_earlier_same_day_range_is_carried_forward(self):
        payload, count = self._recover("20260916153000", "20260916120000")
        repaired = payload["filings"][0]
        self.assertEqual(count, 1)
        self.assertEqual(repaired["filing_price"], "$9.00–$11.00")
        self.assertEqual(
            repaired["filing_price_source"]["accession_no"],
            CANDIDATE_ACCESSION,
        )

    def test_later_same_day_range_is_not_carried_backward(self):
        payload, count = self._recover("20260916120000", "20260916153000")
        self.assertEqual(count, 0)
        self.assertIsNone(payload["filings"][0]["filing_price"])

    def test_equal_same_day_acceptance_fails_closed(self):
        with self.assertRaisesRegex(
            history.S1PriceRangeHistoryError,
            "same-day SEC S-1/S-1/A range",
        ):
            self._recover("20260916120000", "20260916120000")

    def test_timezone_ambiguous_same_day_acceptance_fails_closed(self):
        with self.assertRaisesRegex(
            history.S1PriceRangeHistoryError,
            "same-day SEC S-1/S-1/A range",
        ):
            self._recover("2026-09-16T15:30:00", "20260916120000")


if __name__ == "__main__":
    unittest.main()
