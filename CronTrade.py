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


ORDER_STATUS = ["error", "pending", None, "accepted", "rejected"]


def check_opened_order(client):
    order_histories = db["orders"]
    pending_orders = order_histories.find({"status": "pending"})
    for order in pending_orders:
        res = client.commandExecute(
            "tradeTransactionStatus", {"order": order["order_id"]}
        )
        if res["status"] == True:
            requestStatus = res["returnData"]["requestStatus"]
            order_histories.update_one(
                {"order_id": order["order_id"]},
                {"$set": {"status": ORDER_STATUS[requestStatus]}},
            )


def main():
    userId = os.getenv("XTB_USER_ID")
    password = os.getenv("XTB_PASSWORD")
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=userId, password=password))

    if loginResponse["status"] == False:
        print("Login failed. Error code: {0}".format(loginResponse["errorCode"]))
        return
    configs = db["configs"]
    pairs = configs.find({"enabled": True})
    check_opened_order(client)
    for pair in pairs:
        macd(pair["pair"], pair["trend"])

    mongoClient.close()


if __name__ == "__main__":
    main()
