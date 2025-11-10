import requests
import os

GSHEET_WEBHOOK_URL = os.getenv("GSHEET_WEBHOOK_URL")

def save_to_google_sheet(user_id, name, email):
    """ارسال داده‌ها به Google Sheet Webhook"""
    payload = {
        "ig_id": user_id,
        "name": name,
        "email": email
    }
    response = requests.post(GSHEET_WEBHOOK_URL, json=payload)
    return response.status_code, response.text
