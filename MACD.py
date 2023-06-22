from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pandas as pd
from pymongo import MongoClient
import matplotlib.pyplot as plt
import mplfinance as mpf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]

histories = db["eurusd_15"]


def plot_candles(df):
    df["index"] = pd.to_datetime(df["ctm"], unit="ms")
    # Create a figure with two subplots (rows=2, cols=1) and shared x-axis (shared_xaxes=True)
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

    # Add a MACD indicator trace to the second subplot (row=2, col=1)
    # You can use the same code as before to calculate the MACD and signal lines
    ema_12 = df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9, adjust=False).mean()
    fig.add_trace(
        go.Scatter(x=df.index, y=macd, line=dict(color="blue", width=1.5), name="MACD"),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=signal, line=dict(color="orange", width=1.5), name="Signal"
        ),
        row=2,
        col=1,
    )
    fig.add_bar(x=df.index, y=macd - signal, name="Histogram", row=2, col=1)

    # Show the figure
    fig.show()


def main():
    documents = histories.find().sort("_id", -1).limit(1000)
    # Convert the documents to a list of dictionaries

    data = list(documents)
    # Reverse the list to restore the original order
    data.reverse()
    # Create a DataFrame from the list of dictionaries
    df = pd.DataFrame(data)

    plot_candles(df)
    # macd = calculate_macd(df)
    # plot_macd(macd)


if __name__ == "__main__":
    main()
