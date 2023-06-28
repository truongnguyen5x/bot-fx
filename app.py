from flask import Flask, jsonify, request
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

# Connect to your mongodb database
mongoClient = MongoClient(os.getenv("MONGO_CONNECTION"))
db = mongoClient["bot_fx"]

# Một danh sách các đối tượng dữ liệu giả
books = [
    {"id": 1, "title": "Book 1", "author": "Author 1"},
    {"id": 2, "title": "Book 2", "author": "Author 2"},
    {"id": 3, "title": "Book 3", "author": "Author 3"},
]


# Định nghĩa route cho API
@app.route("/api/books", methods=["GET"])
def get_books():
    return jsonify(books)


@app.route("/pairs", methods=["GET"])
def get_pairs():
    enabled_pairs = db.configs.find({"enabled": True})
    print(enabled_pairs)
    return "hello"


if __name__ == "__main__":
    app.run(debug=True)
