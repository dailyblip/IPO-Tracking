import unittest

from lifecycle_reconciler import _select_final_meta


class LifecycleFollowonCandidateGuardTests(unittest.TestCase):
    def test_existing_final_does_not_fall_forward_to_different_424b4_accession(self):
        existing_final = {
            "cik": "0001234567",
            "accession_no": "0001234567-26-000100",
            "form": "424B4",
            "stage": "Priced",
            "filed": "2026-06-11",
            "pricing_date": "2026-06-10",
            "offering_price": 10.0,
            "ticker": "ACME",
        }
        later_followon = {
            "cik": "0001234567",
            "accession_no": "0001234567-26-000900",
            "form_type": "424B4",
            "filing_date": "2026-09-01",
            "ticker": "ACME",
        }

        selected = _select_final_meta(
            [later_followon], existing_final=existing_final
        )

        self.assertIsNone(
            selected,
            "A later 424B4 for the same CIK may be a follow-on/re-offering and must not replace an existing IPO final when its accession is absent from the scan window.",
        )

    def test_existing_final_still_selects_its_exact_424b4_accession(self):
        existing_final = {
            "cik": "0001234567",
            "accession_no": "0001234567-26-000100",
            "form": "424B4",
            "stage": "Priced",
        }
        ipo_final = {
            "cik": "0001234567",
            "accession_no": "0001234567-26-000100",
            "form_type": "424B4",
            "filing_date": "2026-06-11",
        }
        later_followon = {
            "cik": "0001234567",
            "accession_no": "0001234567-26-000900",
            "form_type": "424B4",
            "filing_date": "2026-09-01",
        }

        selected = _select_final_meta(
            [later_followon, ipo_final], existing_final=existing_final
        )

        self.assertIs(selected, ipo_final)

    def test_prepricing_record_can_still_select_first_later_final(self):
        prepricing = {
            "cik": "0001234567",
            "form": "S-1/A",
            "filed": "2026-06-01",
        }
        first_final = {
            "cik": "0001234567",
            "accession_no": "0001234567-26-000100",
            "form_type": "424B4",
            "filing_date": "2026-06-11",
        }
        later_final = {
            "cik": "0001234567",
            "accession_no": "0001234567-26-000900",
            "form_type": "424B4",
            "filing_date": "2026-09-01",
        }

        selected = _select_final_meta(
            [later_final, first_final], prepricing=prepricing
        )

        self.assertIs(selected, first_final)


if __name__ == "__main__":
    unittest.main()
