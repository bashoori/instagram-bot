# =====================================================
# Instagram Bot (Flask) - Simple Lead Collector (Persian)
# Author: Bita Ashoori (adapted)
# Description:
# - Auto-reply about the franchise system on any incoming DM
# - Ask for name, then email
# - Save name/email to Google Sheet via Apps Script
# - Simple in-memory state with expiry (10 minutes)
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
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID")
PORT = int(os.getenv("PORT", 5000))
GRAPH_API = "https://graph.facebook.com/v17.0"

# conversation expiry (seconds)
STATE_TTL = 10 * 60  # 10 minutes

app = Flask(__name__)

# user_state: {user_id: {"state": "...", "name": "...", "ts": unix_timestamp}}
user_state = {}
_state_lock = threading.Lock()

# ----------------------------
# helper utils
# ----------------------------
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def is_valid_email(e):
    return bool(EMAIL_REGEX.match(e or ""))

def now_ts():
    return int(time.time())

def set_state(user_id, state_dict):
    with _state_lock:
        state_dict["ts"] = now_ts()
        user_state[user_id] = state_dict

def clear_state(user_id):
    with _state_lock:
        if user_id in user_state:
            del user_state[user_id]

def get_state(user_id):
    with _state_lock:
        return user_state.get(user_id)

# background cleaner
def _cleanup_loop():
    while True:
        time.sleep(60)
        cutoff = now_ts() - STATE_TTL
        removed = []
        with _state_lock:
            for uid, s in list(user_state.items()):
                if s.get("ts", 0) < cutoff:
                    removed.append(uid)
                    del user_state[uid]
        if removed:
            print(f"🧹 Cleared expired states: {removed}")

_cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
_cleanup_thread.start()

# ----------------------------
# messaging helpers
# ----------------------------
def send_text(recipient_id, text):
    url = f"{GRAPH_API}/{IG_ACCOUNT_ID}/messages"
    payload = {
        "messaging_product": "instagram",
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}
    try:
        r = requests.post(url, json=payload, params=params, timeout=8)
        print(f"➡️ Sent to {recipient_id}: {text} | status: {r.status_code}")
        return r.status_code, r.text
    except Exception as e:
        print("❌ send_text error:", e)
        return None, str(e)

def send_welcome_and_ask_name(recipient_id):
    pitch = (
        "سلام! ممنون از پیام شما 🙏\n\n"
        "ما یک سیستم آموزشی و «فرانچایز دیجیتال مارکتینگ» داریم که به افراد و کسب‌وکارها کمک می‌کند "
        "تا با آموزش گام‌به‌گام و ابزارهای آماده، کسب‌وکار آنلاین خودشون رو راه‌اندازی و مقیاس کنن.\n\n"
        "اگر دوست داری توضیحات کامل و لینک‌های مربوطه رو برات بفرستم، لطفاً اول نام خودت رو بفرست."
    )
    send_text(recipient_id, pitch)
    set_state(recipient_id, {"state": "expecting_name"})

def ask_for_email(recipient_id, name):
    send_text(recipient_id, f"خیلی عالی {name} 🙌\nحالا لطفاً ایمیل خودت رو وارد کن تا اطلاعات و راهنمای کامل برات ارسال بشه.")
    # state updated by caller

def confirm_saved_and_finish(recipient_id, name):
    send_text(recipient_id, f"✅ {name} عزیز، اطلاعاتت ثبت شد. تیم ما به زودی با تو تماس می‌گیره.\nمتشکرم!")
    # optionally show a short menu / next steps
    send_text(recipient_id, "اگر سوال دیگری داری، پیام بده یا بنویس 'راهنما' برای دیدن گزینه‌ها.")
    clear_state(recipient_id)

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
    print("❌ Webhook verification failed.")
    return "Verification failed", 403

