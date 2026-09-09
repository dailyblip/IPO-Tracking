import unittest

from lifecycle_reconciler import _select_final_meta


class LifecycleStaleFinalBeforeRegistrationTests(unittest.TestCase):
    def test_stale_existing_final_before_current_registration_is_not_selected(self):
        stale_final = {
            "accession_no": "0002100000-26-000100",
            "filing_date": "2026-06-10",
            "cik": "0002100000",
        }
        current_final = {
            "accession_no": "0002100000-26-000200",
            "filing_date": "2026-09-08",
            "cik": "0002100000",
        }
        existing_final = {
            "accession_no": stale_final["accession_no"],
            "form": "424B4",
            "stage": "Priced",
        }
        current_registration = {
            "form": "S-1/A",
            "stage": "Pre-pricing",
            "filed": "2026-09-01",
        }

        selected = _select_final_meta(
            [stale_final, current_final],
            existing_final=existing_final,
            prepricing=current_registration,
        )

        self.assertEqual(selected["accession_no"], current_final["accession_no"])

    def test_stale_existing_final_does_not_override_unpriced_current_registration(self):
        stale_final = {
            "accession_no": "0002100000-26-000100",
            "filing_date": "2026-06-10",
            "cik": "0002100000",
        }
        existing_final = {
            "accession_no": stale_final["accession_no"],
            "form": "424B4",
            "stage": "Priced",
        }
        current_registration = {
            "form": "S-1",
            "stage": "Pre-pricing",
            "filing_date": "2026-09-01",
        }

        selected = _select_final_meta(
            [stale_final],
            existing_final=existing_final,
            prepricing=current_registration,
        )

        self.assertIsNone(selected)


if __name__ == "__main__":
    unittest.main()
