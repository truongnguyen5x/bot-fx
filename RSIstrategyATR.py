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

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(os.path.join(os.getcwd(), "logfile.txt"))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

BOT_SIGN = "By RSI strategy"


def calculate_rsi(prices, window=14):
    delta = prices.diff()
    up = delta.copy()
    down = delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    average_gain = up.rolling(window).mean()
    average_loss = abs(down.rolling(window).mean())
    relative_strength = average_gain / average_loss
    rsi = 100.0 - (100.0 / (1.0 + relative_strength))
    return rsi


def open_order(client, trend, ask, bid, config, pair, anchor_ctm, order_histories):
    # Lấy múi giờ +0
    timezone = pytz.timezone("UTC")
    now = datetime.now(timezone)
    # open order
    res_order = client.commandExecute(
        "tradeTransaction",
        {
            "tradeTransInfo": {
                "cmd": 0 if trend == "uptrend" else 1,
                "customComment": BOT_SIGN,
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
    order_id = res_order["returnData"]["order"]
    logger.info(f"{trend} create order {pair} at {now} base on RSI {anchor_ctm}")
    requests.get(
        f'https://api.telegram.org/bot{os.getenv("TELEGRAM_BOT_TOKEN")}/sendMessage?chat_id={os.getenv("TELEGRAM_USER_ID")}&text={trend} create order {pair} base on RSI'
    )
    order_histories.insert_one(
        {
            "pair": pair.split("_")[0],
            "timeframe": int(pair.split("_")[1]),
            "ctm": anchor_ctm,
            "ctm_str": datetime.utcfromtimestamp(anchor_ctm / 1000),
            "from": BOT_SIGN,
            "order_id": order_id,
            "status": "pending",
            "open_time": int(now.timestamp() * 1000),
            "open_time_str": datetime.utcfromtimestamp(int(now.timestamp())),
        }
    )


def rsi(pair, trend):
    # nguyên tắc vào lệnh

    mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"), connectTimeoutMS=2000)
    db = mongoClient["bot_fx"]
    order_histories = db["orders"]
    histories = db[pair]
    configs = db["configs"]
    config = configs.find_one({"pair": pair})

    timezone = pytz.timezone("UTC")
    now = datetime.now(timezone)

    candles = histories.find().sort("ctm", -1).limit(1000)
    _candles = list(candles)
    _candles.reverse()
    df = pd.DataFrame(_candles)

    rsi = calculate_rsi(df["close"], window=14)
    rsi_peaks, _ = find_peaks(
        rsi, prominence=config["rsi_prominence"], distance=config["rsi_distance"]
    )
    rsi_valleys, _ = find_peaks(
        -rsi, prominence=config["rsi_prominence"], distance=config["rsi_distance"]
    )
    peaks = rsi_peaks if trend == "downtrend" else rsi_valleys
    last_peak_index = peaks[-1]
    last_peak_candle = _candles[last_peak_index]

    # check oversold or overbuy
    if trend == "downtrend":
        if rsi[last_peak_index] < 70:
            reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} rsi < 70"
            print(reason)
            configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
            return
    else:
        if rsi[last_peak_index] > 30:
            reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} rsi > 30"
            print(reason)
            configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
            return

    # Calculate True Range (TR)
    df["tr1"] = df["high"] - df["low"]
    df["tr2"] = abs(df["high"] - df["close"].shift())
    df["tr3"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
    df.drop(["tr1", "tr2", "tr3"], axis=1, inplace=True)
    # Calculate ATR
    df["atr"] = df["tr"].rolling(window=config["atr_length"]).mean()
    df["atr_min"] = df["atr"].rolling(config["atr_length"]).min()

    if df.iloc[-1]["atr_min"] > config["atr_threshold"]:
        reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} atr is too high {df.iloc[-1]['atr_min']} > {config['atr_threshold']}"
        print(reason)
        configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
        return

    # check order opened is that peak
    last_order = order_histories.find_one(
        {
            "pair": pair.split("_")[0],
            "ctm": {"$gte": last_peak_candle["ctm"]},
            "status": {"$in": ["accepted", "pending"]},
        }
    )
    if last_order is not None:
        reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} has last order at {last_order['open_time_str']}"
        print(reason)
        configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
        return

    # login to get bid, ask
    userId = os.getenv("XTB_USER_ID")
    password = os.getenv("XTB_PASSWORD")
    client = APIClient()
    client.timeout = 5
    loginResponse = client.execute(loginCommand(userId=userId, password=password))
    if loginResponse["status"] == False:
        print("Login failed. Error code: {0}".format(loginResponse["errorCode"]))
        return
    # check open too many order
    all_opened_orders = client.commandExecute("getTrades", {"openedOnly": True})
    if all_opened_orders["status"] == False:
        return
    opened_lots = 0
    for order in all_opened_orders["returnData"]:
        if (
            order["symbol"] == pair.split("_")[0].upper()
            and order["customComment"] == BOT_SIGN
        ):
            opened_lots += order["volume"]

    if config["max_lots"] - opened_lots < config["lots_size"]:
        reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} max lots"
        print(reason)
        configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
        return

    # get bid and ask price
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
            reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} buy slippage show far {round(ask - last_peak_candle['close'], config['digits'])}"
            print(reason)
            configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
            return
    elif trend == "downtrend":
        if bid < last_peak_candle["close"] - config["slippage"]:
            reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} sell slippage show far {round(last_peak_candle['close'] - bid, config['digits'])}"
            print(reason)
            configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
            return

    open_order(
        client=client,
        trend=trend,
        ask=ask,
        bid=bid,
        config=config,
        pair=pair,
        anchor_ctm=last_peak_candle["ctm"],
        order_histories=order_histories,
    )
