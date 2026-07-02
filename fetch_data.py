"""
Haalt echte historische crypto-koersdata op via een exchange (Binance, publiek,
geen account/API-key nodig voor market-data).

Dit script vereist internetverbinding en de 'ccxt' library — draai dit LOKAAL
op je eigen computer (niet in deze sandbox, die heeft geen internettoegang).

Installeren:
    pip install ccxt pandas

Gebruik:
    python fetch_data.py
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta


def fetch_ohlcv(symbol="BTC/USDT", timeframe="1h", days_back=365, exchange_id="binance"):
    exchange = getattr(ccxt, exchange_id)()
    since = exchange.parse8601((datetime.utcnow() - timedelta(days=days_back)).isoformat())

    all_candles = []
    while True:
        candles = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not candles:
            break
        all_candles += candles
        since = candles[-1][0] + 1
        if len(candles) < 1000:
            break

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")
    return df


def fetch_multiple(symbols, timeframe="1h", days_back=365):
    """Haalt data op voor meerdere coins in één keer, slaat elk op als aparte CSV."""
    for symbol in symbols:
        print(f"Ophalen: {symbol}...")
        df = fetch_ohlcv(symbol=symbol, timeframe=timeframe, days_back=days_back)
        filename = f"data_{symbol.replace('/', '_')}.csv"
        df.to_csv(filename)
        print(f"  Opgeslagen: {filename} ({len(df)} candles)")


if __name__ == "__main__":
    # Pas deze lijst aan met de coins die je wil monitoren
    SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    fetch_multiple(SYMBOLS, timeframe="1h", days_back=365)
