from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pandas as pd
from pymongo import MongoClient
import logging
import os
from xAPIConnector import APIClient, loginCommand

load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]
list_pair = ("eurusd", "gbpusd")
# Configure logging
# Set the log file path
log_file = os.path.join(os.getcwd(), "logfile.txt")
# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Create a FileHandler and set its properties
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)

# Create a Formatter and set its properties
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler.setFormatter(formatter)

# Add the FileHandler to the logger
logger.addHandler(file_handler)


def collect(
    pair,
    client,
    timeframe=5,
):
    configs = db["configs"]

    config = configs.find_one({"pair": pair})
    histories = db[pair]

    # Current time
    current_time = datetime.now()

    # Time to subtract
    time_to_subtract = timedelta(minutes=timeframe * 2)
    res = client.commandExecute(
        "getChartLastRequest",
        {
            "info": {
                "period": timeframe,
                "start": config["last_fetch"]
                if "last_fetch" in config
                else (current_time - time_to_subtract).timestamp() * 1000,
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
        records.pop()
        trim_record = list(filter(lambda x: x["ctm"] > config["last_fetch"], records))

        if len(trim_record) > 0:
            logging.info(
                f'cronjob get {len(trim_record)} {pair} candles {records[-1]["ctm"]}'
            )
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
            histories.insert_many(trim_record)


def main():
    # Usage example

    userId = os.getenv("XTB_USER_ID")
    password = os.getenv("XTB_PASSWORD")
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=userId, password=password))

    if loginResponse["status"] == False:
        print("Login failed. Error code: {0}".format(loginResponse["errorCode"]))
        return
    for pair in list_pair:
        collect(pair, client)


if __name__ == "__main__":
    main()
