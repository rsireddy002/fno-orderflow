"""
fno_universe.py
Builds the current F&O futures universe from Upstox's instrument master.
For each underlying stock, keeps only the near-month (soonest-expiry) future.
"""

from datetime import datetime
from upstox_downloads import get_instrument_master


def build_fno_universe():
    """
    Returns a list of dicts: [{symbol, instrument_key, expiry, lot_size}, ...]
    One entry per underlying — the near-month future only.
    """
    instruments = get_instrument_master()

    if not instruments:
        print("No instrument data available.")
        return []

    # Step 1: keep only NSE F&O futures contracts
    futures = [
        inst for inst in instruments
        if inst.get("segment") == "NSE_FO"
        and inst.get("instrument_type") == "FUT"
    ]

    print(f"Total F&O futures contracts found: {len(futures)}")

    # Step 2: group by underlying symbol, keep the nearest expiry per symbol
    nearest_by_symbol = {}

    for inst in futures:
        # Upstox instrument master uses 'name' as the underlying symbol
        # for futures, and 'expiry' as an epoch-millisecond timestamp.
        symbol = inst.get("name")
        expiry_raw = inst.get("expiry")

        if not symbol or expiry_raw is None:
            continue

        try:
            expiry_date = datetime.fromtimestamp(expiry_raw / 1000)
        except (TypeError, ValueError):
            continue

        existing = nearest_by_symbol.get(symbol)
        if existing is None or expiry_date < existing["expiry_date"]:
            nearest_by_symbol[symbol] = {
                "symbol": symbol,
                "instrument_key": inst.get("instrument_key"),
                "expiry_date": expiry_date,
                "lot_size": inst.get("lot_size"),
            }

    universe = list(nearest_by_symbol.values())
    universe.sort(key=lambda x: x["symbol"])

    print(f"F&O universe built: {len(universe)} unique underlyings (near-month futures).")
    return universe


if __name__ == "__main__":
    universe = build_fno_universe()
    print("\nFirst 5 entries:")
    for entry in universe[:5]:
        print(entry)