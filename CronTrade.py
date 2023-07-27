from dotenv import load_dotenv
import os
from pymongo import MongoClient
import logging
from MACDstrategyATR import macd
from RSIstrategyATR import rsi
import os
from xAPIConnector import APIClient, loginCommand

load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"), connectTimeoutMS=2000)
db = mongoClient["bot_fx"]
ORDER_STATUS = ["error", "pending", None, "accepted", "rejected"]

# Create a logger object and set its level to DEBUG
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(os.path.join(os.getcwd(), "logfile.txt"))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)


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
    try:
        client = APIClient()
        client.timeout = 5
        loginResponse = client.execute(loginCommand(userId=userId, password=password))

        if loginResponse["status"] == False:
            print("Login failed. Error code: {0}".format(loginResponse["errorCode"]))
            return
        configs = db["configs"]
        pairs = configs.find({"enabled": True})

        check_opened_order(client)
        for pair in pairs:
            if pair["trend"] == "uptrend" or pair["trend"] == "downtrend":
                rsi(pair["pair"], pair["trend"])
                pass
    except Exception as e:
        mongoClient.close()
        logger.error(e)

    mongoClient.close()


if __name__ == "__main__":
    main()
