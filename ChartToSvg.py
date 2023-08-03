import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import pymongo
import os
from pymongo import MongoClient

load_dotenv()

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"), connectTimeoutMS=2000)
db = mongoClient["bot_fx"]
histories = db["eurusd_5"]


def main():
    rows = list(histories.find().sort("ctm", -1).limit(432))
    eurusd_df = pd.DataFrame(rows)

    # Create a transparent background figure
    fig, ax = plt.subplots(figsize=(6, 2))
    ax.plot(eurusd_df["timestamp"], eurusd_df["close"], color="#15d90d", label="EURUSD")

    # Set the background color to None for transparency
    fig.patch.set_alpha(0.0)

    # Remove chart borders and ticks
    ax.axis("off")

    # Remove the whitespace around the plot
    ax.margins(0)
    ax.autoscale(tight=True)

    # Save the plot as an SVG image with transparent background
    plt.savefig(
        os.getcwd() + "\images\eurusd_chart.svg",
        format="svg",
        bbox_inches="tight",
        transparent=True,
    )


if __name__ == "__main__":
    main()
