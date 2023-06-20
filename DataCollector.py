from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pandas as pd
from pymongo import MongoClient
import logging
from xAPIConnector import APIClient, loginCommand

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
client = MongoClient(os.getenv("MONGO_CONNECTION"))
db = client["bot_fx"]
collection = db["eurusd_histories"]


def main():
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
    now = datetime.now()
    end = now + timedelta(minutes=10)
    res = client.commandExecute(
        "getChartRangeRequest",
        {
            "info": {
                "period": 5,
                "end": round(end.timestamp() * 1000),
                "start": 1673888400000,
                "symbol": "EURUSD",
            }
        },
    )
    if res["status"] == True:
        df = pd.DataFrame(res["returnData"]["rateInfos"])
        digits = res["returnData"]["digits"]
        # df["timestamp"]
        del df["ctmString"]
        df["timestamp"] = pd.to_datetime(df["ctm"], unit="ms")
        records = df.to_dict("records")
        collection.insert_many(records)


if __name__ == "__main__":
    main()
