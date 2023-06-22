from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pandas as pd
from pymongo import MongoClient
import matplotlib.pyplot as plt
import mplfinance as mpf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ta

load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]

histories = db["eurusd_15"]


def plot_candles(df):
    df["index"] = pd.to_datetime(df["ctm"], unit="ms")
    # Create a figure with two subplots (rows=2, cols=1) and shared x-axis (shared_xaxes=True)
    # Assuming your dataframe is called df and has columns named 'Open', 'High', 'Low', 'Close'
    # You can change the column names as needed

    # Calculate the ADX indicator using the ta library
    adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14)
    df["ADX"] = adx.adx()
    df["+DI"] = adx.adx_pos()
    df["-DI"] = adx.adx_neg()

    # Create a figure with three subplots (rows=3, cols=1) and shared x-axis (shared_xaxes=True)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True)

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

    # Add an ADX indicator trace to the third subplot (row=3, col=1)
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df["ADX"], line=dict(color="black", width=1.5), name="ADX"
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df["+DI"], line=dict(color="green", width=1.5), name="+DI"
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df["-DI"], line=dict(color="red", width=1.5), name="-DI"
        ),
        row=3,
        col=1,
    )

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
