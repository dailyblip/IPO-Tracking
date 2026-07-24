"""
sheets_writer.py

Writes/upserts IPO tracking rows to a shared Google Sheet using a
service account. Requires GOOGLE_SERVICE_ACCOUNT_JSON (the full JSON
key content, as a string) to be set as an environment variable, and
the target sheet to be shared with the service account's client_email
(Editor access).
"""

import os
import json
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Column order for the main tracking tab. Keep this in sync with
# whatever main.py / qc_review.py produce per row.
COLUMNS = [
    "Company Name",
    "Ticker",
    "Filing Price",
    "Actual Price",
    "Current Price",
    "Holder Name",
    "Shares",
    "Cash Value",
    "Stanford Grade",
    "Stanford Justification",
    "Lock-Up Expiry",
    "QC Status",
    "QC Notes",
    "Last Updated",
]

MAIN_TAB_NAME = "IPO Tracker"
QC_TAB_NAME = "QC Flags"


def _get_client() -> gspread.Client:
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw_json:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON environment variable is not set."
        )
    service_account_info = json.loads(raw_json)
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_or_create_worksheet(spreadsheet, title, header):
    try:
        worksheet = spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(header) + 2)
        worksheet.append_row(header)
        return worksheet

    existing_header = worksheet.row_values(1)
    if not existing_header:
        worksheet.append_row(header)
    return worksheet


def _row_key(row: dict) -> tuple:
    """Unique identity for a row: one ticker/holder combination."""
    return (row.get("Ticker", "").upper(), row.get("Holder Name", "").strip().lower())


def fetch_existing_rows(spreadsheet_id: str) -> dict:
    """
    Fetch all current rows from the main tab, keyed by (ticker, holder
    name), so callers (e.g. qc_review.py) can compare today's values
    against the last run before writing. Returns {} if the tab is
    empty or doesn't exist yet.
    """
    client = _get_client()
    spreadsheet = client.open_by_key(spreadsheet_id)

    try:
        main_ws = spreadsheet.worksheet(MAIN_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        return {}

    existing_values = main_ws.get_all_values()
    if len(existing_values) < 2:
        return {}

    header = existing_values[0]
    data_rows = existing_values[1:]

    result = {}
    for data_row in data_rows:
        row_dict = dict(zip(header, data_row))
        result[_row_key(row_dict)] = row_dict
    return result


def ensure_tabs_exist(spreadsheet_id: str) -> None:
    """
    Create both tabs with headers if they don't exist yet, without
    writing any data rows. Called on every run - including runs that
    produce zero rows - so the Sheet always shows its structure and
    confirms the pipeline is actually reaching it.
    """
    client = _get_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    _get_or_create_worksheet(spreadsheet, MAIN_TAB_NAME, COLUMNS)
    _get_or_create_worksheet(spreadsheet, QC_TAB_NAME, COLUMNS)


def upsert_rows(spreadsheet_id: str, rows: list) -> dict:
    """
    Write or update rows in the main IPO Tracker tab.

    `rows` is a list of dicts keyed by the COLUMNS names above.
    Existing rows (matched by ticker + holder name) are updated in
    place; new combinations are appended. Rows with a QC Status other
    than "Verified" are also mirrored to the QC Flags tab.

    Returns a summary dict: {"new": n, "updated": n, "flagged": n}
    """
    client = _get_client()
    spreadsheet = client.open_by_key(spreadsheet_id)

    main_ws = _get_or_create_worksheet(spreadsheet, MAIN_TAB_NAME, COLUMNS)
    qc_ws = _get_or_create_worksheet(spreadsheet, QC_TAB_NAME, COLUMNS)

    existing_values = main_ws.get_all_values()
    existing_header = existing_values[0] if existing_values else COLUMNS
    existing_data_rows = existing_values[1:] if len(existing_values) > 1 else []

    # Map existing rows by key -> sheet row number (1-indexed, +1 for header)
    key_to_sheet_row = {}
    for i, existing_row in enumerate(existing_data_rows):
        row_dict = dict(zip(existing_header, existing_row))
        key_to_sheet_row[_row_key(row_dict)] = i + 2  # +2: header row + 1-indexing

    new_count = 0
    updated_count = 0
    flagged_count = 0
    rows_to_append = []

    for row in rows:
        ordered_values = [str(row.get(col, "")) for col in COLUMNS]
        key = _row_key(row)

        if key in key_to_sheet_row:
            sheet_row_num = key_to_sheet_row[key]
            # Anchor cell only - gspread expands the range to fit the
            # values array automatically.
            main_ws.update(f"A{sheet_row_num}", [ordered_values])
            updated_count += 1
        else:
            rows_to_append.append(ordered_values)
            new_count += 1

        if row.get("QC Status", "Verified") != "Verified":
            flagged_count += 1

    if rows_to_append:
        main_ws.append_rows(rows_to_append)

    # Refresh QC tab fully each run: it should only ever show current
    # flags, not accumulate stale ones from prior runs.
    qc_rows = [row for row in rows if row.get("QC Status", "Verified") != "Verified"]
    qc_ws.clear()
    qc_ws.append_row(COLUMNS)
    if qc_rows:
        qc_ws.append_rows([[str(r.get(col, "")) for col in COLUMNS] for r in qc_rows])

    return {"new": new_count, "updated": updated_count, "flagged": flagged_count}


if __name__ == "__main__":
    # Quick manual test - requires SPREADSHEET_ID env var and a real
    # sheet already shared with the service account's client_email.
    test_spreadsheet_id = os.environ.get("SPREADSHEET_ID")
    if not test_spreadsheet_id:
        print("Set SPREADSHEET_ID env var to test.")
    else:
        test_rows = [{
            "Company Name": "Test Co",
            "Ticker": "TEST",
            "Filing Price": "18.00",
            "Actual Price": "20.00",
            "Current Price": "22.50",
            "Holder Name": "Jane Example",
            "Shares": "1000000",
            "Cash Value": "22500000",
            "Stanford Grade": "3",
            "Stanford Justification": "Bio mentions 'Palo Alto' but no direct Stanford mention found in two searches.",
            "Lock-Up Expiry": "2027-01-15",
            "QC Status": "Needs Review",
            "QC Notes": "Stanford grade based on indirect location match only.",
            "Last Updated": "2026-07-23",
        }]
        summary = upsert_rows(test_spreadsheet_id, test_rows)
        print(summary)
