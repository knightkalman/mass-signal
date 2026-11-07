import json
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from mass_monitor import (
    WATCHLIST_TICKERS,
    append_record,
    collect_all_prices,
    fetch_yahoo_price,
    init_state_db,
    record_payload,
    sentiment_for_change,
)


class MassMonitorTests(TestCase):
    def test_watchlist_contains_all_22_tickers(self):
        self.assertEqual(len(WATCHLIST_TICKERS), 22)
        symbols = [t["symbol"] for t in WATCHLIST_TICKERS]
        expected_symbols = [
            "OIL", "NVDA", "MU", "ORCL", "CAT", "GS", "INTC", "MS", "PLTR", "SHOP",
            "AMD", "ASML", "ARM", "TXN", "COP", "MRK", "GOOGL", "QCOM", "AMZN",
            "META", "CRWD", "HOOD"
        ]
        self.assertEqual(symbols, expected_symbols)

        # Check OIL has CL=F and commodities asset class
        oil = next(t for t in WATCHLIST_TICKERS if t["symbol"] == "OIL")
        self.assertEqual(oil["instrument_id"], 17)
        self.assertEqual(oil["yahoo_symbol"], "CL=F")
        self.assertEqual(oil["asset_class"], "commodities")

        # Check NVDA has 1137 and stocks
        nvda = next(t for t in WATCHLIST_TICKERS if t["symbol"] == "NVDA")
        self.assertEqual(nvda["instrument_id"], 1137)
        self.assertEqual(nvda["asset_class"], "stocks")

    def test_sentiment_for_change(self):
        change, pct, sentiment = sentiment_for_change(105.0, 100.0)
        self.assertEqual(change, 5.0)
        self.assertEqual(pct, 5.0)
        self.assertEqual(sentiment, "bullish")

        change, pct, sentiment = sentiment_for_change(95.0, 100.0)
        self.assertEqual(change, -5.0)
        self.assertEqual(pct, -5.0)
        self.assertEqual(sentiment, "bearish")

        change, pct, sentiment = sentiment_for_change(100.0, 100.0)
        self.assertEqual(change, 0.0)
        self.assertEqual(pct, 0.0)
        self.assertEqual(sentiment, "neutral")

        change, pct, sentiment = sentiment_for_change(100.0, None)
        self.assertIsNone(change)
        self.assertIsNone(pct)
        self.assertEqual(sentiment, "unknown")

    def test_fetch_yahoo_price_parses_chart_response(self):
        sample_payload = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "currency": "USD",
                            "regularMarketPrice": 450.50,
                            "regularMarketTime": 1730000000,
                            "chartPreviousClose": 440.0,
                        },
                        "timestamp": [1729999000, 1730000000],
                        "indicators": {
                            "quote": [
                                {
                                    "close": [445.0, 450.50]
                                }
                            ]
                        },
                    }
                ],
                "error": None,
            }
        }

        ticker_def = {
            "symbol": "AMD",
            "yahoo_symbol": "AMD",
            "name": "Advanced Micro Devices Inc.",
            "instrument_id": 1832,
            "asset_class": "stocks",
        }

        with patch("mass_monitor.request_bytes", return_value=json.dumps(sample_payload).encode()):
            data = fetch_yahoo_price(ticker_def)

        self.assertEqual(data["symbol"], "AMD")
        self.assertEqual(data["instrument_id"], 1832)
        self.assertEqual(data["price"], 450.50)
        self.assertEqual(data["previous_close"], 440.0)
        self.assertEqual(data["change"], 10.5)
        self.assertEqual(data["price_change_sentiment"], "bullish")
        self.assertEqual(len(data["history"]), 2)
        self.assertEqual(data["history"][-1]["price"], 450.50)

    def test_record_payload_and_append(self):
        prices = {
            "nvda": {"symbol": "NVDA", "price": 186.5},
            "oil": {"symbol": "OIL", "price": 90.5},
        }
        errors = []
        payload = record_payload(prices, errors)
        self.assertEqual(payload["tickers_count"], 2)
        self.assertIn("collected_at", payload)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "test.jsonl"
            append_record(out_file, payload)
            lines = out_file.read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lines), 1)
            parsed = json.loads(lines[0])
            self.assertEqual(parsed["tickers_count"], 2)

    def test_init_state_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.sqlite3"
            conn = init_state_db(db_path)
            conn.execute("INSERT INTO runs (collected_at, tickers_count, error_count) VALUES ('2026-11-08T00:00:00Z', 22, 0)")
            conn.commit()
            cur = conn.execute("SELECT COUNT(*) FROM runs")
            self.assertEqual(cur.fetchone()[0], 1)
            conn.close()
