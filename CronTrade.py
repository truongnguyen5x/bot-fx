from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pandas as pd
import pymongo
from pymongo import MongoClient
import logging
from MACDstrategy import macd
import os
from xAPIConnector import APIClient, loginCommand


load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]
list_pair = ("eurusd", "gbpusd", "audusd", "nzdusd", "usdjpy")
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


def main():
    userId = os.getenv("XTB_USER_ID")
    password = os.getenv("XTB_PASSWORD")
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=userId, password=password))

    if loginResponse["status"] == False:
        print("Login failed. Error code: {0}".format(loginResponse["errorCode"]))
        return
    configs = db["configs"]
    enabled_pair = configs.find({"enabled": True})
    for pair in enabled_pair:
        macd(pair["pair"], 5, pair["trend"])

    mongoClient.close()


if __name__ == "__main__":
    main()
