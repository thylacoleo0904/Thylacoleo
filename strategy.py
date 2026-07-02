"""
Trend + momentum strategie met volatiliteits-gebaseerd risicomanagement.

Logica:
- Trendfilter: prijs boven EMA200 = alleen longs toegestaan (we handelen mee met de trend,
  niet ertegenin — kortetermijn-reversals tegen de trend zijn de meeste "verliezers")
- Timing: RSI(14) kruist omhoog vanuit oversold (<35) terwijl trend intact is = entry-signaal
- Exit: ATR-gebaseerde stop-loss en take-profit (past zich aan aan huidige volatiliteit,
  in plaats van een vaste "5% stop" die in rustige markten te ruim en in wilde markten te krap is)
- Positiegrootte: risico per trade is een VAST percentage van kapitaal (bv. 1%), nooit een vast
  bedrag. Dit is de belangrijkste regel: het beperkt hoeveel één slechte trade kan kosten.
"""

import pandas as pd
import numpy as np


def add_indicators(df: pd.DataFrame, ema_period=200, rsi_period=14, atr_period=14) -> pd.DataFrame:
    df = df.copy()

    # Trend filter
    df["ema"] = df["close"].ewm(span=ema_period, adjust=False).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(rsi_period).mean()
    avg_loss = loss.rolling(rsi_period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    # ATR (volatiliteit, gebruikt voor stop-loss/target afstand)
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(atr_period).mean()

    return df


def generate_signals(df: pd.DataFrame, rsi_oversold=35, atr_stop_mult=2.0, atr_target_mult=3.0) -> pd.DataFrame:
    """
    Voegt een 'signal' kolom toe: 1 = koopsignaal op deze candle.
    Ook 'stop_price' en 'target_price' voor risicomanagement.
    """
    df = df.copy()
    uptrend = df["close"] > df["ema"]
    rsi_cross_up = (df["rsi"] > rsi_oversold) & (df["rsi"].shift(1) <= rsi_oversold)

    df["signal"] = ((uptrend) & (rsi_cross_up)).astype(int)
    df["stop_price"] = df["close"] - atr_stop_mult * df["atr"]
    df["target_price"] = df["close"] + atr_target_mult * df["atr"]

    return df


def position_size(capital: float, entry_price: float, stop_price: float, risk_pct: float = 0.01) -> float:
    """
    Bepaalt hoeveel je koopt zodat je bij het raken van de stop-loss maximaal
    `risk_pct` van je kapitaal verliest. Dit is de kern van risicomanagement:
    nooit meer riskeren dan je vooraf besluit, ongeacht hoe "zeker" een signaal aanvoelt.
    """
    risk_amount = capital * risk_pct
    risk_per_unit = entry_price - stop_price
    if risk_per_unit <= 0:
        return 0.0
    return risk_amount / risk_per_unit
