from dotenv import load_dotenv
import os
from pymongo import MongoClient
import logging
from datetime import datetime, time, timedelta, timezone
import pandas as pd
from scipy.signal import find_peaks
import requests
import pytz


load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"), connectTimeoutMS=2000)
db = mongoClient["bot_fx"]


# Create a logger object and set its level to DEBUG
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(os.path.join(os.getcwd(), "logfile.txt"))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)


def calculate_rsi(prices, window=14):
    delta = prices.diff()
    up = delta.copy()
    down = delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    average_gain = up.rolling(window).mean()
    average_loss = abs(down.rolling(window).mean())
    relative_strength = average_gain / average_loss
    rsi = 100.0 - (100.0 / (1.0 + relative_strength))
    return rsi


def notify(pair, trend, strategy_name, configs, ctm):
    _time = datetime.fromtimestamp(ctm / 1000, pytz.utc).astimezone(
        pytz.timezone("Etc/GMT-7")
    )
    requests.get(
        f'https://api.telegram.org/bot{os.getenv("TELEGRAM_BOT_TOKEN")}/sendMessage?chat_id={os.getenv("TELEGRAM_USER_ID")}&text={"Buy" if trend == "uptrend" else "Sell"} in {pair} with {strategy_name} at {_time.strftime("%d-%m-%Y %H:%M:%S")}'
    )


def check_signal(pair, trend):
    configs = db["configs"]
    config = configs.find_one({"pair": pair})
    histories = db[pair]
    now = datetime.now(timezone.utc)
    candles = histories.find().sort("ctm", -1).limit(1000)
    _candles = list(candles)
    _candles.reverse()
    df = pd.DataFrame(_candles)

    # Calculate MACD and signal lines
    ema_12 = df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    # Find peaks and valleys of the MACD line
    macd_peaks, _ = find_peaks(
        macd, prominence=config["macd_prominence"], distance=config["macd_distance"]
    )
    macd_valleys, _ = find_peaks(
        -macd, prominence=config["macd_prominence"], distance=config["macd_distance"]
    )
    macd_point = macd_peaks if trend == "downtrend" else macd_valleys
    last_peak_macd_index = macd_point[-1]
    last_peak_macd_candle = _candles[last_peak_macd_index]

    if (
        "macd_peak_ctm"
        not in config
        # or last_peak_macd_candle["ctm"] > config["macd_peak_ctm"]
    ):
        configs.update_one(
            {"pair": pair}, {"$set": {"macd_peak_ctm": last_peak_macd_candle["ctm"]}}
        )
        notify(
            pair=pair,
            trend=trend,
            strategy_name="MACD",
            configs=configs,
            ctm=last_peak_macd_candle["ctm"],
        )

    rsi = calculate_rsi(df["close"], window=14)
    rsi_peaks, _ = find_peaks(
        rsi, prominence=config["rsi_prominence"], distance=config["rsi_distance"]
    )
    rsi_valleys, _ = find_peaks(
        -rsi, prominence=config["rsi_prominence"], distance=config["rsi_distance"]
    )
    rsi_point = rsi_peaks if trend == "downtrend" else rsi_valleys
    last_peak_rsi_index = rsi_point[-1]
    last_peak_rsi_candle = _candles[last_peak_rsi_index]

    # if (
    #     "rsi_peak_ctm" not in config
    #     or last_peak_rsi_candle["ctm"] > config["rsi_peak_ctm"]
    # ):
    #     configs.update_one(
    #         {"pair": pair}, {"$set": {"rsi_peak_ctm": last_peak_rsi_candle["ctm"]}}
    #     )
    #     notify(
    #         pair=pair,
    #         trend=trend,
    #         strategy_name="RSI",
    #         configs=configs,
    #         ctm=last_peak_rsi_candle["ctm"],
    #     )
    # TODO:
    notify(
        pair=pair,
        trend=trend,
        strategy_name="RSI",
        configs=configs,
        ctm=last_peak_rsi_candle["ctm"],
    )

    # Calculate True Range (TR)
    df["tr1"] = df["high"] - df["low"]
    df["tr2"] = abs(df["high"] - df["close"].shift())
    df["tr3"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
    df.drop(["tr1", "tr2", "tr3"], axis=1, inplace=True)
    # Calculate ATR
    df["atr"] = df["tr"].rolling(window=config["atr_length"]).mean()
    df["atr_min"] = df["atr"].rolling(config["atr_length"]).min()

    # if df.iloc[-1]["atr_min"] > config["atr_threshold"]:
    #     reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} atr is too high {df.iloc[-1]['atr_min']} > {config['atr_threshold']}"
    #     print(reason)
    #     # configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
    #     return


def main():
    try:
        configs = db["configs"]
        pairs = configs.find({"enabled": True})
        for pair in pairs:
            if pair["trend"] == "uptrend" or pair["trend"] == "downtrend":
                check_signal(pair["pair"], pair["trend"])
                pass
    except Exception as e:
        mongoClient.close()
        logger.error(e)

    mongoClient.close()


if __name__ == "__main__":
    main()
