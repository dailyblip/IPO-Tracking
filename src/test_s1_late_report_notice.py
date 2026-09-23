import unittest
from unittest.mock import patch

import s1_registration_history_gate


RULE_12B25_FORMS = (
    "NT 10-Q",
    "NT 10-Q/A",
    "NT 10-K",
    "NT 10-K/A",
    "NT 20-F",
    "NT 20-F/A",
)

CURRENT_ACCESSION = "0001234567-26-000100"


def _record():
    return {
        "form": "S-1",
        "stage": "Pre-pricing",
        "cik": "1234567",
        "accession_no": CURRENT_ACCESSION,
        "company": "Example Corp",
    }


def _current_row():
    return {
        "accession_no": CURRENT_ACCESSION,
        "form": "S-1",
        "file_number": "333-300000",
        "filing_date": "2026-06-01",
        "primary_document": "s1.htm",
        "acceptance_datetime": "20260601120000",
    }


def _reporting_row(
    form,
    *,
    filing_date="2026-05-20",
    acceptance_datetime="20260520120000",
):
    return {
        "accession_no": "0001234567-26-000090",
        "form": form,
        "file_number": "001-50000",
        "filing_date": filing_date,
        "primary_document": "nt.htm",
        "acceptance_datetime": acceptance_datetime,
    }


class Rule12b25RegistrationHistoryTests(unittest.TestCase):
    def test_all_supported_late_report_notices_prove_prior_reporting(self):
        for form in RULE_12B25_FORMS:
            with self.subTest(form=form):
                rows = [_current_row(), _reporting_row(form)]
                with patch.object(
                    s1_registration_history_gate,
                    "_recent_submission_rows",
                    return_value=rows,
                ):
                    self.assertTrue(
                        s1_registration_history_gate.already_reporting_before_registration(
                            _record()
                        )
                    )

    def test_notice_after_candidate_does_not_prove_prior_reporting(self):
        rows = [
            _current_row(),
            _reporting_row(
                "NT 10-Q",
                filing_date="2026-06-02",
                acceptance_datetime="20260602120000",
            ),
        ]
        with patch.object(
            s1_registration_history_gate,
            "_recent_submission_rows",
            return_value=rows,
        ):
            self.assertFalse(
                s1_registration_history_gate.already_reporting_before_registration(
                    _record()
                )
            )

    def test_same_day_acceptance_time_must_prove_notice_is_earlier(self):
        earlier_rows = [
            _current_row(),
            _reporting_row(
                "NT 10-K",
                filing_date="2026-06-01",
                acceptance_datetime="20260601110000",
            ),
        ]
        later_rows = [
            _current_row(),
            _reporting_row(
                "NT 10-K",
                filing_date="2026-06-01",
                acceptance_datetime="20260601130000",
            ),
        ]

        with patch.object(
            s1_registration_history_gate,
            "_recent_submission_rows",
            return_value=earlier_rows,
        ):
            self.assertTrue(
                s1_registration_history_gate.already_reporting_before_registration(
                    _record()
                )
            )

        with patch.object(
            s1_registration_history_gate,
            "_recent_submission_rows",
            return_value=later_rows,
        ):
            self.assertFalse(
                s1_registration_history_gate.already_reporting_before_registration(
                    _record()
                )
            )


if __name__ == "__main__":
    unittest.main()
