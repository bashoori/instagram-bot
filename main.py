# =====================================================
# Meta Lead Bot (Flask)
# Author: Bita Ashoori
# Description:
# - Works for both Instagram and Messenger
# - Auto-reply about the Digital Franchise system
# - Collects name and email
# - Saves leads to Google Sheet (via Apps Script)
# - In-memory conversation state (expires after 10 minutes)
# =====================================================

import os
import re
import time
import threading
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from utils.google_sheet import save_to_google_sheet

# ----------------------------
# config
# ----------------------------
load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")  # used for both IG & FB
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID")
PORT = int(os.getenv("PORT", 5000))
GRAPH_API = "https://graph.facebook.com/v17.0"

# state expires after 10 minutes
STATE_TTL = 10 * 60

app = Flask(__name__)

# conversation memory
user_state = {}
_state_lock = threading.Lock()

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def now_ts(): return int(time.time())
def is_valid_email(e): return bool(EMAIL_REGEX.match(e or ""))


# ----------------------------
# state management
# ----------------------------
def set_state(uid, data):
    with _state_lock:
        data["ts"] = now_ts()
        user_state[uid] = data

def get_state(uid):
    with _state_lock:
        return user_state.get(uid)

def clear_state(uid):
    with _state_lock:
        if uid in user_state:
            del user_state[uid]

def cleanup_states():
    while True:
        time.sleep(60)
        cutoff = now_ts() - STATE_TTL
        with _state_lock:
            expired = [u for u, s in user_state.items() if s.get("ts", 0) < cutoff]
            for u in expired:
                del user_state[u]
        if expired:
            print(f"🧹 Cleared expired sessions: {expired}")

threading.Thread(target=cleanup_states, daemon=True).start()

# ----------------------------
# messaging helpers
# ----------------------------
def send_text(user_id, text, platform="instagram"):
    """Send message via correct API endpoint (IG or Messenger)."""
    if platform == "instagram":
        url = f"{GRAPH_API}/{IG_ACCOUNT_ID}/messages"
        payload = {
            "messaging_product": "instagram",
            "recipient": {"id": user_id},
            "message": {"text": text}
        }
    else:
        url = f"{GRAPH_API}/me/messages"
        payload = {
            "recipient": {"id": user_id},
            "message": {"text": text}
        }

    try:
        r = requests.post(url, params={"access_token": PAGE_ACCESS_TOKEN}, json=payload, timeout=8)
        print(f"➡️ Sent ({platform}) → {user_id}: {text} | status={r.status_code}")
        return r.status_code
    except Exception as e:
        print("❌ send_text error:", e)
        return None


# ----------------------------
# conversation logic
# ----------------------------
def start_pitch(user_id, platform):
    intro = (
        "سلام! 👋 خوش اومدی 🌿\n\n"
        "ما یه سیستم آموزش و «فرانچایز دیجیتال مارکتینگ» داریم که کمک می‌کنه بیزنس آنلاین خودت رو بسازی "
        "و از ابزارهای آماده برای رشد سریع‌تر استفاده کنی.\n\n"
        "لطفاً برای شروع، اسم خودت رو بفرست 🌱"
    )
    send_text(user_id, intro, platform)
    set_state(user_id, {"state": "expecting_name", "platform": platform})


def ask_email(user_id, name, platform):
    send_text(user_id, f"عالی {name} 🙌 حالا لطفاً ایمیلت رو بنویس:", platform)
    set_state(user_id, {"state": "expecting_email", "name": name, "platform": platform})


def finish(user_id, name, email, platform):
    try:
        save_to_google_sheet(user_id, name, email)
    except Exception as e:
        print("❌ save error:", e)

    send_text(user_id, f"✅ {name} عزیز، اطلاعاتت ثبت شد و تیم ما به زودی باهات تماس می‌گیره 💬", platform)
    send_text(user_id, "اگه سوال دیگه‌ای داری بنویس «راهنما» یا پیام بده ✨", platform)
    clear_state(user_id)


def handle_message(uid, text, platform):
    text = text.strip()
    state = get_state(uid)
    current = state["state"] if state else None

    if not state:
        start_pitch(uid, platform)
        return

    if current == "expecting_name":
        ask_email(uid, text, platform)
        return

    if current == "expecting_email":
        if not is_valid_email(text):
            send_text(uid, "ایمیل معتبر نیست، لطفاً دوباره وارد کن (مثلاً name@example.com).", platform)
            set_state(uid, {"state": "expecting_email", "name": state.get("name"), "platform": platform})
            return
        finish(uid, state.get("name", ""), text, platform)
        return

    send_text(uid, "برای شروع بنویس «شروع» یا «سلام» 🌱", platform)


# ----------------------------
# webhook verification
# ----------------------------
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verified.")
        return challenge, 200
    return "Verification failed", 403


# ----------------------------
# webhook receiver (IG + Messenger)
# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    print("📩 Webhook received:", data)
    if not data:
        return "no data", 400

    try:
        for entry in data.get("entry", []):
            # Messenger
            for msg in entry.get("messaging", []):
                sender_id = msg.get("sender", {}).get("id")
                text = msg.get("message", {}).get("text", "")
                if sender_id and text:
                    handle_message(sender_id, text, "messenger")

            # Instagram
            for change in entry.get("changes", []):
                value = change.get("value", {})
                sender_id = value.get("from", {}).get("id")
                text = value.get("message", {}).get("text", "") if "message" in value else value.get("text", "")
                if sender_id and text:
                    handle_message(sender_id, text, "instagram")

    except Exception as e:
        print("⚠️ Webhook error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

    return "ok", 200


# ----------------------------
# run
# ----------------------------
if __name__ == "__main__":
    print(f"🚀 Starting Meta Lead Bot on port {PORT} ...")
    app.run(host="0.0.0.0", port=PORT)
