from flask import Flask, jsonify, request

app = Flask(__name__)

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


if __name__ == "__main__":
    app.run(debug=True)
