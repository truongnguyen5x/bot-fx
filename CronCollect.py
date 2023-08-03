from dotenv import load_dotenv
import os
import pandas as pd
import pymongo
from pymongo import MongoClient
import logging
import os
from xAPIConnector import APIClient, loginCommand
import matplotlib.pyplot as plt
import argparse

load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"), connectTimeoutMS=2000)
db = mongoClient["bot_fx"]


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
    print(path)
    plt.savefig(
        path,
        format="svg",
        bbox_inches="tight",
        transparent=True,
    )


def collect(pair, client, timeframe):
    histories = db[pair]

    last_candle = histories.find_one({}, sort=[("ctm", pymongo.DESCENDING)])

    symbol = pair.split("_")[0]
    res = client.commandExecute(
        "getChartLastRequest",
        {
            "info": {
                "period": timeframe,
                "start": last_candle["ctm"] - timeframe * 60000,
                "symbol": symbol.upper(),
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
        print(pair)
        print(df)

        if len(records) > 0:
            # logging.info(
            #     f"cronjob get {len(records)} {pair} candles timeframe m{timeframe}"
            # )
            for record in records:
                histories.update_one(
                    {"ctm": record["ctm"]}, {"$set": record}, upsert=True
                )


def main():
    # create a parser object
    parser = argparse.ArgumentParser(description="Collector data candle jobs")
    parser.add_argument("-t", "--timeframe", type=int, help="timeframe")
    args = parser.parse_args()

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
        pairs = configs.find()
        tf = args.timeframe if args.timeframe is not None else 5
        list_pair = list(pairs)
        for pair in list_pair:
            if tf == int(pair["pair"].split("_")[1]):
                collect(
                    pair=pair["pair"],
                    client=client,
                    timeframe=tf,
                )

        for pair in list_pair:
            if tf == int(pair["pair"].split("_")[1]):
                draw_svg(pair=pair["pair"])
    except Exception as e:
        print(e)
        mongoClient.close()
    mongoClient.close()


if __name__ == "__main__":
    main()
