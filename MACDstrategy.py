from pymongo import MongoClient
import os
from dotenv import load_dotenv
import pandas as pd
from scipy.signal import find_peaks

load_dotenv()

# class Strategy:
#     def __init__(self, name, pair, timeframe, trend) -> None:
#         self.name = name
#         self.pair = pair
#         self.timeframe = timeframe
#         self.trend = trend


# class MACDstrategy(Strategy):
#     def __init__(self, pair, timeframe, trend) -> None:
#         super().__init__("macd", pair, timeframe, trend)

#     def execute():
#         print("execute")
#         pass


def macd(pair, timeframe, trend):
    print(pair)
    mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))

    db = mongoClient["bot_fx"]
    order_histories = db["orders"]
    histories = db[pair]
    configs = db["configs"]
    config = configs.find_one({"pair": pair})

    candles = histories.find().sort("ctm", -1).limit(200)
    _candles = list(candles)
    _candles.reverse()
    df = pd.DataFrame(_candles)

    # Calculate MACD and signal lines
    ema_12 = df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26

    # Find peaks and valleys of the MACD line
    peaks, _ = find_peaks(
        macd if trend == "downtrend" else -macd,
        prominence=config["macd_prominence"],
        distance=config["macd_distance"],
    )
    last_peak_index = peaks[-1]
    last_peaK_candle = _candles[last_peak_index]

    print(last_peaK_candle)
