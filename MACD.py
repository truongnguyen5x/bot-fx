from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pandas as pd
from pymongo import MongoClient
import matplotlib.pyplot as plt
import mplfinance as mpf

load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]

histories = db["eurusd_15"]


def calculate_macd(df, fast_period=12, slow_period=26, signal_period=9):
    # Calculate the exponential moving averages (EMA)
    ema_fast = df["close"].ewm(span=fast_period).mean()
    ema_slow = df["close"].ewm(span=slow_period).mean()

    # Calculate the MACD line
    macd_line = ema_fast - ema_slow

    # Calculate the signal line
    signal_line = macd_line.ewm(span=signal_period).mean()

    # Calculate the MACD histogram
    macd_histogram = macd_line - signal_line

    # Add the calculated values to the DataFrame
    df["macd_line"] = macd_line
    df["signal_line"] = signal_line
    df["macd_histogram"] = macd_histogram

    return df


def plot_macd(df):
    plt.figure(figsize=(12, 6))

    # Plot MACD line
    plt.plot(df.index, df["macd_line"], label="MACD Line")

    # Plot signal line
    plt.plot(df.index, df["signal_line"], label="Signal Line")

    # Plot MACD histogram
    plt.bar(df.index, df["macd_histogram"], label="MACD Histogram", color="gray")

    # Add zero line for the histogram
    plt.axhline(0, color="black", linewidth=0.5)

    plt.xlabel("Date")
    plt.ylabel("MACD")
    plt.title("MACD Indicator")
    plt.legend()
    plt.grid(True)
    plt.show()


def plot_candles(df):
    # Convert the date index to datetime format
    df.index = pd.to_datetime(df.ctm, unit="ms")
    df["volume"] = df["vol"]

    # Create a dictionary with the required arguments for the candlestick chart
    kwargs = dict(
        type="candle", volume=True, figratio=(16, 9), title="EUR/USD Candlestick Chart"
    )

    # Plot the candlestick chart
    mpf.plot(df, **kwargs)


def main():
    documents = histories.find().sort("_id", -1).limit(250)
    # Convert the documents to a list of dictionaries

    data = list(documents)
    # Reverse the list to restore the original order
    data.reverse()
    # Create a DataFrame from the list of dictionaries
    df = pd.DataFrame(data)
    print(df)
    plot_candles(df)
    # macd = calculate_macd(df)
    # plot_macd(macd)


if __name__ == "__main__":
    main()
