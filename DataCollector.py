from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pandas as pd
from pymongo import MongoClient
import logging
from xAPIConnector import APIClient, loginCommand
import argparse

load_dotenv()
# set to true on debug environment only
DEBUG = True
# logger properties
logger = logging.getLogger("jsonSocket")
FORMAT = "[%(asctime)-15s][%(funcName)s:%(lineno)d] %(message)s"
logging.basicConfig(format=FORMAT)

if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.CRITICAL)

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]


def collect(pair, fromTime, toTime):
    collection = db["eurusd"]
    configs = db["configs"]
    # enter your login credentials here
    userId = os.getenv("XTB_USER_ID")
    password = os.getenv("XTB_PASSWORD")

    # create & connect to RR socket
    client = APIClient()

    # connect to RR socket, login
    loginResponse = client.execute(loginCommand(userId=userId, password=password))
    logger.info(str(loginResponse))

    # check if user logged in correctly
    if loginResponse["status"] == False:
        print("Login failed. Error code: {0}".format(loginResponse["errorCode"]))
        return

    # now add 10 minutes
    now = datetime.now()
    end = now + timedelta(minutes=10)

    res = client.commandExecute(
        "getChartRangeRequest",
        {
            "info": {
                "period": 5,
                "end": toTime if toTime is not None else round(end.timestamp() * 1000),
                "start": fromTime,
                "symbol": pair.upper(),
            }
        },
    )
    if res["status"] == True:
        df = pd.DataFrame(res["returnData"]["rateInfos"])
        digits = res["returnData"]["digits"]
        # configs.insert_one({"paid": pair, "digits": digits})
        # df["timestamp"]
        del df["ctmString"]
        df["timestamp"] = pd.to_datetime(df["ctm"], unit="ms")
        print(df)
        # records = df.to_dict("records")
        # collection.insert_many(records)


def main():
    # create a parser object
    parser = argparse.ArgumentParser(description="Collector data candle manually")
    parser.add_argument("pair", type=str, help="currency pair")
    parser.add_argument("start", type=int, help="from timestamp")
    parser.add_argument("-e", "--end", type=int, help="to timestamp")
    args = parser.parse_args()
    collect(args.pair, args.start, args.end)


if __name__ == "__main__":
    main()
