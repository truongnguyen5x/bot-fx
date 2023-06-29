from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pandas as pd
from pymongo import MongoClient
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import find_peaks

load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]
pair = "audusd_5"
histories = db[pair]
configs = db["configs"]

config = configs.find_one({"pair": pair})


def plot_candles(df):
    df["index"] = pd.to_datetime(df["ctm"], unit="ms")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True)

    # Add a candlestick trace to the first subplot (row=1, col=1)
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Candlestick",
        ),
        row=1,
        col=1,
    )

    # Calculate MACD and signal lines
    ema_12 = df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9, adjust=False).mean()

    # Find peaks and valleys of the MACD line
    macd_peaks, _ = find_peaks(
        macd, prominence=config["macd_prominence"], distance=config["macd_distance"]
    )
    macd_valleys, _ = find_peaks(
        -macd, prominence=config["macd_prominence"], distance=config["macd_distance"]
    )

    # Plot MACD peaks as '*' symbols
    fig.add_trace(
        go.Scatter(
            x=df.index[macd_peaks],
            y=macd.iloc[macd_peaks],
            mode="markers",
            marker=dict(symbol="star", size=8, color="red"),
            name="MACD Peaks",
        ),
        row=2,
        col=1,
    )

    # Plot MACD valleys as '*' symbols
    fig.add_trace(
        go.Scatter(
            x=df.index[macd_valleys],
            y=macd.iloc[macd_valleys],
            mode="markers",
            marker=dict(symbol="star", size=8, color="green"),
            name="MACD Valleys",
        ),
        row=2,
        col=1,
    )

    # Plot MACD peaks as '*' symbols on the candlestick chart
    fig.add_trace(
        go.Scatter(
            x=df.index[macd_peaks],
            y=df["high"].iloc[macd_peaks],
            mode="markers",
            marker=dict(symbol="star", size=8, color="black"),
            name="MACD Peaks",
        ),
        row=1,
        col=1,
    )

    # Plot MACD valleys as '*' symbols on the candlestick chart
    fig.add_trace(
        go.Scatter(
            x=df.index[macd_valleys],
            y=df["low"].iloc[macd_valleys],
            mode="markers",
            marker=dict(symbol="star", size=8, color="black"),
            name="MACD Valleys",
        ),
        row=1,
        col=1,
    )

    # Add MACD and signal lines to the second subplot (row=2, col=1)
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=macd,
            line=dict(color="blue", width=1.5),
            name="MACD",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=signal,
            line=dict(color="orange", width=1.5),
            name="Signal",
        ),
        row=2,
        col=1,
    )
    fig.add_bar(x=df.index, y=macd - signal, name="Histogram", row=2, col=1)

    # Show the figure
    fig.show()


def main():
    documents = histories.find(
        {
            "ctm": {
                "$gt": datetime(2023, 6, 23).timestamp() * 1000,
                "$lt": datetime(2023, 7, 28, 23).timestamp() * 1000,
            }
        }
    )
    # documents = histories.find().sort("_id", -1).limit(1000)
    # Convert the documents to a list of dictionaries
    data = list(documents)
    # data.reverse()
    # del data[-24:]
    df = pd.DataFrame(data)
    plot_candles(df)


if __name__ == "__main__":
    main()
