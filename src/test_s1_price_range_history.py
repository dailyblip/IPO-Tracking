import unittest

import filing_price_history
import s1_price_range_history as history


def _row(
    *,
    accession="0001234567-26-000003",
    filed="2026-09-16",
    file_number="333-300001",
    form="S-1/A",
):
    return {
        "form_type": form,
        "accession_no": accession,
        "filing_date": filed,
        "file_number": file_number,
    }


def _filing():
    return {
        "id": "0001234567-26-000003",
        "company": "Example Biotech, Inc.",
        "ticker": "EXBI",
        "cik": "0001234567",
        "accession_no": "0001234567-26-000003",
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


class S1PriceRangeHistoryTests(unittest.TestCase):
    def test_nuvox_style_anticipated_between_range_is_supported_by_sec_parser(self):
        parsed = filing_price_history._extract_explicit_price_range_from_text(
            "We anticipate that the initial public offering price of our shares "
            "will be between $6.00 and $8.00."
        )
        self.assertEqual(parsed, {"range_low": 6.0, "range_high": 8.0})

    def test_recovers_range_from_current_exact_accession(self):
        filing = _filing()
        history_rows = [_row()]

        def registration_loader(cik, metadata):
            self.assertEqual(cik, "0001234567")
            self.assertEqual(metadata["accession_no"], filing["accession_no"])
            return (
                {"price_range": {"range_low": 6, "range_high": 8}},
                "https://www.sec.gov/current-index.htm",
            )

        payload, count = history.recover_payload_prepricing_ranges(
            {"filings": [filing]},
            history_loader=lambda cik, filed: history_rows,
            registration_loader=registration_loader,
        )

        repaired = payload["filings"][0]
        self.assertEqual(count, 1)
        self.assertEqual(repaired["price_range"], "$6.00–$8.00")
        self.assertEqual(repaired["filing_price"], "$6.00–$8.00")
        self.assertEqual(repaired["priority"], "High")
        self.assertEqual(
            repaired["filing_price_source"]["accession_no"],
            filing["accession_no"],
        )
        self.assertEqual(
            repaired["filing_price_source"]["file_number"], "333-300001"
        )
        self.assertNotIn(
            "No preliminary price range or fixed offering price detected yet",
            repaired["signals"],
        )

    def test_carries_range_from_prior_same_registration(self):
        filing = _filing()
        current = _row()
        prior = _row(
            accession="0001234567-26-000002",
            filed="2026-08-20",
        )

        def registration_loader(cik, metadata):
            if metadata["accession_no"] == current["accession_no"]:
                return (
                    {"price_range": {"range_low": None, "range_high": None}},
                    "https://www.sec.gov/current.htm",
                )
            return (
                {"price_range": {"range_low": 18, "range_high": 20}},
                "https://www.sec.gov/prior.htm",
            )

        payload, count = history.recover_payload_prepricing_ranges(
            {"filings": [filing]},
            history_loader=lambda cik, filed: [current, prior],
            registration_loader=registration_loader,
        )

        repaired = payload["filings"][0]
        self.assertEqual(count, 1)
        self.assertEqual(repaired["filing_price"], "$18.00–$20.00")
        self.assertEqual(
            repaired["filing_price_source"]["accession_no"],
            prior["accession_no"],
        )
        self.assertIn(
            "Filing Price carried from SEC registration history dated 2026-08-20",
            repaired["signals"],
        )

        queue = {
            "filings": [
                {
                    "id": "s1:0001234567",
                    "company": filing["company"],
                    "cik": filing["cik"],
                    "accession_no": filing["accession_no"],
                    "form": "S-1/A",
                    "stage": "Pre-pricing",
                    "filing_price": None,
                    "price_range": None,
                    "signals": [],
                }
            ]
        }
        synced, queue_count = history.synchronize_queue_ranges(queue, payload)
        self.assertEqual(queue_count, 1)
        self.assertEqual(
            synced["filings"][0]["filing_price"], "$18.00–$20.00"
        )
        self.assertEqual(
            synced["filings"][0]["filing_price_source"]["accession_no"],
            prior["accession_no"],
        )

    def test_ignores_concurrent_registration_with_different_file_number(self):
        filing = _filing()
        current = _row()
        other_registration = _row(
            accession="0001234567-26-000001",
            filed="2026-08-20",
            file_number="333-999999",
        )
        parsed_accessions = []

        def registration_loader(cik, metadata):
            parsed_accessions.append(metadata["accession_no"])
            if metadata["accession_no"] == current["accession_no"]:
                return (
                    {"price_range": {"range_low": None, "range_high": None}},
                    "https://www.sec.gov/current.htm",
                )
            return (
                {"price_range": {"range_low": 40, "range_high": 50}},
                "https://www.sec.gov/other.htm",
            )

        payload, count = history.recover_payload_prepricing_ranges(
            {"filings": [filing]},
            history_loader=lambda cik, filed: [current, other_registration],
            registration_loader=registration_loader,
        )

        self.assertEqual(count, 0)
        self.assertIsNone(payload["filings"][0]["filing_price"])
        self.assertEqual(parsed_accessions, [current["accession_no"]])

    def test_same_day_noncurrent_range_fails_closed_instead_of_guessing_order(self):
        filing = _filing()
        current = _row()
        same_day = _row(accession="0001234567-26-000002")

        def registration_loader(cik, metadata):
            if metadata["accession_no"] == current["accession_no"]:
                return (
                    {"price_range": {"range_low": None, "range_high": None}},
                    "https://www.sec.gov/current.htm",
                )
            return (
                {"price_range": {"range_low": 9, "range_high": 11}},
                "https://www.sec.gov/same-day.htm",
            )

        with self.assertRaisesRegex(
            history.S1PriceRangeHistoryError, "same-day SEC S-1/S-1A range"
        ):
            history.recover_payload_prepricing_ranges(
                {"filings": [filing]},
                history_loader=lambda cik, filed: [current, same_day],
                registration_loader=registration_loader,
            )

    def test_conflicting_ranges_on_same_prior_day_fail_closed(self):
        filing = _filing()
        current = _row()
        prior_a = _row(
            accession="0001234567-26-000001",
            filed="2026-08-20",
        )
        prior_b = _row(
            accession="0001234567-26-000002",
            filed="2026-08-20",
        )

        def registration_loader(cik, metadata):
            accession = metadata["accession_no"]
            if accession == current["accession_no"]:
                result = {"range_low": None, "range_high": None}
            elif accession == prior_a["accession_no"]:
                result = {"range_low": 10, "range_high": 12}
            else:
                result = {"range_low": 11, "range_high": 13}
            return {"price_range": result}, f"https://www.sec.gov/{accession}.htm"

        with self.assertRaisesRegex(
            history.S1PriceRangeHistoryError, "conflicting preliminary ranges"
        ):
            history.recover_payload_prepricing_ranges(
                {"filings": [filing]},
                history_loader=lambda cik, filed: [current, prior_a, prior_b],
                registration_loader=registration_loader,
            )

    def test_existing_preliminary_price_is_not_reinterpreted(self):
        filing = _filing()
        filing["price_range"] = "$18.00–$20.00"
        filing["filing_price"] = "$18.00–$20.00"

        def should_not_run(*args, **kwargs):
            raise AssertionError("history loader should not run")

        payload, count = history.recover_payload_prepricing_ranges(
            {"filings": [filing]},
            history_loader=should_not_run,
            registration_loader=should_not_run,
        )
        self.assertEqual(count, 0)
        self.assertEqual(
            payload["filings"][0]["filing_price"], "$18.00–$20.00"
        )

    def test_degenerate_point_price_is_left_for_fixed_price_gate(self):
        filing = _filing()
        current = _row()

        payload, count = history.recover_payload_prepricing_ranges(
            {"filings": [filing]},
            history_loader=lambda cik, filed: [current],
            registration_loader=lambda cik, metadata: (
                {"price_range": {"range_low": 7, "range_high": 7}},
                "https://www.sec.gov/current.htm",
            ),
        )

        self.assertEqual(count, 0)
        self.assertIsNone(payload["filings"][0]["filing_price"])


if __name__ == "__main__":
    unittest.main()
