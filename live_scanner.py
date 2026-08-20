"""
live_scanner.py
Combines live RVOL (vs. 10-day time-of-day baseline) with order-flow
depth imbalance to rank the F&O futures universe.
"""

from datetime import datetime

from upstox_downloads import get_full_market_quotes
from fno_universe import build_fno_universe
from rvol_baseline import build_rvol_baseline


def nearest_baseline_volume(time_buckets, now_str):
    """
    Finds the baseline cumulative volume for the closest time bucket
    at or before the current time.
    time_buckets: {'HH:MM': avg_volume}
    now_str: 'HH:MM'
    """
    if not time_buckets:
        return None

    candidates = [t for t in time_buckets.keys() if t <= now_str]
    if not candidates:
        return None

    closest = max(candidates)
    return time_buckets[closest]


def compute_imbalance(quote):
    """
    Computes bid/ask depth imbalance from a single quote's data.
    Returns (imbalance_ratio, buy_qty, sell_qty).
    """
    total_buy = quote.get("total_buy_quantity", 0)
    total_sell = quote.get("total_sell_quantity", 0)

    if total_sell > 0:
        ratio = round(total_buy / total_sell, 2)
    elif total_buy > 0:
        ratio = float("inf")
    else:
        ratio = 1.0

    return ratio, total_buy, total_sell


def run_scan():
    universe = build_fno_universe()
    if not universe:
        print("No universe available.")
        return []

    print("Building RVOL baseline...")
    baseline = build_rvol_baseline()

    symbol_to_key = {entry["symbol"]: entry["instrument_key"] for entry in universe}
    instrument_keys = list(symbol_to_key.values())

    print("Fetching live quotes for all stocks...")
    quotes = get_full_market_quotes(instrument_keys)

    # quotes is keyed by 'NSE_FO:SYMBOL' (trading symbol), not instrument_key,
    # so build a lookup from instrument_token back to our universe symbol.
    key_to_symbol = {v: k for k, v in symbol_to_key.items()}

    now_str = datetime.now().strftime("%H:%M")

    results = []

    for quote_key, quote in quotes.items():
        instrument_token = quote.get("instrument_token")
        symbol = key_to_symbol.get(instrument_token)
        if not symbol:
            continue

        current_volume = quote.get("volume", 0)
        time_buckets = baseline.get(symbol, {})
        baseline_volume = nearest_baseline_volume(time_buckets, now_str)

        if baseline_volume and baseline_volume > 0:
            rvol = round(current_volume / baseline_volume, 2)
        else:
            rvol = None

        imbalance_ratio, buy_qty, sell_qty = compute_imbalance(quote)

        results.append({
            "symbol": symbol,
            "rvol": rvol,
            "current_volume": current_volume,
            "baseline_volume": baseline_volume,
            "imbalance_ratio": imbalance_ratio,
            "buy_qty": buy_qty,
            "sell_qty": sell_qty,
            "last_price": quote.get("last_price"),
        })

    # Sort by RVOL descending (None values go last)
    results.sort(key=lambda r: (r["rvol"] is None, -(r["rvol"] or 0)))

    return results


if __name__ == "__main__":
    results = run_scan()

    print(f"\n{'Symbol':<25} {'RVOL':>6} {'Imbalance':>10} {'LTP':>10}")
    print("-" * 55)
    for r in results[:20]:
        rvol_str = f"{r['rvol']:.2f}" if r["rvol"] is not None else "N/A"
        imb_str = f"{r['imbalance_ratio']:.2f}" if r["imbalance_ratio"] != float("inf") else "inf"
        price_str = f"{r['last_price']:.2f}" if r["last_price"] is not None else "N/A"
        print(f"{r['symbol']:<25} {rvol_str:>6} {imb_str:>10} {price_str:>10}")