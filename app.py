from flask import Flask, request, abort
import requests
import os

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = "S4N+uoOuISPL2gUkAFek7PGhEdgE91KSbIkp6V6ZO4M8dT9sDui+EcXmXWTr75NxLcBkGS9dKNDX6DHr+yfhAoVyTbfElLHkV9Ov1e0KzIMIf5qu+jDBxXiWvY8hv1hOQV9UDqRd9SI4Q3+8lq/uWQdB04t89/1O/w1cDnyilFU="

@app.route("/")
def home():
    return "LINE BOT RUNNING"

@app.route("/callback", methods=['POST'])
def callback():
    body = request.get_json()

    for event in body.get("events", []):
        if event["type"] == "message":
            reply_token = event["replyToken"]
            user_msg = event["message"].get("text", "")

            reply_message(reply_token, f"你說的是：{user_msg}")

    return "OK"

def reply_message(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }
    data = {
        "replyToken": reply_token,
        "messages": [
            {"type": "text", "text": text}
        ]
    }
    requests.post(url, headers=headers, json=data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
