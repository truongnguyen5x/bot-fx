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

BOT_SIGN = "By MACD strategy"


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
    logger.info(f"{trend} create order {pair} at {now} base on MACD {anchor_ctm}")
    requests.get(
        f'https://api.telegram.org/bot{os.getenv("TELEGRAM_BOT_TOKEN")}/sendMessage?chat_id={os.getenv("TELEGRAM_USER_ID")}&text={trend} create order {pair} base on MACD'
    )
    order_histories.insert_one(
        {
            "pair": pair.split("_")[0],
            "timeframe": int(pair.split("_")[1]),
            "ctm": anchor_ctm,
            "ctm_str": datetime.utcfromtimestamp(anchor_ctm / 1000),
            "from": "MACD strategy",
            "order_id": order_id,
            "status": "pending",
            "open_time": int(now.timestamp() * 1000),
            "open_time_str": datetime.utcfromtimestamp(int(now.timestamp())),
        }
    )


def macd(pair, trend):
    mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"), connectTimeoutMS=2000)
    db = mongoClient["bot_fx"]
    order_histories = db["orders"]
    histories = db[pair]
    configs = db["configs"]
    config = configs.find_one({"pair": pair})

    # check session EU, US
    # Lấy múi giờ +0
    timezone = pytz.timezone("UTC")
    now = datetime.now(timezone)
    # in_session = None
    # start_session = datetime.now(timezone)

    # for session in config["sessions"]:
    #     # Chuyển đổi chuỗi thành đối tượng time
    #     start_str, end_str = session.split("-")
    #     start_time = time.fromisoformat(start_str)
    #     end_time = time.fromisoformat(end_str)
    #     start_session = start_session.replace(
    #         hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0
    #     )
    #     # Lấy múi giờ +0 (UTC+0)
    #     current_time = now.time()
    #     # Kiểm tra xem thời gian hiện tại có nằm trong khoảng thời gian hay không
    #     if start_time <= end_time:
    #         if start_time <= current_time <= end_time:
    #             in_session = True
    #             break
    #     else:
    #         if start_time <= current_time:
    #             in_session = True
    #             break
    #         if current_time <= end_time:
    #             in_session = True
    #             start_session = start_session - timedelta(days=1)
    #             break
    # if in_session is None:
    #     reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} not in session"
    #     print(reason)
    #     configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
    #     return

    candles = histories.find().sort("ctm", -1).limit(1000)
    _candles = list(candles)
    _candles.reverse()
    df = pd.DataFrame(_candles)

    # Calculate MACD and signal lines
    ema_12 = df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    # Find peaks and valleys of the MACD line
    macd_peaks, _ = find_peaks(
        macd, prominence=config["macd_prominence"], distance=config["macd_distance"]
    )
    macd_valleys, _ = find_peaks(
        -macd, prominence=config["macd_prominence"], distance=config["macd_distance"]
    )
    peaks = macd_peaks if trend == "downtrend" else macd_valleys
    # valleys = macd_valleys if trend == "downtrend" else macd_peaks
    last_peak_index = peaks[-1]
    last_peak_candle = _candles[last_peak_index]
    # last_peak_time = datetime.fromtimestamp(last_peak_candle["ctm"] / 1000, tz=timezone)
    # if last_peak_time < start_session:
    #     reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} last peak not in session {last_peak_time} {start_session}"
    #     print(reason)
    #     configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
    #     return
    # if last_peak_index < valleys[-1]:
    #     reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} last peak so far {last_peak_index} < {valleys[-1]}"
    #     print(reason)
    #     configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
    #     return

    # Calculate True Range (TR)
    df["tr1"] = df["high"] - df["low"]
    df["tr2"] = abs(df["high"] - df["close"].shift())
    df["tr3"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
    df.drop(["tr1", "tr2", "tr3"], axis=1, inplace=True)
    # Calculate ATR
    df["atr"] = df["tr"].rolling(window=config["atr_length"]).mean()
    df["atr_min"] = df["atr"].rolling(config["atr_length"]).min()
    # Find ATR valleys
    # atr_valleys, _ = find_peaks(
    #     -df["atr"], distance=config["atr_distance"], prominence=config["atr_prominence"]
    # )
    # atr_peaks, _ = find_peaks(
    #     df["atr"], distance=config["atr_distance"], prominence=config["atr_prominence"]
    # )
    # last_atr_peak = atr_peaks[-1]
    # last_atr_valley = atr_valleys[-1]
    # if last_atr_peak > last_atr_valley:
    #     print(f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} atr is slow down")
    #     return

    if df.iloc[-1]["atr_min"] > config["atr_threshold"]:
        reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} atr is too high {df.iloc[-1]['atr_min']} > {config['atr_threshold']}"
        print(reason)
        configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
        return

    # check order opened is that peak
    # last_order = order_histories.find_one(
    #     {
    #         "pair": pair.split("_")[0],
    #         "ctm": {"$gte": last_peak_candle["ctm"]},
    #         "status": {"$in": ["accepted", "pending"]},
    #     }
    # )
    # if last_order is not None:
    #     reason = f"[{now.strftime('%d-%m-%Y %H:%M:%S')}] {pair} has last order at {last_order['open_time_str']}"
    #     print(reason)
    #     configs.update_one({"pair": pair}, {"$set": {"reason": reason}})
    #     return

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
