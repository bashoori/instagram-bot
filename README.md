# 🤖 Meta Lead Bot (Instagram + Messenger)
**Author:** Bita Ashoori  
**Description:**  
A lightweight Flask bot that automatically replies to **Instagram** and **Facebook Messenger** DMs, introduces your **Digital Marketing Franchise System**, and collects leads (name + email).  
Leads are sent to a **Google Sheet** via Apps Script.  
Supports **both platforms in one app** with simple in-memory session management.

---

## 🌟 Features
- 💬 Auto-reply to incoming DMs on Instagram and Messenger  
- 🧭 Persian conversation flow introducing the Digital Franchise system  
- 🧾 Collects name → email in two steps  
- 📊 Saves leads to Google Sheets using a webhook (Apps Script)  
- 🧠 Lightweight in-memory state with automatic cleanup (10 min TTL)  
- ☁️ Deployable to **Render**, **Codespaces**, or any Python host

---




pip install -r requirements.txt

python tests/test_webhook.py


python main.py
