from flask import Flask, jsonify, request
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from bson.json_util import dumps

load_dotenv()

app = Flask(__name__)

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]


@app.route("/pairs", methods=["GET"])
def get_pairs():
    enabled_pairs = db.configs.find({"enabled": True})
    res = dumps(list(enabled_pairs))
    return res


@app.route("/pair/<pair>", methods=["POST"])
def update_pair(pair):
    data = request.get_json()
    db.configs.update_one({"pair": pair}, {"$set": data})

    return "update pair success"


if __name__ == "__main__":
    app.run(debug=True)
