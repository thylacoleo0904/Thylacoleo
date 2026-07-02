"""
Registry van strategieën. Elke strategie is een functie die een OHLCV-dataframe
neemt en er 'signal', 'stop_price', 'target_price' kolommen aan toevoegt.

Zo kun je meerdere strategieën eerlijk vergelijken op dezelfde data via dezelfde
backtest-engine (backtest.py) — appels met appels vergelijken.
"""

import numpy as np
import pandas as pd
from strategy import add_indicators, generate_signals as trend_rsi_signals


def strategy_trend_rsi(df: pd.DataFrame) -> pd.DataFrame:
    """Bestaande strategie: EMA200-trendfilter + RSI oversold-kruising."""
    df = add_indicators(df)
    df = trend_rsi_signals(df)
    return df


def strategy_macd_cross(df: pd.DataFrame, atr_stop_mult=2.0, atr_target_mult=3.0) -> pd.DataFrame:
    """
    Alternatieve strategie: MACD-lijn kruist boven de signaallijn, terwijl prijs
    boven EMA50 staat (kortere trendfilter dan de EMA200-strategie -> reageert
    sneller, maar ook gevoeliger voor valse signalen in zijwaartse markten).
    """
    df = df.copy()
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    macd_cross_up = (df["macd"] > df["macd_signal"]) & (df["macd"].shift(1) <= df["macd_signal"].shift(1))
    uptrend = df["close"] > df["ema50"]

    df["signal"] = (macd_cross_up & uptrend).astype(int)
    df["stop_price"] = df["close"] - atr_stop_mult * df["atr"]
    df["target_price"] = df["close"] + atr_target_mult * df["atr"]
    return df


def strategy_breakout(df: pd.DataFrame, lookback=20, atr_stop_mult=1.5, atr_target_mult=3.0) -> pd.DataFrame:
    """
    Alternatieve strategie: koop bij een uitbraak boven de hoogste high van de
    afgelopen `lookback` candles (Donchian-breakout). Vangt sterke trends vroeg,
    maar geeft vaker valse signalen ("fakeouts") in grillige markten.
    """
    df = df.copy()
    df["rolling_high"] = df["high"].rolling(lookback).max().shift(1)

    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    df["signal"] = (df["close"] > df["rolling_high"]).astype(int)
    df["stop_price"] = df["close"] - atr_stop_mult * df["atr"]
    df["target_price"] = df["close"] + atr_target_mult * df["atr"]
    return df


STRATEGIES = {
    "trend_rsi": strategy_trend_rsi,
    "macd_cross": strategy_macd_cross,
    "breakout": strategy_breakout,
}
