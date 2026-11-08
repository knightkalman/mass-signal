#!/usr/bin/env python3
"""Collect public market prices for all 22 watchlist tickers into a JSON Lines file.

Based on nvda-signal monitor architecture, extended to handle all 22 tickers from:
trading-targets/tickers.md
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sqlite3
import time
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LOGGER = logging.getLogger("mass_monitor")
USER_AGENT = "mass-monitor/1.0 (public multi-ticker data collector)"
HTTP_TIMEOUT_SECONDS = 15

# 22 Watchlist Tickers Specification
WATCHLIST_TICKERS: list[dict[str, Any]] = [
    {"symbol": "OIL", "instrument_id": 17, "yahoo_symbol": "CL=F", "name": "Crude Oil (WTI)", "asset_class": "commodities"},
    {"symbol": "NVDA", "instrument_id": 1137, "yahoo_symbol": "NVDA", "name": "NVIDIA Corporation", "asset_class": "stocks"},
    {"symbol": "MU", "instrument_id": 1130, "yahoo_symbol": "MU", "name": "Micron Technology Inc.", "asset_class": "stocks"},
    {"symbol": "ORCL", "instrument_id": 1135, "yahoo_symbol": "ORCL", "name": "Oracle Corporation", "asset_class": "stocks"},
    {"symbol": "CAT", "instrument_id": 1012, "yahoo_symbol": "CAT", "name": "Caterpillar Inc.", "asset_class": "stocks"},
    {"symbol": "GS", "instrument_id": 1467, "yahoo_symbol": "GS", "name": "The Goldman Sachs Group Inc.", "asset_class": "stocks"},
    {"symbol": "INTC", "instrument_id": 1021, "yahoo_symbol": "INTC", "name": "Intel Corporation", "asset_class": "stocks"},
    {"symbol": "MS", "instrument_id": 1976, "yahoo_symbol": "MS", "name": "Morgan Stanley", "asset_class": "stocks"},
    {"symbol": "PLTR", "instrument_id": 7991, "yahoo_symbol": "PLTR", "name": "Palantir Technologies Inc.", "asset_class": "stocks"},
    {"symbol": "SHOP", "instrument_id": 4148, "yahoo_symbol": "SHOP", "name": "Shopify Inc.", "asset_class": "stocks"},
    {"symbol": "AMD", "instrument_id": 1832, "yahoo_symbol": "AMD", "name": "Advanced Micro Devices Inc.", "asset_class": "stocks"},
    {"symbol": "ASML", "instrument_id": 4244, "yahoo_symbol": "ASML", "name": "ASML Holding N.V.", "asset_class": "stocks"},
    {"symbol": "ARM", "instrument_id": 1365, "yahoo_symbol": "ARM", "name": "Arm Holdings plc", "asset_class": "stocks"},
    {"symbol": "TXN", "instrument_id": 1634, "yahoo_symbol": "TXN", "name": "Texas Instruments Incorporated", "asset_class": "stocks"},
    {"symbol": "COP", "instrument_id": 1510, "yahoo_symbol": "COP", "name": "ConocoPhillips", "asset_class": "stocks"},
    {"symbol": "MRK", "instrument_id": 1027, "yahoo_symbol": "MRK", "name": "Merck & Co., Inc.", "asset_class": "stocks"},
    {"symbol": "GOOGL", "instrument_id": 6434, "yahoo_symbol": "GOOGL", "name": "Alphabet Inc.", "asset_class": "stocks"},
    {"symbol": "QCOM", "instrument_id": 1485, "yahoo_symbol": "QCOM", "name": "QUALCOMM Incorporated", "asset_class": "stocks"},
    {"symbol": "AMZN", "instrument_id": 1005, "yahoo_symbol": "AMZN", "name": "Amazon.com Inc.", "asset_class": "stocks"},
    {"symbol": "META", "instrument_id": 1003, "yahoo_symbol": "META", "name": "Meta Platforms Inc.", "asset_class": "stocks"},
    {"symbol": "CRWD", "instrument_id": 5506, "yahoo_symbol": "CRWD", "name": "CrowdStrike Holdings Inc.", "asset_class": "stocks"},
    {"symbol": "HOOD", "instrument_id": 9272, "yahoo_symbol": "HOOD", "name": "Robinhood Markets, Inc.", "asset_class": "stocks"},
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def request_bytes(url: str, headers: dict[str, str] | None = None) -> bytes:
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return response.read()


def sentiment_for_change(
    price: float, previous_close: float | None
) -> tuple[float | None, float | None, str]:
    if previous_close is None or previous_close == 0:
        return None, None, "unknown"

    change = price - previous_close
    change_percent = change / previous_close * 100
    sentiment = "bullish" if change > 0 else "bearish" if change < 0 else "neutral"
    return round(change, 6), round(change_percent, 4), sentiment


def fetch_yahoo_price(
    symbol_def: dict[str, Any],
    range_str: str = "7d",
    interval_str: str = "15m",
) -> dict[str, Any]:
    symbol = symbol_def["symbol"]
    yahoo_symbol = symbol_def["yahoo_symbol"]
    name = symbol_def["name"]
    instrument_id = symbol_def["instrument_id"]
    asset_class = symbol_def["asset_class"]

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote(yahoo_symbol, safe='')}?range={range_str}&interval={interval_str}"
    )
    payload = json.loads(request_bytes(url))
    chart = payload.get("chart", {})
    if chart.get("error"):
        raise ValueError(f"Price provider error for {symbol}: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise ValueError(f"Price provider returned no chart data for {symbol}")

    result = results[0]
    metadata = result.get("meta", {})
    quote_data = (result.get("indicators", {}).get("quote") or [{}])[0]
    timestamps = result.get("timestamp") or []
    closes = quote_data.get("close", [])

    history = [
        {
            "timestamp": datetime.fromtimestamp(ts, timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "price": round(float(close), 4),
        }
        for ts, close in zip(timestamps, closes)
        if ts is not None and close is not None
    ]

    current_price = metadata.get("regularMarketPrice")
    if current_price is None and history:
        current_price = history[-1]["price"]
    if current_price is None:
        raise ValueError(f"No current price for {symbol}")

    previous_close = metadata.get("chartPreviousClose")
    timestamp = metadata.get("regularMarketTime")
    if timestamp is None and timestamps:
        timestamp = timestamps[-1]

    quote_timestamp = (
        datetime.fromtimestamp(timestamp, timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
        if timestamp is not None
        else (history[-1]["timestamp"] if history else utc_now())
    )

    change, change_percent, sentiment = sentiment_for_change(
        float(current_price),
        float(previous_close) if previous_close is not None else None,
    )

    return {
        "symbol": symbol,
        "yahoo_symbol": yahoo_symbol,
        "instrument_id": instrument_id,
        "name": name,
        "asset_class": asset_class,
        "price": float(current_price),
        "currency": metadata.get("currency", "USD"),
        "unit": "barrel" if asset_class == "commodities" else "share",
        "price_timestamp": quote_timestamp,
        "history": history,
        "previous_close": (
            float(previous_close) if previous_close is not None else None
        ),
        "change": change,
        "change_percent": change_percent,
        "change_basis": "previous_daily_close",
        "price_change_sentiment": sentiment,
        "source": "Yahoo Finance chart API",
        "source_url": url,
    }


def collect_all_prices(
    tickers: list[dict[str, Any]] | None = None,
    max_workers: int = 8,
    range_str: str = "1d",
    interval_str: str = "5m",
) -> tuple[dict[str, Any], list[str]]:
    tickers = tickers or WATCHLIST_TICKERS
    prices: dict[str, Any] = {}
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(fetch_yahoo_price, ticker_def, range_str, interval_str): ticker_def["symbol"]
            for ticker_def in tickers
        }
        for future in as_completed(future_map):
            sym = future_map[future]
            try:
                data = future.result()
                prices[sym.lower()] = data
            except Exception as exc:
                LOGGER.error("Failed to fetch price for %s: %s", sym, exc)
                errors.append(f"{sym}: {exc}")

    return prices, errors


def record_payload(prices: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "collected_at": utc_now(),
        "tickers_count": len(prices),
        "prices": prices,
        "errors": errors,
    }


def append_record(output_path: Path, payload: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, separators=(",", ":")) + "\n")


def init_state_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at TEXT NOT NULL,
            tickers_count INTEGER NOT NULL,
            error_count INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def main() -> int:
    parser = argparse.ArgumentParser(description="Mass Signal Multi-Ticker Price Collector")
    parser.add_argument("--once", action="store_true", help="Run collection once and exit")
    parser.add_argument("--output", type=Path, default=Path("data/mass/latest.jsonl"), help="Output JSONL path")
    parser.add_argument("--state-db", type=Path, default=Path("data/mass_monitor_state.sqlite3"), help="SQLite state db path")
    parser.add_argument("--range", dest="history_range", default="7d", help="History range (1d, 5d, 7d, 1mo)")
    parser.add_argument("--interval", dest="history_interval", default="15m", help="History interval (1m, 5m, 15m)")
    parser.add_argument("--interval-seconds", type=int, default=300, help="Loop interval in seconds when not running --once")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    LOGGER.info("Starting mass_monitor with %d tickers...", len(WATCHLIST_TICKERS))

    conn = init_state_db(args.state_db)

    def do_cycle() -> None:
        start_t = time.time()
        prices, errors = collect_all_prices(range_str=args.history_range, interval_str=args.history_interval)
        payload = record_payload(prices, errors)
        append_record(args.output, payload)
        conn.execute(
            "INSERT INTO runs (collected_at, tickers_count, error_count) VALUES (?, ?, ?)",
            (payload["collected_at"], len(prices), len(errors)),
        )
        conn.commit()
        duration = time.time() - start_t
        LOGGER.info(
            "Collected %d/%d tickers in %.2fs (errors: %d) -> %s",
            len(prices),
            len(WATCHLIST_TICKERS),
            duration,
            len(errors),
            args.output,
        )

    if args.once:
        do_cycle()
        return 0

    while True:
        try:
            do_cycle()
        except Exception as exc:
            LOGGER.exception("Error in collection loop: %s", exc)
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
