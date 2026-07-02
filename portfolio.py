"""
Portfolio-tracker. Omdat Yaantje zelf niet handelt (jij drukt op de knop),
log je hier je eigen trades zodat je een eerlijk overzicht hebt van wat je
werkelijk hebt gedaan en wat het opleverde — los van wat de backtest belooft.

Gebruik als losse module (import) of via de command-line functies onderaan.
Data wordt opgeslagen in portfolio.csv (simpel, leesbaar, geen database nodig).
"""

import os
import pandas as pd
from datetime import datetime

PORTFOLIO_FILE = "portfolio.csv"
COLUMNS = ["datum", "symbol", "type", "prijs", "hoeveelheid", "kosten_eur"]


def _load() -> pd.DataFrame:
    if os.path.exists(PORTFOLIO_FILE):
        return pd.read_csv(PORTFOLIO_FILE, parse_dates=["datum"])
    return pd.DataFrame(columns=COLUMNS)


def log_trade(symbol: str, trade_type: str, prijs: float, hoeveelheid: float, kosten_eur: float = 0.0):
    """
    trade_type: 'buy' of 'sell'
    Voeg een trade toe die je ZELF hebt uitgevoerd (na een Yaantje-signaal of los).
    """
    assert trade_type in ("buy", "sell"), "trade_type moet 'buy' of 'sell' zijn"
    df = _load()
    new_row = {
        "datum": datetime.now(),
        "symbol": symbol,
        "type": trade_type,
        "prijs": prijs,
        "hoeveelheid": hoeveelheid,
        "kosten_eur": kosten_eur,
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(PORTFOLIO_FILE, index=False)
    print(f"Gelogd: {trade_type} {hoeveelheid} {symbol} @ {prijs}")


def get_positions() -> pd.DataFrame:
    """Huidige open posities per coin (hoeveelheid nog in bezit + gemiddelde aankoopprijs)."""
    df = _load()
    if df.empty:
        return pd.DataFrame(columns=["symbol", "hoeveelheid", "gem_aankoopprijs"])

    positions = []
    for symbol, group in df.groupby("symbol"):
        buys = group[group["type"] == "buy"]
        sells = group[group["type"] == "sell"]
        held = buys["hoeveelheid"].sum() - sells["hoeveelheid"].sum()
        if held > 1e-9:
            avg_price = (buys["prijs"] * buys["hoeveelheid"]).sum() / buys["hoeveelheid"].sum()
            positions.append({"symbol": symbol, "hoeveelheid": held, "gem_aankoopprijs": avg_price})

    return pd.DataFrame(positions)


def get_realized_pnl() -> pd.DataFrame:
    """Gerealiseerde winst/verlies per coin (alleen afgeronde buy->sell trades, FIFO)."""
    df = _load()
    if df.empty:
        return pd.DataFrame(columns=["symbol", "gerealiseerd_pnl_eur"])

    results = []
    for symbol, group in df.groupby("symbol"):
        group = group.sort_values("datum")
        buy_queue = []  # FIFO: [hoeveelheid, prijs]
        realized = 0.0

        for _, row in group.iterrows():
            if row["type"] == "buy":
                buy_queue.append([row["hoeveelheid"], row["prijs"]])
                realized -= row["kosten_eur"]
            else:  # sell
                qty_to_sell = row["hoeveelheid"]
                realized -= row["kosten_eur"]
                while qty_to_sell > 1e-9 and buy_queue:
                    buy_qty, buy_price = buy_queue[0]
                    matched = min(qty_to_sell, buy_qty)
                    realized += matched * (row["prijs"] - buy_price)
                    buy_queue[0][0] -= matched
                    qty_to_sell -= matched
                    if buy_queue[0][0] <= 1e-9:
                        buy_queue.pop(0)

        results.append({"symbol": symbol, "gerealiseerd_pnl_eur": round(realized, 2)})

    return pd.DataFrame(results)


def print_summary():
    positions = get_positions()
    pnl = get_realized_pnl()

    print("=== Open posities ===")
    if positions.empty:
        print("(geen open posities)")
    else:
        print(positions.to_string(index=False))

    print("\n=== Gerealiseerde winst/verlies (afgeronde trades) ===")
    if pnl.empty:
        print("(nog geen afgeronde trades)")
    else:
        print(pnl.to_string(index=False))
        print(f"\nTotaal gerealiseerd: €{pnl['gerealiseerd_pnl_eur'].sum():.2f}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Gebruik:")
        print("  python portfolio.py log <buy|sell> <symbol> <prijs> <hoeveelheid> [kosten_eur]")
        print("  python portfolio.py summary")
        exit(0)

    command = sys.argv[1]
    if command == "log":
        trade_type, symbol, prijs, hoeveelheid = sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
        kosten = float(sys.argv[6]) if len(sys.argv) > 6 else 0.0
        log_trade(symbol, trade_type, prijs, hoeveelheid, kosten)
    elif command == "summary":
        print_summary()
