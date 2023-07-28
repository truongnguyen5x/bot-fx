from dotenv import load_dotenv
import os
import pandas as pd
import pymongo
from pymongo import MongoClient
import logging
import os
import yfinance as yf
import argparse
from datetime import datetime, timedelta, timezone

load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"), connectTimeoutMS=2000)
db = mongoClient["bot_fx"]
list_pair = ("eurusd", "gbpusd", "audusd", "nzdusd", "usdjpy")


# Create a logger object and set its level to DEBUG
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(os.path.join(os.getcwd(), "logfile.txt"))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)


def symbol_label(pair):
    return f"{pair.upper()}=X"


def collect(
    timeframe,
):
    # histories = db[f"{pair}_{timeframe}"]
    # last_candle = histories.find_one({}, sort=[("ctm", pymongo.DESCENDING)])
    # TODO:
    current_time_utc = datetime.now(timezone.utc)
    start_date_utc = current_time_utc - timedelta(minutes=3 * int(timeframe))

    symbol = list(map(symbol_label, list_pair))
    interval = f"{timeframe}m"
    data = yf.download(
        symbol, start=start_date_utc, interval=interval, group_by="ticker"
    )

    for pair in list_pair:
        df = data[symbol_label(pair)]
        # df.rename(
        #     columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"},
        #     inplace=True,
        # )
        df.columns = ["open", "high", "low", "close", "adj close", "vol"]
        del df["adj close"]
        del df["vol"]
        df["timestamp"] = pd.to_datetime(df.index)
        df["ctm"] = df["timestamp"].apply(lambda x: int(x.timestamp() * 1000))

        records = df.to_dict("records")
        print(df)

        # if len(records) > 0:
        #     # logging.info(
        #     #     f"cronjob get {len(records)} {pair} candles timeframe m{timeframe}"
        #     # )
        #     for record in records:
        #         histories.update_one(
        #             {"ctm": record["ctm"]}, {"$set": record}, upsert=True
        #         )


def main():
    # create a parser object
    parser = argparse.ArgumentParser(description="Collector data candle jobs")
    parser.add_argument("-t", "--timeframe", type=int, help="timeframe")
    args = parser.parse_args()

    try:
        collect(args.timeframe if args.timeframe is not None else 5)
    except Exception as e:
        mongoClient.close()
        logger.error(e)
    mongoClient.close()


if __name__ == "__main__":
    main()
