"""
Thylacoleo — live signaalbot. Checkt periodiek de markt en stuurt een Telegram-bericht
met een CONCREET voorstel (entry, stop-loss, target, positiegrootte) als de
strategie een signaal geeft. Voert zelf GEEN trades uit — jij beslist en
handelt handmatig. Dat is een bewuste keuze: een menselijke check voordat
er geld beweegt, is een extra veiligheidslaag.

Setup:
1. pip install ccxt python-telegram-bot pandas
2. Maak een Telegram bot via @BotFather -> krijg een BOT_TOKEN
3. Stuur je bot een bericht, zoek je CHAT_ID op (bv. via @userinfobot of de Telegram API)
4. Vul TELEGRAM_TOKEN en TELEGRAM_CHAT_ID hieronder in (of als environment variables)
5. Draai dit script continu (bv. op een gratis Railway/Render service, of gewoon
   op je eigen computer/Raspberry Pi met een cronjob elk uur)

BELANGRIJK: dit is GEEN garantie op winst. Het is een hulpmiddel dat je helpt
consistent een vooraf getest plan te volgen, met risicomanagement, in plaats
van te gokken op emotie.
"""

import os
import time
import math
import requests
import ccxt
from strategy import position_size
from backtest import run_backtest, compute_metrics

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "VUL_HIER_IN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "VUL_HIER_IN")

BOT_NAME = "Thylacoleo"
QUOTE_CURRENCIES = ("USDT", "USD")   # scan alle coins met deze quote-valuta
SYMBOL_REFRESH_INTERVAL = 24         # ververs de coinlijst elke X checks (nieuwe coins kunnen bijkomen)
TIMEFRAME = "15m"
TOTAL_CAPITAL = 1000.0   # jouw totale kapitaal, verdeeld over alle mogelijke signalen
RISK_PCT = 0.01          # riskeer max 1% van TOTAL_CAPITAL per trade, ongeacht welke coin
CHECK_INTERVAL_SEC = 900  # elke 15 min checken (past bij 15m timeframe)
DELAY_BETWEEN_SYMBOLS_SEC = 1.0  # kleine pauze tussen coins, om Kraken niet te overspoelen

# Filter op historische betrouwbaarheid: GEEN garantie voor de toekomst, alleen een
# indicatie of de strategie op DEZE coin recent vaker gelijk had dan ongelijk.
MIN_WIN_RATE = 0.55       # toon alleen coins met minstens 55% winnende trades in de recente historie
MIN_TRADES_FOR_FILTER = 5  # te weinig historische trades = te onbetrouwbaar om iets over te zeggen, dan overslaan


def get_all_symbols(exchange):
    """Haalt alle spot-markten op met USDT of USD als quote-valuta."""
    markets = exchange.load_markets()
    symbols = [
        s for s, m in markets.items()
        if m.get("spot") and m.get("active") and m.get("quote") in QUOTE_CURRENCIES
    ]
    return sorted(symbols)


def send_telegram(message: str):
    if TELEGRAM_TOKEN == "VUL_HIER_IN":
        print("[TELEGRAM NIET GECONFIGUREERD] Bericht zou zijn:")
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})


def check_symbol(exchange, symbol: str):
    import pandas as pd
    candles = exchange.fetch_ohlcv(symbol, TIMEFRAME)  # geen limit: Kraken geeft dan zelf zijn standaard hoeveelheid data terug
    raw_df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    raw_df["timestamp"] = pd.to_datetime(raw_df["timestamp"], unit="ms")
    raw_df = raw_df.set_index("timestamp")

    if len(raw_df) < 210:
        return  # te weinig data voor EMA200, sla stil over (te veel coins om dit te loggen)

    # Backtest op dezelfde opgehaalde data: dit geeft ons zowel het actuele signaal
    # (laatste rij) als hoe vaak deze strategie op DEZE coin recent gelijk had.
    result_df, trades = run_backtest(raw_df, initial_capital=TOTAL_CAPITAL, risk_pct=RISK_PCT)

    if len(trades) < MIN_TRADES_FOR_FILTER:
        return  # te weinig historische trades op deze coin om betrouwbaar te filteren

    win_rate = trades["win"].mean()
    if win_rate < MIN_WIN_RATE:
        return  # historisch niet overtuigend genoeg op deze coin, overslaan

    last = result_df.iloc[-1]

    if last["signal"] == 1:
        entry = last["close"]
        stop = last["stop_price"]
        target = last["target_price"]
        units = position_size(TOTAL_CAPITAL, entry, stop, RISK_PCT)
        risk_eur = TOTAL_CAPITAL * RISK_PCT
        positie_kosten_eur = units * entry
        # Rond af naar boven op een handig bedrag (5% marge voor fees/koersschommeling, dan afgerond op 10 euro)
        voorgesteld_storten = math.ceil((positie_kosten_eur * 1.05) / 10) * 10

        message = (
            f"🦁 {BOT_NAME} — SIGNAAL: {symbol}\n\n"
            f"Entry: {entry:.6f}\n"
            f"Stop-loss: {stop:.6f}\n"
            f"Target: {target:.6f}\n"
            f"Voorgestelde positie: {units:.6f} {symbol.split('/')[0]}\n"
            f"Kostprijs van deze positie: €{positie_kosten_eur:.2f}\n"
            f"👉 Stort/zorg voor ongeveer €{voorgesteld_storten:.0f} op je exchange "
            f"(inclusief kleine marge voor fees/koersschommeling)\n"
            f"Risico bij deze trade: €{risk_eur:.2f} ({RISK_PCT*100:.0f}% van totaalkapitaal)\n\n"
            f"📊 Historische win rate op deze coin (recente periode): {win_rate*100:.0f}% "
            f"over {len(trades)} trades. Dit is GEEN garantie voor de toekomst, "
            f"alleen hoe de strategie zich hier recent gedroeg.\n\n"
            f"⚠️ Handel alleen als je zelf akkoord bent met het risico.\n\n"
            f"Tip: log deze trade in portfolio.py als je 'm uitvoert, om je P&L bij te houden."
        )
        send_telegram(message)
        print(f"[{symbol}] Signaal verstuurd om {last.name} (win rate {win_rate*100:.0f}% over {len(trades)} trades)")


def check_and_alert(exchange, symbols):
    n_signals = 0
    for symbol in symbols:
        try:
            check_symbol(exchange, symbol)
        except Exception as e:
            print(f"[{symbol}] Fout (overgeslagen): {e}")
        time.sleep(DELAY_BETWEEN_SYMBOLS_SEC)
    print(f"Check voltooid voor {len(symbols)} coins.")


if __name__ == "__main__":
    exchange = ccxt.kraken({"enableRateLimit": True})  # Kraken i.p.v. Binance: Binance blokkeert cloud-server IP's

    print("Coinlijst ophalen van Kraken...")
    symbols = get_all_symbols(exchange)
    print(f"{BOT_NAME} gestart, {len(symbols)} coins gevonden (quote: {', '.join(QUOTE_CURRENCIES)}), "
          f"check elke {CHECK_INTERVAL_SEC}s...")

    check_count = 0
    while True:
        if check_count % SYMBOL_REFRESH_INTERVAL == 0 and check_count > 0:
            print("Coinlijst vernieuwen...")
            symbols = get_all_symbols(exchange)
            print(f"{len(symbols)} coins nu actief.")

        check_and_alert(exchange, symbols)
        check_count += 1
        time.sleep(CHECK_INTERVAL_SEC)
