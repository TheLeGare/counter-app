import json
import os
import queue
import sqlite3
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, render_template

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent / "counter.db"))

app = Flask(__name__)

db_lock = threading.Lock()
subscribers_lock = threading.Lock()
subscribers: list[queue.Queue] = []


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS counter ("
            "id INTEGER PRIMARY KEY CHECK (id = 1), "
            "count INTEGER NOT NULL DEFAULT 0)"
        )
        conn.execute("INSERT OR IGNORE INTO counter (id, count) VALUES (1, 0)")


def read_count() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT count FROM counter WHERE id = 1").fetchone()
    return row[0]


def broadcast(count: int) -> None:
    with subscribers_lock:
        targets = list(subscribers)
    for q in targets:
        q.put(count)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/count")
def count():
    return jsonify(count=read_count())


@app.route("/click", methods=["POST"])
def click():
    with db_lock:
        with get_conn() as conn:
            conn.execute("UPDATE counter SET count = count + 1 WHERE id = 1")
            row = conn.execute("SELECT count FROM counter WHERE id = 1").fetchone()
        new_count = row[0]
    broadcast(new_count)
    return jsonify(count=new_count)


@app.route("/stream")
def stream():
    def gen(q: queue.Queue):
        try:
            yield f"data: {json.dumps({'count': read_count()})}\n\n"
            while True:
                value = q.get()
                yield f"data: {json.dumps({'count': value})}\n\n"
        finally:
            with subscribers_lock:
                if q in subscribers:
                    subscribers.remove(q)

    client_q: queue.Queue = queue.Queue()
    with subscribers_lock:
        subscribers.append(client_q)

    resp = Response(gen(client_q), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)
