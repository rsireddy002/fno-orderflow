"""
rvol_baseline.py
Builds a 10-day, time-of-day-matched volume baseline for the F&O futures universe.
For each stock, computes average cumulative volume traded by each 5-minute
mark of the trading day, across the last 10 trading days.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

from upstox_downloads import get_intraday_candles
from fno_universe import build_fno_universe

MAX_WORKERS = 8          # concurrent requests — kept modest to avoid rate limits
CANDLE_UNIT = "minutes"
CANDLE_INTERVAL = "5"    # 5-minute candles
DAYS_BACK = 15           # calendar days back (covers ~10 trading days incl. weekends)


def fetch_baseline_for_symbol(entry):
    """
    Fetches candles for one stock's futures contract and computes
    cumulative volume at each time-of-day bucket, per day.
    Returns: {symbol, time_buckets: {HH:MM: [volumes across days]}}
    """
    symbol = entry["symbol"]
    instrument_key = entry["instrument_key"]

    candles = get_intraday_candles(
        instrument_key,
        unit=CANDLE_UNIT,
        interval=CANDLE_INTERVAL,
        days_back=DAYS_BACK,
    )

    if not candles:
        return symbol, {}

    # Group candles by trading day, then compute cumulative volume
    # at each time-of-day bucket within that day.
    by_day = defaultdict(list)
    for candle in candles:
        timestamp = candle[0]          # e.g. '2026-08-17T09:15:00+05:30'
        volume = candle[5]
        date_part, time_part = timestamp.split("T")
        time_bucket = time_part[:5]    # 'HH:MM'
        by_day[date_part].append((time_bucket, volume))

    time_buckets = defaultdict(list)
    for date_part, entries in by_day.items():
        entries.sort(key=lambda x: x[0])
        cumulative = 0
        for time_bucket, volume in entries:
            cumulative += volume
            time_buckets[time_bucket].append(cumulative)

    return symbol, dict(time_buckets)


def build_rvol_baseline():
    """
    Builds the full baseline for all F&O stocks.
    Returns: {symbol: {HH:MM: average_cumulative_volume}}
    """
    universe = build_fno_universe()
    if not universe:
        print("No universe available — aborting baseline build.")
        return {}

    print(f"Fetching {DAYS_BACK}-day baseline for {len(universe)} stocks "
          f"using {MAX_WORKERS} concurrent workers...")

    raw_results = {}
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_baseline_for_symbol, entry): entry["symbol"]
            for entry in universe
        }

        completed = 0
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                sym, time_buckets = future.result()
                raw_results[sym] = time_buckets
            except Exception as e:
                print(f"Error building baseline for {symbol}: {e}")
                raw_results[symbol] = {}

            completed += 1
            if completed % 25 == 0 or completed == len(universe):
                print(f"  Progress: {completed}/{len(universe)}")

    elapsed = time.time() - start_time
    print(f"Baseline fetch complete in {elapsed:.1f} seconds.")

    # Average across days for each time bucket
    baseline = {}
    for symbol, time_buckets in raw_results.items():
        averaged = {}
        for time_bucket, volumes in time_buckets.items():
            if volumes:
                averaged[time_bucket] = sum(volumes) / len(volumes)
        baseline[symbol] = averaged

    return baseline


if __name__ == "__main__":
    baseline = build_rvol_baseline()

    print("\nSample baseline (first stock with data):")
    for symbol, time_buckets in baseline.items():
        if time_buckets:
            print(f"{symbol}:")
            for time_bucket in sorted(time_buckets.keys())[:5]:
                print(f"  {time_bucket} -> avg cumulative volume: {time_buckets[time_bucket]:.0f}")
            break