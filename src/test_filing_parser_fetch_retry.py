import os
import unittest
from unittest.mock import Mock, patch

import requests

import filing_parser


class FilingParserFetchRetryTests(unittest.TestCase):
    def setUp(self):
        self.previous_user_agent = os.environ.get("SEC_EDGAR_USER_AGENT")
        os.environ["SEC_EDGAR_USER_AGENT"] = "research-monitor-tests contact@example.com"

    def tearDown(self):
        if self.previous_user_agent is None:
            os.environ.pop("SEC_EDGAR_USER_AGENT", None)
        else:
            os.environ["SEC_EDGAR_USER_AGENT"] = self.previous_user_agent

    @staticmethod
    def _response(status_code, text="<html><body>ok</body></html>"):
        response = Mock()
        response.status_code = status_code
        response.text = text
        if status_code >= 400:
            error = requests.HTTPError(f"{status_code} response")
            error.response = response
            response.raise_for_status.side_effect = error
        else:
            response.raise_for_status.return_value = None
        return response

    @patch("filing_parser.time.sleep")
    @patch("filing_parser.requests.get")
    def test_transient_503_is_retried_then_succeeds(self, get_mock, sleep_mock):
        get_mock.side_effect = [self._response(503), self._response(200)]

        soup = filing_parser.fetch_document("https://www.sec.gov/example.htm")

        self.assertEqual("ok", soup.get_text(strip=True))
        self.assertEqual(2, get_mock.call_count)
        self.assertEqual(2, sleep_mock.call_count)
        self.assertEqual(
            filing_parser.SEC_FETCH_RETRY_BACKOFF_SECONDS,
            sleep_mock.call_args_list[0].args[0],
        )
        self.assertEqual(
            filing_parser.REQUEST_DELAY_SECONDS,
            sleep_mock.call_args_list[1].args[0],
        )

    @patch("filing_parser.time.sleep")
    @patch("filing_parser.requests.get")
    def test_repeated_503_still_fails_closed_after_bounded_retries(
        self, get_mock, sleep_mock
    ):
        get_mock.side_effect = [
            self._response(503)
            for _ in range(filing_parser.SEC_FETCH_MAX_ATTEMPTS)
        ]

        with self.assertRaises(requests.HTTPError):
            filing_parser.fetch_document("https://www.sec.gov/example.htm")

        self.assertEqual(filing_parser.SEC_FETCH_MAX_ATTEMPTS, get_mock.call_count)
        self.assertEqual(filing_parser.SEC_FETCH_MAX_ATTEMPTS - 1, sleep_mock.call_count)

    @patch("filing_parser.time.sleep")
    @patch("filing_parser.requests.get")
    def test_non_retryable_404_fails_immediately(self, get_mock, sleep_mock):
        get_mock.return_value = self._response(404)

        with self.assertRaises(requests.HTTPError):
            filing_parser.fetch_document("https://www.sec.gov/missing.htm")

        self.assertEqual(1, get_mock.call_count)
        sleep_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
