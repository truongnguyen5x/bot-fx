from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pandas as pd
from pymongo import MongoClient
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import find_peaks
import argparse
import numpy as np

load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]


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


def plot_candles(df, config):
    df["index"] = pd.to_datetime(df["ctm"], unit="ms")

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.6, 0.2, 0.2],
        vertical_spacing=0.01,
    )

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
            marker=dict(symbol="star", size=8, color="green"),
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
            marker=dict(symbol="star", size=8, color="red"),
            name="MACD Valleys",
        ),
        row=2,
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

    # Calculate True Range (TR)
    df["tr1"] = df["high"] - df["low"]
    df["tr2"] = abs(df["high"] - df["close"].shift())
    df["tr3"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
    df.drop(["tr1", "tr2", "tr3"], axis=1, inplace=True)

    # Calculate ATR
    df["atr"] = df["tr"].rolling(window=config["atr_length"]).mean()

    # Add ATR to the third subplot (row=3, col=1)
    # fig.add_trace(
    #     go.Scatter(
    #         x=df.index,
    #         y=df["atr"],
    #         line=dict(color="purple", width=1.5),
    #         name="ATR",
    #     ),
    #     row=3,
    #     col=1,
    # )
    # Find ATR valleys
    # atr_valleys, _ = find_peaks(
    #     -df["atr"], distance=config["atr_distance"], prominence=config["atr_prominence"]
    # )

    # atr_peaks, _ = find_peaks(
    #     df["atr"], distance=config["atr_distance"], prominence=config["atr_prominence"]
    # )
    # Plot ATR valleys as '*' symbols
    # fig.add_trace(
    #     go.Scatter(
    #         x=df.index[atr_valleys],
    #         y=df["atr"].iloc[atr_valleys],
    #         mode="markers",
    #         marker=dict(symbol="star", size=8, color="red"),
    #         name="ATR Valleys",
    #     ),
    #     row=3,
    #     col=1,
    # )
    # # Plot ATR valleys as '*' symbols
    # fig.add_trace(
    #     go.Scatter(
    #         x=df.index[atr_peaks],
    #         y=df["atr"].iloc[atr_peaks],
    #         mode="markers",
    #         marker=dict(symbol="star", size=8, color="blue"),
    #         name="ATR Valleys",
    #     ),
    #     row=3,
    #     col=1,
    # )
    # Calculate RSI
    rsi = calculate_rsi(df["close"], window=14)
    rsi_peaks, _ = find_peaks(-rsi, distance=30, prominence=20)
    rsi_valleys, _ = find_peaks(rsi, distance=30, prominence=20)
    # Add RSI to the fourth subplot (row=4, col=1)
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=rsi,
            line=dict(color="green", width=1),
            name="RSI",
        ),
        row=3,
        col=1,
    )
    # Plot RSI valleys as '*' symbols
    fig.add_trace(
        go.Scatter(
            x=df.index[rsi_peaks],
            y=rsi.iloc[rsi_peaks],
            mode="markers",
            marker=dict(symbol="star", size=8, color="red"),
            name="RSI Valleys",
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index[rsi_valleys],
            y=rsi.iloc[rsi_valleys],
            mode="markers",
            marker=dict(symbol="star", size=8, color="red"),
            name="RSI Valleys",
        ),
        row=3,
        col=1,
    )
    fig.update_layout(xaxis_rangeslider_visible=False)

    fig.update_xaxes(
        showspikes=True,
        spikecolor="red",
        spikesnap="cursor",
        spikemode="across",
        spikedash="solid",
    )

    fig.update_traces(xaxis="x1")
    # Show the figure
    fig.show()


def main():
    # create a parser object
    parser = argparse.ArgumentParser(description="Collector data candle jobs")
    parser.add_argument("timeframe", type=str, help="timeframe")
    parser.add_argument("-o", "--offset", type=int, help="offset")
    args = parser.parse_args()
    pair = args.timeframe if args.timeframe is not None else "eurusd_5"

    histories = db[pair]
    configs = db["configs"]

    config = configs.find_one({"pair": pair})

    # documents = histories.find(
    #     {
    #         "ctm": {
    #             "$gt": datetime(2023, 6, 23).timestamp() * 1000,
    #             "$lt": datetime(2023, 7, 28, 23).timestamp() * 1000,
    #         }
    #     }
    # )
    documents = (
        histories.find()
        .sort("ctm", -1)
        .skip(args.offset if args.offset is not None else 0)
        .limit(1500)
    )
    # Convert the documents to a list of dictionaries
    data = list(documents)
    data.reverse()
    # del data[-24:]
    df = pd.DataFrame(data)
    plot_candles(df, config)


if __name__ == "__main__":
    main()
