from flask import Flask, jsonify, request, make_response
from pymongo import MongoClient
from dotenv import load_dotenv
from flask_cors import CORS, cross_origin
import os
from datetime import datetime, time, timedelta

import pytz
from bson.json_util import dumps

load_dotenv()

app = Flask(__name__)
CORS(app)

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]


@app.route("/pairs", methods=["GET"])
def get_pairs():
    enabled_pairs = db.configs.find({}).sort("created_at", 1)
    res = dumps(list(enabled_pairs))
    return res


def get_close(x):
    return x["close"]


@app.route("/pairs-histories", methods=["GET"])
def get_pairs_history():
    limit = int(request.args.get("limit") or "576")
    res = []
    enabled_pairs = db.configs.find({}).sort("created_at", 1)
    for p in enabled_pairs:
        candles = db[p["pair"]].find().sort("ctm", -1).limit(limit)
        _candles = list(candles)
        # _candles = _candles[::-8]
        _candles.reverse()
        res.append(list(map(get_close, _candles)))
    return dumps(res)


@app.route("/pair/<pair>", methods=["POST"])
def update_pair(pair):
    data = request.get_json()

    # timezone = pytz.timezone("UTC")
    # now = datetime.now(timezone)
    # data["updated_at"] = now
    db.configs.update_one({"pair": pair}, {"$set": data})

    return {"status": True}


if __name__ == "__main__":
    app.run(debug=True)
