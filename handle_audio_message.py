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

        # 4. 組合回覆（Excel TAB格式）
        reply_text = build_reply_text(transcript, data)

        # 5. 產生 txt（覆蓋）
        file_path = "order.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(reply_text)

        # 6. 回覆下載連結（取代原本回文字）
        download_url = "https://你的render網址.onrender.com/download"
        reply_message(reply_token, f"下載訂單：\n{download_url}")

    except Exception as e:
        print("audio error:", str(e))
        reply_message(reply_token, f"❌ 語音處理失敗：{str(e)}")

    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
