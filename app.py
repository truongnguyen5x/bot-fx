from flask import Flask, jsonify, request
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
    enabled_pairs = db.configs.find({})
    res = dumps(list(enabled_pairs))
    return res


@app.route("/pair/<pair>", methods=["POST"])
def update_pair(pair):
    data = request.get_json()
    print(data)
    timezone = pytz.timezone("UTC")
    now = datetime.now(timezone)
    data["updated_at"] = now
    db.configs.update_one({"pair": pair}, {"$set": data})

    return {"status": True}


if __name__ == "__main__":
    app.run(debug=True)
