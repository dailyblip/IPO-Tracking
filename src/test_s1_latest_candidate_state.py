import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SEC_EDGAR_USER_AGENT", "Research Monitor test@example.com")

import s1_monitor


class S1LatestCandidateStateTests(unittest.TestCase):
    @staticmethod
    def _meta(accession, filed, form="S-1/A"):
        return {
            "company_name": "Acme Robotics, Inc.",
            "cik": "1234567",
            "form_type": form,
            "filing_date": filed,
            "accession_no": accession,
        }

    @staticmethod
    def _record(meta):
        return {
            "id": meta["accession_no"],
            "company": meta["company_name"],
            "cik": "0001234567",
            "accession_no": meta["accession_no"],
            "form": meta["form_type"],
            "filed": meta["filing_date"],
            "stage": "Pre-pricing",
            "signals": [],
            "sec_url": "https://www.sec.gov/test",
        }

    @patch("s1_monitor.sync_research_queue")
    @patch("s1_monitor.export_feed")
    @patch("s1_monitor.evaluate_record")
    @patch("s1_monitor.discover_recent_s1")
    def test_newer_deterministic_exclusion_cannot_republish_older_s1(
        self, discover, evaluate, export_feed, sync_queue
    ):
        older = self._meta("older", "2026-09-01", "S-1")
        latest = self._meta("latest", "2026-09-04", "S-1/A")
        discover.return_value = [older, latest]
        evaluate.side_effect = [(self._record(older), True), (None, True)]
        export_feed.return_value = {"filings": []}
        sync_queue.return_value = {"filings": []}

        s1_monitor.run()

        self.assertEqual(export_feed.call_args.args[0], [])
        self.assertEqual(sync_queue.call_args.args[0], [])
        self.assertEqual(
            export_feed.call_args.kwargs["processed_ciks"], {"0001234567"}
        )
        self.assertEqual(
            sync_queue.call_args.kwargs["processed_ciks"], {"0001234567"}
        )

    @patch("s1_monitor.sync_research_queue")
    @patch("s1_monitor.export_feed")
    @patch("s1_monitor.evaluate_record")
    @patch("s1_monitor.discover_recent_s1")
    def test_newer_transient_failure_preserves_existing_state_instead_of_using_older_s1(
        self, discover, evaluate, export_feed, sync_queue
    ):
        older = self._meta("older", "2026-09-01", "S-1")
        latest = self._meta("latest", "2026-09-04", "S-1/A")
        discover.return_value = [older, latest]
        evaluate.side_effect = [(self._record(older), True), (None, False)]
        export_feed.return_value = {"filings": []}
        sync_queue.return_value = {"filings": []}

        s1_monitor.run()

        self.assertEqual(export_feed.call_args.args[0], [])
        self.assertEqual(sync_queue.call_args.args[0], [])
        self.assertEqual(export_feed.call_args.kwargs["processed_ciks"], set())
        self.assertEqual(sync_queue.call_args.kwargs["processed_ciks"], set())

    @patch("s1_monitor.sync_research_queue")
    @patch("s1_monitor.export_feed")
    @patch("s1_monitor.evaluate_record")
    @patch("s1_monitor.discover_recent_s1")
    def test_latest_qualifying_amendment_drives_queue_while_history_keeps_lineage(
        self, discover, evaluate, export_feed, sync_queue
    ):
        amendment = self._meta("amendment", "2026-09-04", "S-1/A")
        initial = self._meta("initial", "2026-09-04", "S-1")
        amendment_record = self._record(amendment)
        initial_record = self._record(initial)
        # Put the S-1 after the amendment to prove same-day form precedence is not
        # accidental list-order precedence.
        discover.return_value = [amendment, initial]
        evaluate.side_effect = [
            (amendment_record, True),
            (initial_record, True),
        ]
        export_feed.return_value = {"filings": []}
        sync_queue.return_value = {"filings": []}

        s1_monitor.run()

        self.assertEqual(
            export_feed.call_args.args[0], [amendment_record, initial_record]
        )
        self.assertEqual(sync_queue.call_args.args[0], [amendment_record])
        self.assertEqual(
            sync_queue.call_args.kwargs["processed_ciks"], {"0001234567"}
        )


if __name__ == "__main__":
    unittest.main()
