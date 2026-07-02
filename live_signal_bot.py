"""
Yaantje — live signaalbot. Checkt periodiek de markt en stuurt een Telegram-bericht
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
import requests
import ccxt
from strategy import add_indicators, generate_signals, position_size

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "VUL_HIER_IN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "VUL_HIER_IN")

BOT_NAME = "Yaantje"
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]   # pas aan naar de coins die je wil monitoren
TIMEFRAME = "1h"
CAPITAL_PER_COIN = {  # verdeel je kapitaal zelf over de coins, of geef iedereen hetzelfde
    "BTC/USDT": 500.0,
    "ETH/USDT": 300.0,
    "SOL/USDT": 200.0,
}
RISK_PCT = 0.01         # riskeer max 1% van het toegewezen kapitaal per trade
CHECK_INTERVAL_SEC = 3600  # elk uur checken (past bij 1h timeframe)


def send_telegram(message: str):
    if TELEGRAM_TOKEN == "VUL_HIER_IN":
        print("[TELEGRAM NIET GECONFIGUREERD] Bericht zou zijn:")
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})


def check_symbol(symbol: str):
    import pandas as pd
    exchange = exchange = ccxt.kraken()  # Kraken i.p.v. Binance: Binance blokkeert cloud-server IP's
    candles = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=250)  # genoeg voor EMA200
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")

    df = add_indicators(df)
    df = generate_signals(df)

    last = df.iloc[-1]
    capital = CAPITAL_PER_COIN.get(symbol, 100.0)

    if last["signal"] == 1:
        entry = last["close"]
        stop = last["stop_price"]
        target = last["target_price"]
        units = position_size(capital, entry, stop, RISK_PCT)
        risk_eur = capital * RISK_PCT

        message = (
            f"🐾 {BOT_NAME} — SIGNAAL: {symbol}\n\n"
            f"Entry: {entry:.4f}\n"
            f"Stop-loss: {stop:.4f}\n"
            f"Target: {target:.4f}\n"
            f"Voorgestelde positie: {units:.6f} {symbol.split('/')[0]}\n"
            f"Risico bij deze trade: €{risk_eur:.2f} ({RISK_PCT*100:.0f}% van toegewezen kapitaal)\n\n"
            f"⚠️ Dit is een signaal op basis van een historische backtest, "
            f"geen garantie. Handel alleen als je zelf akkoord bent met het risico.\n\n"
            f"Tip: log deze trade in portfolio.py als je 'm uitvoert, om je P&L bij te houden."
        )
        send_telegram(message)
        print(f"[{symbol}] Signaal verstuurd om {last.name}")
    else:
        print(f"[{symbol}] Geen signaal om {last.name} (RSI={last['rsi']:.1f}, boven EMA={last['close'] > last['ema']})")


def check_and_alert():
    for symbol in SYMBOLS:
        try:
            check_symbol(symbol)
        except Exception as e:
            print(f"[{symbol}] Fout: {e}")


if __name__ == "__main__":
    print(f"{BOT_NAME} gestart voor {', '.join(SYMBOLS)}, check elke {CHECK_INTERVAL_SEC}s...")
    while True:
        check_and_alert()
        time.sleep(CHECK_INTERVAL_SEC)
