"""
upstox_downloads.py
Centralized module for all Upstox API network calls.
"""

import os
import io
import gzip
import json
import urllib.parse
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_PATH)

try:
    import streamlit as st
    UPSTOX_API_KEY = st.secrets.get("UPSTOX_API_KEY", os.getenv("UPSTOX_API_KEY"))
    UPSTOX_API_SECRET = st.secrets.get("UPSTOX_API_SECRET", os.getenv("UPSTOX_API_SECRET"))
    UPSTOX_ACCESS_TOKEN = st.secrets.get("UPSTOX_ACCESS_TOKEN", os.getenv("UPSTOX_ACCESS_TOKEN"))
except (ImportError, FileNotFoundError):
    UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")
    UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET")
    UPSTOX_ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")

BASE_URL = "https://api.upstox.com/v3"


def check_config():
    status = {
        "UPSTOX_API_KEY": bool(UPSTOX_API_KEY),
        "UPSTOX_API_SECRET": bool(UPSTOX_API_SECRET),
        "UPSTOX_ACCESS_TOKEN": bool(UPSTOX_ACCESS_TOKEN),
    }
    for key, loaded in status.items():
        flag = "OK" if loaded else "MISSING"
        print(f"{key}: {flag}")
    return all(status.values())


def check_access_token():
    url = "https://api.upstox.com/v2/user/profile"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Network error while checking token: {e}")
        return False

    if response.status_code == 200:
        data = response.json().get("data", {})
        name = data.get("user_name", "Unknown")
        print(f"Access token is VALID. Logged in as: {name}")
        return True
    else:
        print(f"Access token check FAILED. Status: {response.status_code}")
        print(f"Response: {response.text}")
        return False


def get_instrument_master():
    """
    Downloads Upstox's complete NSE instrument master (JSON, gzipped).
    Returns it as a list of instrument dicts.
    """
    url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to download instrument master: {e}")
        return []

    with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
        data = json.load(f)

    print(f"Instrument master downloaded: {len(data)} instruments total.")
    return data


def get_intraday_candles(instrument_key, unit="minutes", interval="30", days_back=1):
    """
    Fetches historical candles for one instrument using Upstox v3 API.

    unit: 'minutes', 'hours', 'days', 'weeks', or 'months'
    interval: the numeric interval within that unit, as a string
              (e.g. unit='minutes', interval='30' -> 30-minute candles)
    days_back: how many calendar days of history to request

    Returns a list of candles sorted oldest-first:
      [timestamp, open, high, low, close, volume, oi]
    """
    encoded_key = urllib.parse.quote(instrument_key, safe="")

    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    url = (
        f"https://api.upstox.com/v3/historical-candle/"
        f"{encoded_key}/{unit}/{interval}/{to_date}/{from_date}"
    )
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching candles for {instrument_key}: {e}")
        return []

    if response.status_code != 200:
        print(f"Failed candles for {instrument_key}: {response.status_code} {response.text}")
        return []

    candles = response.json().get("data", {}).get("candles", [])
    candles.sort(key=lambda c: c[0])
    return candles


def get_full_market_quotes(instrument_keys):
    """
    Fetches live full market quotes (OHLC, volume, depth) for a batch of
    instrument keys in a single request. Upstox allows multiple keys
    comma-separated in one call.

    instrument_keys: list of instrument key strings, e.g. ['NSE_FO|58074', ...]

    Returns: dict keyed by the quote's own key (usually 'EXCHANGE:SYMBOL'),
             each value containing depth, volume, ohlc, etc.
    """
    if not instrument_keys:
        return {}

    joined_keys = ",".join(instrument_keys)
    encoded_keys = urllib.parse.quote(joined_keys, safe=",")

    url = f"https://api.upstox.com/v2/market-quote/quotes?instrument_key={encoded_keys}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}",
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching full market quotes: {e}")
        return {}

    if response.status_code != 200:
        print(f"Failed to fetch quotes: {response.status_code} {response.text}")
        return {}

    return response.json().get("data", {})


if __name__ == "__main__":
    print("Checking .env configuration...")
    ok = check_config()
    if ok:
        print("")
        print("All credentials loaded successfully.")
        print("")
        print("Checking access token validity...")
        check_access_token()
    else:
        print("")
        print("Some credentials are missing - check your .env file.")