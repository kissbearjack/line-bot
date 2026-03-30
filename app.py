from flask import Flask, request
import requests
import os
import json
import re
from openai import OpenAI

app = Flask(__name__)

# =========================
# ENV
# =========================
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("❌ LINE_CHANNEL_ACCESS_TOKEN 沒有設定")

if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY 沒有設定")

client = OpenAI(api_key=OPENAI_API_KEY)


# =========================
# 工具（沿用 voice_order.py 思路）
# =========================
def ensure_str(x):
    if x is None:
        return ""
    return str(x).strip()


def format_member_block(text):
    return ensure_str(text)


def format_phone_plain(phone):
    digits = re.sub(r"\D", "", ensure_str(phone))
    if len(digits) == 10:
        return digits
    return ensure_str(phone)


def format_car_no(car_no):
    text = ensure_str(car_no).upper().replace(" ", "")
    text = text.replace("—", "-").replace("－", "-")
    return text


def ensure_fields(data):
    fields = [
        "預約日期", "預約時間", "航班編號", "服務類型", "會員姓名",
        "成人數", "加點次數", "車型", "地址", "航站",
        "司機", "車號", "司機行動電話", "車商備註",
        "請準備安全座椅", "收現金", "機代費", "外派價"
    ]
    for f in fields:
        if f not in data:
            data[f] = ""
    return data


def speech_to_text(file_path):
    with open(file_path, "rb") as audio_file:
        res = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file,
            language="zh"
        )
    return res.text


def parse_with_gpt(text):
    response = client.chat.completions.create(
        model="gpt-4.1",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": """
你是台灣機場接送訂單解析器。

1. 只能輸出 JSON
2. 必須輸出完整18欄
3. 沒資料填 "" 或 0
4. 不要解釋

【地址辨識規則（強制）】
- 只要內容包含以下任一關鍵字，就一定是地址：
  縣、市、區、鄉、鎮、里、路、街、段、巷、弄、號
- 地址必須完整保留，不可刪字
- 地址不得改寫、不得簡化
- 地址不得拆錯

【地址輸出格式（強制）】
- 多筆地址請用：
1地址A
2地址B
3地址C
- 編號必須連續，不可跳號

【禁止錯誤】
- 不可把地址誤當備註
- 不可把地址截斷
- 不可合併不同地址
"""
            },
            {
                "role": "user",
                "content": f"""
逐字稿：
{text}

注意：
只要是地址，一定完整輸出，不可漏掉任何一筆

輸出：

{{
  "預約日期": "",
  "預約時間": "",
  "航班編號": "",
  "服務類型": "",
  "會員姓名": "",
  "成人數": "",
  "加點次數": "",
  "車型": "",
  "地址": "",
  "航站": "",
  "司機": "",
  "車號": "",
  "司機行動電話": "",
  "車商備註": "",
  "請準備安全座椅": "",
  "收現金": "",
  "機代費": "",
  "外派價": ""
}}
"""
            }
        ]
    )

    return json.loads(response.choices[0].message.content)


def force_split_address(text):
    text = ensure_str(text)

    # 強制把 1地址 2地址 拆開
    text = re.sub(r'(\d+)(?=[^\d])', r'\n\1', text)

    return text.strip()


def normalize_inline_multivalue(text):
    text = ensure_str(text)
    text = text.replace("\r", "\n")
    lines = [x.strip() for x in text.split("\n") if x.strip()]
    return " ｜ ".join(lines)


def safe_plain_field(text):
    text = ensure_str(text)
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_reply_text(transcript, data):
    data = ensure_fields(data)

    # 格式整理
    data["車號"] = format_car_no(data["車號"])
    data["司機行動電話"] = format_phone_plain(data["司機行動電話"])

    # 🔥 多行 → 單行（關鍵）
    member_raw = force_split_address(data["會員姓名"])
    member_name = normalize_inline_multivalue(member_raw)
    address_raw = force_split_address(data["地址"])
    address = normalize_inline_multivalue(address_raw)
    note_raw = force_split_address(data["車商備註"])
    note = normalize_inline_multivalue(note_raw)

    row = [
        safe_plain_field(data["預約日期"]),
        safe_plain_field(data["預約時間"]),
        safe_plain_field(data["航班編號"]),
        safe_plain_field(data["服務類型"]),
        member_name,
        safe_plain_field(data["成人數"]),
        safe_plain_field(data["加點次數"]),
        safe_plain_field(data["車型"]),
        address,
        safe_plain_field(data["航站"]),
        safe_plain_field(data["司機"]),
        safe_plain_field(data["車號"]),
        safe_plain_field(data["司機行動電話"]),
        note,
        safe_plain_field(data["請準備安全座椅"]),
        safe_plain_field(data["收現金"]),
        safe_plain_field(data["機代費"]),
        safe_plain_field(data["外派價"]),
    ]

    excel_line = "\t".join(row)

    if len(excel_line) > 4500:
        excel_line = excel_line[:4500] + " ...(內容過長已截斷)"

    return excel_line


# =========================
# 首頁
# =========================
@app.route("/")
def home():
    return "LINE BOT RUNNING"


# =========================
# callback
# =========================
@app.route("/callback", methods=['POST'])
def callback():
    try:
        body = request.get_json(force=True)
        print("收到 webhook:", body)

        for event in body.get("events", []):
            if event.get("type") != "message":
                continue

            reply_token = event.get("replyToken")
            message = event.get("message", {})
            message_type = message.get("type")

            # ========= 文字訊息 =========
            if message_type == "text":
                user_msg = message.get("text", "")
                reply_message(reply_token, f"你說的是：{user_msg}")

            # ========= 語音訊息 =========
            elif message_type == "audio":
                handle_audio_message(reply_token, message)

        return "OK"

    except Exception as e:
        print("callback error:", str(e))
        return "ERROR", 500


# =========================
# 語音處理
# =========================
def handle_audio_message(reply_token, message):
    temp_path = "temp.m4a"

    try:
        message_id = message.get("id")
        if not message_id:
            reply_message(reply_token, "❌ 取得語音訊息 ID 失敗")
            return

        # 1. 下載語音
        audio_url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
        headers = {
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
        }

        r = requests.get(audio_url, headers=headers, timeout=60)
        r.raise_for_status()

        with open(temp_path, "wb") as f:
            f.write(r.content)

        # 2. 語音轉文字
        transcript = speech_to_text(temp_path)
        print("逐字稿:", transcript)

        # 3. GPT 解析
        data = parse_with_gpt(transcript)
        print("GPT解析:", data)

        # 4. 組合回覆
        reply_text = build_reply_text(transcript, data)

        # 5. 回覆
        reply_message(reply_token, reply_text)

    except Exception as e:
        print("audio error:", str(e))
        reply_message(reply_token, f"❌ 語音處理失敗：{str(e)}")

    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


# =========================
# 回覆 LINE
# =========================
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

    r = requests.post(url, headers=headers, json=data, timeout=30)
    print("reply status:", r.status_code, r.text)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
