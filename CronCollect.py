from dotenv import load_dotenv
import os
import pandas as pd
import pymongo
from pymongo import MongoClient
import logging
import os
from xAPIConnector import APIClient, loginCommand
import argparse

load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]
list_pair = ("eurusd", "gbpusd", "audusd", "nzdusd", "usdjpy")


# Create a logger object and set its level to DEBUG
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(os.path.join(os.getcwd(), "logfile.txt"))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)


def collect(
    pair,
    client,
    timeframe,
):
    histories = db[f"{pair}_{timeframe}"]
    last_candle = histories.find_one({}, sort=[("ctm", pymongo.DESCENDING)])
    res = client.commandExecute(
        "getChartLastRequest",
        {
            "info": {
                "period": timeframe,
                "start": last_candle["ctm"] - timeframe * 60000,
                "symbol": pair.upper(),
            }
        },
    )
    if res["status"] == True:
        df = pd.DataFrame(res["returnData"]["rateInfos"])
        digits = res["returnData"]["digits"]
        del df["ctmString"]
        df["close"] = (df["open"] + df["close"]) / pow(10, digits)
        df["high"] = (df["open"] + df["high"]) / pow(10, digits)
        df["low"] = (df["open"] + df["low"]) / pow(10, digits)
        df["open"] = df["open"] / pow(10, digits)
        df["timestamp"] = pd.to_datetime(df["ctm"], unit="ms")

        records = df.to_dict("records")
        print(df)

        if len(records) > 0:
            # logging.info(
            #     f"cronjob get {len(records)} {pair} candles timeframe m{timeframe}"
            # )
            for record in records:
                histories.update_one(
                    {"ctm": record["ctm"]}, {"$set": record}, upsert=True
                )


def main():
    # create a parser object
    parser = argparse.ArgumentParser(description="Collector data candle jobs")
    parser.add_argument("-t", "--timeframe", type=int, help="timeframe")
    args = parser.parse_args()

    userId = os.getenv("XTB_USER_ID")
    password = os.getenv("XTB_PASSWORD")
    try:
        client = APIClient()
        client.timeout = 5
        loginResponse = client.execute(loginCommand(userId=userId, password=password))

        if loginResponse["status"] == False:
            print("Login failed. Error code: {0}".format(loginResponse["errorCode"]))
            return
        for pair in list_pair:
            collect(pair, client, args.timeframe if args.timeframe is not None else 5)
    except Exception as e:
        mongoClient.close()
        logger.error(e)
    mongoClient.close()


if __name__ == "__main__":
    main()
