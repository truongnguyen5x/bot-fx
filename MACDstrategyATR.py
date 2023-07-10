from pymongo import MongoClient
import os
from dotenv import load_dotenv
import pandas as pd
from scipy.signal import find_peaks
import logging
from datetime import datetime, time, timedelta
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
    timezone = pytz.timezone("UTC")
    now = datetime.now(timezone)
    in_session = None
    start_session = datetime.now(timezone)

    for session in config["sessions"]:
        # Chuyển đổi chuỗi thành đối tượng time
        start_str, end_str = session.split("-")
        start_time = time.fromisoformat(start_str)
        end_time = time.fromisoformat(end_str)
        start_session = start_session.replace(
            hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0
        )

        # Lấy múi giờ +0 (UTC+0)
        current_time = now.time()

        # Kiểm tra xem thời gian hiện tại có nằm trong khoảng thời gian hay không
        if start_time <= end_time:
            if start_time <= current_time <= end_time:
                in_session = True
                break
        else:
            if start_time <= current_time:
                in_session = True
                break
            if current_time <= end_time:
                in_session = True
                start_session = start_session - timedelta(days=1)
                break

    if in_session is None:
        print(f"not in session {pair}")
        # not in session
        return
    # print(f"in session {pair}", start_session)

    candles = histories.find().sort("ctm", -1).limit(1000)
    _candles = list(candles)
    _candles.reverse()
    df = pd.DataFrame(_candles)

    # Calculate MACD and signal lines
    ema_12 = df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26

    # Calculate True Range (TR)
    df["tr1"] = df["high"] - df["low"]
    df["tr2"] = abs(df["high"] - df["close"].shift())
    df["tr3"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
    df.drop(["tr1", "tr2", "tr3"], axis=1, inplace=True)

    # Calculate ATR
    df["atr"] = df["tr"].rolling(window=14).mean()

    if df.iloc[-1]["atr"] > config["atr_threshold"]:
        print(f"{pair} atr so high {df.iloc[-1]['atr']}")
        return

    # Find peaks and valleys of the MACD line
    # Find peaks and valleys of the MACD line
    macd_peaks, _ = find_peaks(
        macd, prominence=config["macd_prominence"], distance=config["macd_distance"]
    )
    macd_valleys, _ = find_peaks(
        -macd, prominence=config["macd_prominence"], distance=config["macd_distance"]
    )

    peaks = macd_peaks if trend == "downtrend" else macd_valleys

    last_peak_index = peaks[-1]
    last_peak_candle = _candles[last_peak_index]

    last_peak_time = datetime.fromtimestamp(last_peak_candle["ctm"] / 1000, tz=timezone)

    if last_peak_time < start_session:
        print(f"last peak not in session {pair} {last_peak_time} {start_session}")
        return

    last_order = order_histories.find_one(
        {
            "pair": pair,
            "ctm": {"$gte": last_peak_candle["ctm"]},
            "status": {"$in": ["accepted", "pending"]},
        }
    )

    if last_order is not None:
        print(f"has last order {pair}")
        return
    # open order
    userId = os.getenv("XTB_USER_ID")
    password = os.getenv("XTB_PASSWORD")
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=userId, password=password))
    if loginResponse["status"] == False:
        print("Login failed. Error code: {0}".format(loginResponse["errorCode"]))
        return
    res_symbol = client.commandExecute(
        "getSymbol",
        {
            "symbol": [pair.split("_")[0].upper()],
        },
    )
    if res_symbol["status"] == False:
        return
    ask = res_symbol["returnData"]["ask"]
    bid = res_symbol["returnData"]["bid"]

    if trend == "uptrend":
        if ask > last_peak_candle["close"] + config["slippage"]:
            print(f"buy slippage show far {pair}")
            return
    elif trend == "downtrend":
        if bid < last_peak_candle["close"] - config["slippage"]:
            print(f"sell slippage show far {pair}")
            return

    res_order = client.commandExecute(
        "tradeTransaction",
        {
            "tradeTransInfo": {
                "cmd": 0 if trend == "uptrend" else 1,
                "customComment": "By MACD strategy",
                "expiration": 0,
                "order": 0,
                "price": ask if trend == "uptrend" else bid,
                "sl": round(
                    bid - config["sl"] if trend == "uptrend" else ask + config["sl"],
                    config["digits"],
                ),
                "tp": round(
                    bid + config["tp"] if trend == "uptrend" else ask - config["tp"],
                    config["digits"],
                ),
                "symbol": pair.split("_")[0].upper(),
                "type": 0,
                "volume": config["lots_size"],
            }
        },
    )
    if res_order["status"] == False:
        return
        # bot.send_message(
        #     chat_id=os.getenv("TELEGRAM_USER_ID"),
        #     text=f"MACD strategy {pair} {trend} create order",
        # )

    order_id = res_order["returnData"]["order"]

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
            "ctm_str": datetime.utcfromtimestamp(last_peak_candle["ctm"] / 1000),
            "from": "MACD strategy",
            "order_id": order_id,
            "status": "pending",
            "open_time": int(now.timestamp() * 1000),
            "open_time_str": datetime.utcfromtimestamp(int(now.timestamp())),
        }
    )
