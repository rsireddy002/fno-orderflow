"""
streamlit_app.py
Live F&O scanner: RVOL + order-flow imbalance, auto-refreshing.
"""

import time
import pandas as pd
import streamlit as st

from live_scanner import run_scan

st.set_page_config(page_title="F&O RVOL + Order Flow Scanner", layout="wide")

st.title("F&O Futures Scanner — RVOL + Order Flow")
st.caption("Ranked by RVOL vs. 10-day time-of-day baseline, with bid/ask depth imbalance")

REFRESH_SECONDS = 10

placeholder = st.empty()


def render_table():
    results = run_scan()

    if not results:
        st.warning("No data available. Check your access token or network connection.")
        return

    df = pd.DataFrame(results)

    # Clean up display columns and formatting
    df = df[[
        "symbol", "rvol", "imbalance_ratio", "last_price",
        "current_volume", "baseline_volume", "buy_qty", "sell_qty"
    ]]
    df.columns = [
        "Symbol", "RVOL", "Imbalance", "LTP",
        "Volume", "Baseline Vol", "Buy Qty", "Sell Qty"
    ]

    df["RVOL"] = df["RVOL"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
    df["Imbalance"] = df["Imbalance"].apply(
        lambda x: "inf" if x == float("inf") else f"{x:.2f}"
    )
    df["LTP"] = df["LTP"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")

    st.dataframe(df, use_container_width=True, height=700)


with placeholder.container():
    render_table()
    st.caption(f"Last updated: {time.strftime('%H:%M:%S')} | Auto-refreshing every {REFRESH_SECONDS}s")

time.sleep(REFRESH_SECONDS)
st.rerun()