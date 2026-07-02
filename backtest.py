"""
Backtest-engine. Simuleert de strategie op historische data met realistische
kosten (fees + slippage), zodat de resultaten niet kunstmatig te goed lijken.

BELANGRIJK: een backtest laat zien hoe de strategie in het VERLEDEN presteerde.
Dat is geen garantie voor de toekomst — markten veranderen. Gebruik dit om
te filteren op "duidelijk kapotte" strategieën, niet als bewijs van toekomstige winst.
"""

import pandas as pd
import numpy as np
from strategy import add_indicators, generate_signals, position_size


def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = 1000.0,
    risk_pct: float = 0.01,
    fee_pct: float = 0.001,      # 0.1% per trade, typisch voor exchanges
    slippage_pct: float = 0.0005,  # 0.05% — prijs bewogen tegen je tegen de tijd dat order uitgevoerd is
    signal_fn=None,  # optioneel: andere strategie-functie (df -> df met 'signal'/'stop_price'/'target_price'), default = strategy.py
):
    if signal_fn is None:
        df = add_indicators(df)
        df = generate_signals(df)
    else:
        df = signal_fn(df)

    capital = initial_capital
    equity_curve = []
    trades = []
    in_position = False
    entry_price = stop_price = target_price = units = 0.0

    for i, row in df.iterrows():
        if not in_position and row["signal"] == 1 and not np.isnan(row["atr"]):
            entry_price = row["close"] * (1 + slippage_pct)
            stop_price = row["stop_price"]
            target_price = row["target_price"]
            units = position_size(capital, entry_price, stop_price, risk_pct)
            cost = units * entry_price * fee_pct
            capital -= cost
            in_position = True
            trade_entry_capital = capital

        elif in_position:
            hit_stop = row["low"] <= stop_price
            hit_target = row["high"] >= target_price

            if hit_stop or hit_target:
                exit_price = stop_price if hit_stop else target_price
                exit_price *= (1 - slippage_pct)
                pnl = units * (exit_price - entry_price)
                fee = units * exit_price * fee_pct
                capital += pnl - fee
                trades.append({
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl - fee,
                    "win": pnl > 0,
                })
                in_position = False

        equity_curve.append(capital if not in_position else capital)

    df["equity"] = equity_curve
    return df, pd.DataFrame(trades)


def compute_metrics(df: pd.DataFrame, trades: pd.DataFrame, initial_capital: float, periods_per_year=365):
    if len(trades) == 0:
        return {"error": "Geen trades uitgevoerd in deze periode — pas parameters aan of gebruik meer data."}

    final_equity = df["equity"].iloc[-1]
    total_return_pct = (final_equity / initial_capital - 1) * 100

    n_days = (df.index[-1] - df.index[0]).days if hasattr(df.index[-1], "days") else len(df)
    n_years = max(n_days / 365, 0.01)
    cagr_pct = ((final_equity / initial_capital) ** (1 / n_years) - 1) * 100

    equity = df["equity"]
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_drawdown_pct = drawdown.min() * 100

    win_rate = trades["win"].mean() * 100
    avg_win = trades.loc[trades["win"], "pnl"].mean() if trades["win"].any() else 0
    avg_loss = trades.loc[~trades["win"], "pnl"].mean() if (~trades["win"]).any() else 0
    profit_factor = (
        trades.loc[trades["win"], "pnl"].sum() / abs(trades.loc[~trades["win"], "pnl"].sum())
        if (~trades["win"]).any() and trades.loc[~trades["win"], "pnl"].sum() != 0
        else float("inf")
    )

    daily_returns = df["equity"].pct_change().dropna()
    sharpe = (
        (daily_returns.mean() / daily_returns.std()) * np.sqrt(periods_per_year)
        if daily_returns.std() > 0 else 0
    )

    return {
        "totaal_rendement_%": round(total_return_pct, 2),
        "CAGR_%": round(cagr_pct, 2),
        "max_drawdown_%": round(max_drawdown_pct, 2),
        "aantal_trades": len(trades),
        "win_rate_%": round(win_rate, 1),
        "gem_winst_per_trade": round(avg_win, 2),
        "gem_verlies_per_trade": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf (geen verliezende trades)",
        "sharpe_ratio": round(sharpe, 2),
    }
