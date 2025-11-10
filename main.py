# =====================================================
# Instagram Bot (Flask)
# Author: Bita Ashoori
# Description:
# Simple Instagram Chatbot that collects name and email,
# stores in Google Sheets, and shows a 4-button menu.
# =====================================================

import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from utils.google_sheet import save_to_google_sheet

# --- Load environment variables ---
load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID")
PORT = int(os.getenv("PORT", 5000))

GRAPH_API = "https://graph.facebook.com/v17.0"

app = Flask(__name__)

# --- Simple state memory (for prototype only) ---
user_state = {}  # {user_id: {"state": "expecting_name"/"expecting_email", "name": "..." }}

# ---------------------------------------------------
# VERIFY WEBHOOK (for Meta setup)
# ---------------------------------------------------
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verified successfully.")
        return challenge, 200
    else:
        print("❌ Verification failed.")
        return "Verification failed", 403


# ---------------------------------------------------
# RECEIVE MESSAGES
# ---------------------------------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📩 Incoming message:", data)

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                message = value.get("message", {})
                sender_id = message.get("from", {}).get("id") or value.get("from", {}).get("id")
                text = (message.get("text") or "").strip() if "text" in message else None

                if not sender_id:
                    continue

                # --- Handle conversation states ---
                state = user_state.get(sender_id, {}).get("state")

                if state == "expecting_name":
                    user_state[sender_id]["name"] = text
                    user_state[sender_id]["state"] = "expecting_email"
                    send_text(sender_id, "متشکرم! حالا لطفاً ایمیل خود را وارد کنید:")
                    continue

                elif state == "expecting_email":
                    user_state[sender_id]["email"] = text
                    name = user_state[sender_id]["name"]
                    email = user_state[sender_id]["email"]
                    save_to_google_sheet(sender_id, name, email)
                    send_text(sender_id, "✅ اطلاعات شما با موفقیت ثبت شد!\n\nاز منوی زیر گزینه‌ی دیگری را انتخاب کنید:")
                    user_state[sender_id]["state"] = "done"
                    show_menu(sender_id)
                    continue

                # --- Handle main menu commands ---
                if text in ["شروع", "start", "شروع 🏁"]:
                    send_text(sender_id, "سلام 👋 به ربات دیجیتال مارکتینگ خوش آمدید!\nاز منوی زیر انتخاب کنید:")
                    show_menu(sender_id)

                elif text in ["درباره ما", "📘 درباره ما"]:
                    send_text(sender_id, "📘 درباره ما:\nما آموزش و راه‌اندازی بیزنس آنلاین، اتوماسیون و دیجیتال مارکتینگ را برای همه ساده کرده‌ایم.\nبا ما یاد بگیرید چطور برند خودتان را بسازید و درآمد آنلاین کسب کنید.")
                    send_text(sender_id, "برای رزرو جلسه یا ثبت‌نام از منوی زیر انتخاب کنید:")
                    show_menu(sender_id)

                elif text in ["رزرو جلسه", "📅 رزرو جلسه"]:
                    send_text(sender_id, "📅 برای رزرو جلسه لطفاً وارد این لینک شوید:\nhttps://calendly.com/your-link\nیا از منوی زیر گزینه‌ی دیگری را انتخاب کنید.")
                    show_menu(sender_id)

                elif text in ["ثبت‌نام", "📝 ثبت‌نام"]:
                    send_text(sender_id, "📝 لطفاً نام خود را وارد کنید:")
                    user_state[sender_id] = {"state": "expecting_name"}

                else:
                    send_text(sender_id, "من متوجه نشدم، لطفاً یکی از گزینه‌های منو را انتخاب کنید 👇")
                    show_menu(sender_id)

    except Exception as e:
        print("⚠️ Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

    return "ok", 200


# ---------------------------------------------------
# SEND MESSAGE HELPERS
# ---------------------------------------------------
def send_text(recipient_id, text):
    """Send a simple text message"""
    url = f"{GRAPH_API}/{IG_ACCOUNT_ID}/messages"
    payload = {
        "messaging_product": "instagram",
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}
    r = requests.post(url, json=payload, params=params)
    print("➡️ Sent:", text, "| status:", r.status_code)
    return r.status_code


def show_menu(recipient_id):
    """Send main menu as Quick Replies"""
    url = f"{GRAPH_API}/{IG_ACCOUNT_ID}/messages"
    payload = {
        "messaging_product": "instagram",
        "recipient": {"id": recipient_id},
        "message": {
            "text": "منوی اصلی 👇",
            "quick_replies": [
                {"content_type": "text", "title": "شروع 🏁", "payload": "START"},
                {"content_type": "text", "title": "درباره ما 📘", "payload": "ABOUT"},
                {"content_type": "text", "title": "ثبت‌نام 📝", "payload": "REGISTER"},
                {"content_type": "text", "title": "رزرو جلسه 📅", "payload": "BOOK"}
            ]
        }
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}
    requests.post(url, json=payload, params=params)


# ---------------------------------------------------
# START SERVER
# ---------------------------------------------------
if __name__ == "__main__":
    print(f"🚀 Starting Instagram Bot on port {PORT} ...")
    app.run(host="0.0.0.0", port=PORT)
