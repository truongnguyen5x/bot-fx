from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pandas as pd
from pymongo import MongoClient

from xAPIConnector import APIClient, loginCommand
import argparse

load_dotenv()


mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]


def collect(pair, fromTime):
    collection = db[pair]
    configs = db["configs"]

    userId = os.getenv("XTB_USER_ID")
    password = os.getenv("XTB_PASSWORD")
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=userId, password=password))
    if loginResponse["status"] == False:
        print("Login failed. Error code: {0}".format(loginResponse["errorCode"]))
        return

    res = client.commandExecute(
        "getChartLastRequest",
        {
            "info": {
                "period": 5,
                "start": fromTime,
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
        print(df)
        records = df.to_dict("records")
        records.pop()
        collection.delete_many({})
        collection.insert_many(records)
        configs.update_one(
            {"pair": pair},
            {
                "$set": {
                    "last_fetch": records[-1]["ctm"],
                    "last_fetch_date": datetime.utcfromtimestamp(
                        records[-1]["ctm"] / 1000
                    ),
                }
            },
        )


def main():
    # create a parser object
    parser = argparse.ArgumentParser(description="Collector data candle manually")
    parser.add_argument("pair", type=str, help="currency pair")
    parser.add_argument("start", type=int, help="from timestamp")
    args = parser.parse_args()
    collect(args.pair, args.start)


if __name__ == "__main__":
    main()
