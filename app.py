from flask import Flask, request, abort

app = Flask(__name__)

@app.route("/")
def home():
    return "LINE BOT RUNNING"

@app.route("/callback", methods=['POST'])
def callback():
    body = request.get_data(as_text=True)
    print(body)
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
