from dotenv import load_dotenv
import os
import pandas as pd
import pymongo
from pymongo import MongoClient
import logging
import os
import yfinance as yf
import argparse
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt


load_dotenv()

# Create a logger object and set its level to DEBUG
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(os.path.join(os.getcwd(), "logfile.txt"))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)


def draw_svg(pair, limit=576):
    histories = db[pair]
    rows = list(histories.find().sort("ctm", -1).limit(limit))
    rows.reverse()
    df = pd.DataFrame(rows)
    df["idx"] = df.reset_index().index + 1
    fig, ax = plt.subplots(figsize=(6, 2))
    ax.plot(df["idx"], df["close"], color="#15d90d", label=pair)
    fig.patch.set_alpha(0.0)
    ax.axis("off")
    ax.margins(0)
    ax.autoscale(tight=True)
    path = os.path.join(os.getcwd(), "static", f"{pair}.svg")
    # print(path)
    plt.savefig(
        path,
        format="svg",
        bbox_inches="tight",
        transparent=True,
    )


# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"), connectTimeoutMS=2000)
db = mongoClient["bot_fx"]


# Create a logger object and set its level to DEBUG
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(os.path.join(os.getcwd(), "logfile.txt"))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)


def symbol_label(pair):
    return pair["pair"]


def symbol_label2(symbol):
    return f'{symbol.upper().split("_")[0]}=X'


def collect(
    timeframe,
):
    configs = db["configs"]
    pairs = configs.find()
    list_pair = list(pairs)

    # TODO:
    # current_time_utc = datetime.now(timezone.utc)

    # print(current_time_utc)

    symbol = list(map(symbol_label, list_pair))
    # print(str(timeframe))
    symbol = [x for x in symbol if x.endswith(f"_{str(timeframe)}")]
    symbol2 = list(map(symbol_label2, symbol))
    # print(symbol)
    interval = f"{timeframe}m"
    data = yf.download(
        tickers=symbol2,
        # start=current_time_utc,
        period="3d",
        interval=interval,
        group_by="ticker",
    )

    # print(data)
    for i in range(len(symbol)):
        df = data[symbol2[i]]
        df.columns = ["open", "high", "low", "close", "adj close", "vol"]
        del df["adj close"]
        del df["vol"]
        df["timestamp"] = pd.to_datetime(df.index, utc=True)
        # if timeframe == 15:
        #     df["timestamp"] = df["timestamp"].apply(lambda x: x - timedelta(hours=1))
        df["ctm"] = df["timestamp"].apply(lambda x: int(x.timestamp() * 1000))
        print(df)
        histories = db[symbol[i]]
        last_candle = histories.find_one({}, sort=[("ctm", pymongo.DESCENDING)])
        # filter_df = df[df["ctm"] > 0]
        filter_df = df[df["ctm"] > last_candle["ctm"] - timeframe * 60000]
        records = filter_df.to_dict("records")

        if len(records) > 0:
            # logging.info(
            #     f"cronjob get {len(records)} {pair} candles timeframe m{timeframe}"
            # )
            for record in records:
                histories.update_one(
                    {"ctm": record["ctm"]}, {"$set": record}, upsert=True
                )
            # pass


def main():
    # create a parser object
    parser = argparse.ArgumentParser(description="Collector data candle jobs")
    parser.add_argument("-t", "--timeframe", type=int, help="timeframe")
    args = parser.parse_args()

    try:
        tf = args.timeframe if args.timeframe is not None else 5
        collect(timeframe=tf)
        try:
            configs = db["configs"]
            pairs = configs.find()
            list_pair = list(pairs)
            for pair in list_pair:
                if tf == int(pair["pair"].split("_")[1]):
                    draw_svg(pair=pair["pair"])
        except Exception as e1:
            print(e1)

    except Exception as e:
        print(e)
        mongoClient.close()
        logger.error(e)
    mongoClient.close()


if __name__ == "__main__":
    main()
