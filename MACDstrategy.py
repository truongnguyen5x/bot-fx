from pymongo import MongoClient
import os
from dotenv import load_dotenv


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
    candles = db[pair]
