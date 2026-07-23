"""
price_lookup.py

Fetches current market price for a given ticker using the Finnhub API.
Requires MARKET_DATA_API_KEY to be set as an environment variable.
"""

import os
import time
import requests

FINNHUB_BASE_URL = "https://finnhub.io/api/v2"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


class PriceLookupError(Exception):
    """Raised when a price cannot be retrieved for a ticker."""
    pass


def _get_api_key() -> str:
    api_key = os.environ.get("MARKET_DATA_API_KEY")
    if not api_key:
        raise PriceLookupError(
            "MARKET_DATA_API_KEY environment variable is not set."
        )
    return api_key


def get_current_price(ticker: str) -> float:
    """
    Return the current price for a given ticker symbol.

    Raises PriceLookupError if the ticker is invalid, not found, or the
    API call fails after retries.
    """
    api_key = _get_api_key()
    ticker = ticker.strip().upper()

    url = f"{FINNHUB_BASE_URL}/quote"
    params = {"symbol": ticker, "token": api_key}

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Finnhub returns all zeros for an unrecognized symbol rather
            # than an HTTP error, so we need to check explicitly.
            current_price = data.get("c")
            if current_price is None or current_price == 0:
                raise PriceLookupError(
                    f"No price data returned for ticker '{ticker}'. "
                    f"It may be delisted, mistyped, or not yet trading."
                )
            return float(current_price)

        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            continue

    raise PriceLookupError(
        f"Failed to fetch price for '{ticker}' after {MAX_RETRIES} attempts: {last_error}"
    )


def get_current_prices(tickers: list) -> dict:
    """
    Look up current prices for multiple tickers.

    Returns a dict mapping ticker -> price, or ticker -> None if the
    lookup failed for that specific ticker (does not raise, so one bad
    ticker doesn't block the rest of the batch).
    """
    results = {}
    for ticker in tickers:
        try:
            results[ticker] = get_current_price(ticker)
        except PriceLookupError as e:
            print(f"[price_lookup] WARNING: {e}")
            results[ticker] = None
        # Finnhub free tier allows 60 calls/min; a small delay keeps us
        # comfortably under that even with many holders per company.
        time.sleep(1)
    return results


if __name__ == "__main__":
    # Quick manual test: python price_lookup.py AAPL MSFT
    import sys

    test_tickers = sys.argv[1:] or ["AAPL"]
    prices = get_current_prices(test_tickers)
    for t, p in prices.items():
        print(f"{t}: {p}")
