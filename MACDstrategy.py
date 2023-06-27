from pymongo import MongoClient
import os
from dotenv import load_dotenv
import pandas as pd
from scipy.signal import find_peaks
import logging
from datetime import datetime
from xAPIConnector import APIClient, loginCommand
import pytz

load_dotenv()
# set to true on debug environment only
DEBUG = True

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


def macd(pair, timeframe, trend):
    mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))

    db = mongoClient["bot_fx"]
    order_histories = db["orders"]
    histories = db[pair]
    configs = db["configs"]
    config = configs.find_one({"pair": pair})

    # check session EU, US
    # Lấy múi giờ +0
    timezone = pytz.timezone("Etc/GMT")
    now = datetime.now(timezone)
    start_hour = now.replace(
        hour=config["start_hour"].hour,
        minute=config["start_hour"].minute,
        second=0,
        microsecond=0,
    )
    end_hour = now.replace(
        hour=config["end_hour"].hour,
        minute=config["end_hour"].minute,
        second=0,
        microsecond=0,
    )
    if now < start_hour or now > end_hour:
        # TODO:
        print("not in session")
        # return

    candles = histories.find().sort("ctm", -1).limit(200)
    _candles = list(candles)
    _candles.reverse()
    df = pd.DataFrame(_candles)

    # Calculate MACD and signal lines
    ema_12 = df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26

    # Find peaks and valleys of the MACD line
    peaks, _ = find_peaks(
        macd if trend == "downtrend" else -macd,
        prominence=config["macd_prominence"],
        distance=config["macd_distance"],
    )
    last_peak_index = peaks[-1]
    last_peak_candle = _candles[last_peak_index]

    last_peak_ctm = datetime.fromtimestamp(last_peak_candle["ctm"] / 1000, tz=timezone)

    if last_peak_ctm < start_hour or last_peak_ctm > end_hour:
        # TODO:
        print("last peak not in session")
        return

    last_order = order_histories.find_one(
        {"pair": pair, "ctm": {"$gte": last_peak_candle["ctm"]}}
    )

    if last_order is None:
        # open order
        userId = os.getenv("XTB_USER_ID")
        password = os.getenv("XTB_PASSWORD")
        client = APIClient()
        loginResponse = client.execute(loginCommand(userId=userId, password=password))
        if loginResponse["status"] == False:
            print("Login failed. Error code: {0}".format(loginResponse["errorCode"]))
            return

        # res = client.commandExecute(
        #     "tradeTransaction",
        #     {
        #         "tradeTransInfo": {
        #             "cmd": 0 if trend == "uptrend" else 1,
        #             "customComment": "By MACD strategy",
        #             "expiration": 0,
        #             "order": 0,
        #             "price": 1.4,
        #             "sl": 0,
        #             "tp": 0,
        #             "symbol": "EURUSD",
        #             "type": 0,
        #             "volume": 0.1,
        #         }
        #     },
        # )
        # print(res)
