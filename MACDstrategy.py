from pymongo import MongoClient
import os
from dotenv import load_dotenv
import pandas as pd
from scipy.signal import find_peaks
import logging
from datetime import datetime
from xAPIConnector import APIClient, loginCommand
import pytz
import requests

load_dotenv()


# Create a logger object and set its level to DEBUG
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(os.path.join(os.getcwd(), "logfile.txt"))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)


def open_order(pair, tp, sl, lots_size, trend, digits):
    # open order
    userId = os.getenv("XTB_USER_ID")
    password = os.getenv("XTB_PASSWORD")
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=userId, password=password))
    if loginResponse["status"] == False:
        print("Login failed. Error code: {0}".format(loginResponse["errorCode"]))
        return
    res = client.commandExecute(
        "getSymbol",
        {
            "symbol": [pair.split("_")[0].upper()],
        },
    )
    if res["status"] == True:
        ask = res["returnData"]["ask"]
        bid = res["returnData"]["bid"]

        res_order = client.commandExecute(
            "tradeTransaction",
            {
                "tradeTransInfo": {
                    "cmd": 0 if trend == "uptrend" else 1,
                    "customComment": "By MACD strategy",
                    "expiration": 0,
                    "order": 0,
                    "price": ask if trend == "uptrend" else bid,
                    "sl": round(bid - sl if trend == "uptrend" else ask + sl, digits),
                    "tp": round(bid + tp if trend == "uptrend" else ask - tp, digits),
                    "symbol": pair.split("_")[0].upper(),
                    "type": 0,
                    "volume": lots_size,
                }
            },
        )
        if res_order["status"] == True:
            # bot.send_message(
            #     chat_id=os.getenv("TELEGRAM_USER_ID"),
            #     text=f"MACD strategy {pair} {trend} create order",
            # )

            order_id = res_order["returnData"]["order"]
            return order_id


def macd(pair, trend):
    # bot.send_message(
    #     chat_id=os.getenv("TELEGRAM_USER_ID"),
    #     text=f"MACD strategy {pair} {trend} create order",
    # )
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
        # not in session
        return

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

    last_peak_time = datetime.fromtimestamp(last_peak_candle["ctm"] / 1000, tz=timezone)
    last_peak_time_1 = last_peak_time.replace(
        year=now.year, month=now.month, day=now.day
    )

    if last_peak_time_1 < start_hour or last_peak_time_1 > end_hour:
        # last peak not in session
        return

    last_order = order_histories.find_one(
        {
            "pair": pair,
            "ctm": {"$gte": last_peak_candle["ctm"]},
            "status": {"$in": ["accepted", "pending"]},
        }
    )

    if last_order is None:
        order_id = open_order(
            pair=pair,
            trend=trend,
            sl=config["sl"],
            tp=config["tp"],
            digits=config["digits"],
            lots_size=config["lots_size"],
        )
        if order_id is not None:
            logger.info(
                f"{trend} create order {pair} at {now} base on MACD {last_peak_candle['ctm']}"
            )
            requests.get(
                f'https://api.telegram.org/bot{os.getenv("TELEGRAM_BOT_TOKEN")}/sendMessage?chat_id={os.getenv("TELEGRAM_USER_ID")}&text={trend} create order {pair} base on MACD'
            )
            order_histories.insert_one(
                {
                    "pair": pair,
                    "ctm": last_peak_candle["ctm"],
                    "ctm_str": datetime.utcfromtimestamp(
                        last_peak_candle["ctm"] / 1000
                    ),
                    "from": "MACD strategy",
                    "order_id": order_id,
                    "status": "pending",
                    "open_time": int(now.timestamp() * 1000),
                    "open_time_str": datetime.utcfromtimestamp(int(now.timestamp())),
                }
            )
