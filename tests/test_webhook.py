# =====================================================
# Webhook Test Script
# Author: Bita Ashoori
# Description:
# Simulates webhook POST requests from Instagram & Messenger
# to test your Flask bot locally or on Render.
# =====================================================

import json
import requests

# ----------------------------
# CONFIG
# ----------------------------
# Change this to your deployed or local endpoint:
BASE_URL = "http://localhost:10000/webhook"
# Example for Render:
# BASE_URL = "https://instagram-bot-xgvo.onrender.com/webhook"

# ----------------------------
# MOCK PAYLOADS
# ----------------------------

# ✅ Instagram-style webhook payload
INSTAGRAM_PAYLOAD = {
    "object": "instagram",
    "entry": [
        {
            "id": "1234567890",
            "time": 1731200000,
            "changes": [
                {
                    "value": {
                        "from": {"id": "IG_USER_123"},
                        "message": {"text": "سلام"},
                        "id": "IG_MESSAGE_456"
                    },
                    "field": "messages"
                }
            ]
        }
    ]
}

# ✅ Messenger-style webhook payload
MESSENGER_PAYLOAD = {
    "object": "page",
    "entry": [
        {
            "id": "PAGE_123456",
            "time": 1731200000,
            "messaging": [
                {
                    "sender": {"id": "FB_USER_789"},
                    "recipient": {"id": "PAGE_123456"},
                    "timestamp": 1731200000,
                    "message": {"mid": "MID.abc123", "text": "سلام"}
                }
            ]
        }
    ]
}


# ----------------------------
# TEST FUNCTIONS
# ----------------------------
def send_webhook(payload, platform):
    """Send a simulated webhook POST request."""
    print(f"\n🧪 Sending simulated {platform} message...")
    headers = {"Content-Type": "application/json"}
    r = requests.post(BASE_URL, headers=headers, data=json.dumps(payload))
    print(f"✅ {platform} webhook test sent. Status: {r.status_code}")
    print("Response:", r.text)


# ----------------------------
# MAIN
# ----------------------------
if __name__ == "__main__":
    print("🚀 Starting webhook simulation tests...\n")

    # Send a fake Instagram message
    send_webhook(INSTAGRAM_PAYLOAD, "Instagram")

    # Send a fake Messenger message
    send_webhook(MESSENGER_PAYLOAD, "Messenger")

    print("\n✅ Tests complete. Check your Flask logs for bot responses!")