# ----------------------------
# webhook receiver (message events)
# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    print("📩 Webhook POST:", data)
    if not data:
        return "no data", 400

    # structure depends on webhook subscription; handle common patterns
    try:
        # new IG messages typically appear under entry[].changes[].value or entry[].messaging
        entries = data.get("entry", [])
        for entry in entries:
            # try messaging (some setups)
            messaging_list = entry.get("messaging") or []
            for msg in messaging_list:
                _handle_message_event(msg)
            # try changes/value pattern
            for change in entry.get("changes", []):
                value = change.get("value", {})
                # value may contain 'messages' or 'message'
                if "messages" in value:
                    for m in value.get("messages", []):
                        _handle_message_event(m)
                elif "message" in value:
                    _handle_message_event({"message": value.get("message"), "from": value.get("from")})
                else:
                    # sometimes value itself is the message-like payload
                    if "from" in value and ("text" in value or "message" in value):
                        _handle_message_event(value)
    except Exception as e:
        print("⚠️ Error handling webhook:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

    return "ok", 200

def _handle_message_event(payload):
    """
    Normalize and process a single message payload.
    Expected minimal fields: sender id and text.
    """
    # different shapes: { "sender": {"id": ...}, "message": {"text": "..."}} OR
    # { "from": {"id": ...}, "text": "..." } etc.
    sender_id = None
    text = None

    # common patterns:
    if isinstance(payload.get("sender"), dict):
        sender_id = payload["sender"].get("id")
    if isinstance(payload.get("from"), dict):
        sender_id = sender_id or payload["from"].get("id")

    # message nested
    msg = payload.get("message") or {}
    if isinstance(msg, dict):
        text = msg.get("text") or msg.get("body") or text

    # top-level text
    text = text or payload.get("text") or payload.get("body") or ""

    if not sender_id:
        print("⚠️ no sender id in payload:", payload)
        return

    text = (text or "").strip()
    if not text:
        # ignore non-text messages for this simple bot
        print(f"🔕 ignoring empty/non-text from {sender_id}")
        return

    state = get_state(sender_id)
    state_name = state.get("state") if state else None

    # flow:
    if not state:
        # first contact: send pitch + ask name
        print(f"✨ New contact {sender_id}: sending pitch and asking name")
        send_welcome_and_ask_name(sender_id)
        return

    if state_name == "expecting_name":
        # save name and ask email
        name = text
        set_state(sender_id, {"state": "expecting_email", "name": name})
        ask_for_email(sender_id, name)
        return

    if state_name == "expecting_email":
        email = text
        # simple validation
        if not is_valid_email(email):
            send_text(sender_id, "ایمیل وارد شده نامعتبر است. لطفاً آدرس ایمیل معتبر وارد کنید (مثال: name@example.com).")
            # keep state as expecting_email
            with _state_lock:
                s = user_state.get(sender_id, {})
                s["ts"] = now_ts()
                user_state[sender_id] = s
            return
        # persist and confirm
        s = get_state(sender_id) or {}
        name = s.get("name", "")
        # send to Google Sheet
        try:
            status, resp = save_to_google_sheet(sender_id, name, email)
            print(f"💾 Saved to sheet: status={status}")
        except Exception as e:
            print("❌ Error saving to sheet:", e)
            send_text(sender_id, "خطا در ذخیره‌سازی اطلاعات. لطفاً بعداً تلاش کنید.")
            clear_state(sender_id)
            return

        confirm_saved_and_finish(sender_id, name)
        return

    # default fallback
    send_text(sender_id, "پیام شما دریافت شد — لطفاً 'ثبت‌نام' را برای شروع ارسال کنید یا اول نام خود را بفرستید.")
    set_state(sender_id, {"state": "expecting_name"})

# ----------------------------
# run
# ----------------------------
if __name__ == "__main__":
    print(f"🚀 Starting Instagram Lead Bot on port {PORT} ...")
    app.run(host="0.0.0.0", port=PORT)
