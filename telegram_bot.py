"""
Expenz.io - Telegram AI Assistant & Live Excel Expense Logger
100% Free, permanent, zero-restriction personal financial bot on Telegram.
"""

import os
import re
import json
import requests
from datetime import datetime
import excel_manager
import gemini_parser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TELEGRAM_TOKEN_FILE = os.path.join(BASE_DIR, ".telegram_token")

def get_telegram_bot_token():
    """Get stored Telegram Bot Token from environment or config file."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token and os.path.exists(TELEGRAM_TOKEN_FILE):
        try:
            with open(TELEGRAM_TOKEN_FILE, "r") as f:
                token = f.read().strip()
        except Exception:
            token = ""
    return token

def save_telegram_bot_token(token):
    """Save Telegram Bot Token to environment and config file."""
    clean_token = str(token or "").strip()
    os.environ["TELEGRAM_BOT_TOKEN"] = clean_token
    try:
        with open(TELEGRAM_TOKEN_FILE, "w") as f:
            f.write(clean_token)
    except Exception as e:
        print("Failed to write .telegram_token:", e)
    return clean_token

def set_telegram_webhook(bot_token, webhook_url):
    """Registers webhook URL with Telegram Bot API."""
    if not bot_token:
        return {"success": False, "error": "Bot token is missing"}
    
    api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    try:
        resp = requests.post(api_url, json={"url": webhook_url}, timeout=15)
        data = resp.json()
        if data.get("ok"):
            return {"success": True, "description": data.get("description", "Webhook set successfully")}
        return {"success": False, "error": data.get("description", "Failed to set webhook")}
    except Exception as e:
        return {"success": False, "error": str(e)}

def send_telegram_message(chat_id, text, reply_markup=None, bot_token=None):
    """Sends a markdown-formatted message to a Telegram chat."""
    token = bot_token or get_telegram_bot_token()
    if not token:
        print("Telegram bot token not configured.")
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False

def download_telegram_photo(file_id, bot_token=None):
    """Downloads photo bytes from Telegram using file_id."""
    token = bot_token or get_telegram_bot_token()
    if not token or not file_id:
        return None, None

    try:
        # 1. Get file path
        get_file_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
        r = requests.get(get_file_url, timeout=10)
        file_info = r.json()
        if not file_info.get("ok"):
            return None, None
        
        file_path = file_info["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        
        # 2. Download bytes
        img_res = requests.get(download_url, timeout=20)
        if img_res.status_code == 200:
            mime = "image/jpeg" if file_path.endswith(".jpg") or file_path.endswith(".jpeg") else "image/png"
            return img_res.content, mime
    except Exception as e:
        print(f"Failed to download Telegram photo: {e}")
    
    return None, None

TELEGRAM_INTENT_PROMPT = """
You are "Expenz Telegram AI", the personal finance assistant for Expenz.io.
Today's date is {today_date}.
Active Month: {active_month_label}.

The user sent a message on Telegram (text or receipt description).
Analyze their input and determine the appropriate action:

Standard Categories:
{categories_list}

Standard Payment Methods:
["Amex Card", "Credit Card", "Debit Card", "Cash", "Bank Transfer", "UPI / Online", "Apple Pay / Google Pay"]

Actions:
1. "LOG_EXPENSE": The user is logging an expense, purchase, bill, or receipt.
   Extract:
   - "date": Date in "YYYY-MM-DD" format (default to today if unspecified).
   - "amount": Floating point number (> 0).
   - "category": Best matching category from standard list.
   - "payment_method": Detected payment method (default "Amex Card" or "Credit Card").
   - "description": Concise merchant name or item summary (e.g. "Chipotle Lunch", "Shell Gas").

2. "ASK_COPILOT": The user is asking a question about their spending, budget, summaries, or financial advice.
   - Formulate a helpful, friendly, and accurate answer using their live financial ledger data below.

3. "SUMMARY": The user asked for a summary, overview, or report (e.g. "summary", "overview", "status", "budget").

Return ONLY a valid JSON object matching one of these structures:

If LOG_EXPENSE:
{{
  "action": "LOG_EXPENSE",
  "expense": {{
    "date": "2026-08-14",
    "amount": 34.50,
    "category": "Food & Dining",
    "payment_method": "Amex Card",
    "description": "Chipotle Lunch"
  }}
}}

If ASK_COPILOT or SUMMARY:
{{
  "action": "COPILOT_REPLY",
  "reply": "Your Telegram-formatted response using *bold* for emphasis, clean emojis, and concise bullet points."
}}
"""

def process_telegram_update(update_json, user_id=None):
    """
    Processes an incoming Telegram Webhook Update object and replies via Telegram Bot API.
    """
    if not update_json:
        return {"status": "empty"}

    # Handle callback query from inline buttons
    if "callback_query" in update_json:
        cb = update_json["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb.get("data", "")
        
        if data == "cmd_summary":
            return handle_summary_command(chat_id, user_id=user_id)
        elif data == "cmd_budgets":
            return handle_budgets_command(chat_id, user_id=user_id)
        elif data == "cmd_recent":
            return handle_recent_command(chat_id, user_id=user_id)
        elif data == "cmd_help":
            return handle_start_command(chat_id, user_id=user_id)

    message = update_json.get("message")
    if not message:
        return {"status": "no_message"}

    chat_id = message["chat"]["id"]
    text = (message.get("text") or message.get("caption") or "").strip()
    photo_list = message.get("photo")

    # Command Handlers
    if text.startswith("/start") or text.startswith("/help"):
        return handle_start_command(chat_id, user_id=user_id)
    elif text.startswith("/summary") or text.startswith("/overview"):
        return handle_summary_command(chat_id, user_id=user_id)
    elif text.startswith("/budget") or text.startswith("/budgets"):
        return handle_budgets_command(chat_id, user_id=user_id)
    elif text.startswith("/recent") or text.startswith("/expenses"):
        return handle_recent_command(chat_id, user_id=user_id)

    # Handle Photo / Receipt
    image_bytes = None
    mime_type = None
    if photo_list:
        # Highest resolution is last item in photo array
        highest_res = photo_list[-1]
        file_id = highest_res["file_id"]
        image_bytes, mime_type = download_telegram_photo(file_id)
        if not text:
            text = "Please analyze this receipt image and extract the merchant, total amount, date, and expense category."

    today_str = datetime.now().strftime("%Y-%m-%d")
    summary = excel_manager.get_summary_stats(user_id=user_id)
    all_expenses = excel_manager.get_expenses(user_id=user_id)
    categories = excel_manager.get_categories(user_id=user_id)
    cat_names = [c["name"] for c in categories]

    context_payload = {
        "active_period": summary.get("active_month_label", "Current Month"),
        "total_spent": summary.get("current_month_spend", 0.0),
        "total_budget": summary.get("total_monthly_budget", 0.0),
        "remaining_budget": summary.get("remaining_budget", 0.0),
        "budget_usage_pct": summary.get("budget_usage_pct", 0.0),
        "category_spending": summary.get("category_breakdown", []),
        "recent_expenses_sample": all_expenses[:40] if all_expenses else []
    }

    system_prompt = TELEGRAM_INTENT_PROMPT.format(
        today_date=today_str,
        active_month_label=summary.get("active_month_label", "Current Month"),
        categories_list=json.dumps(cat_names, indent=2)
    )

    user_query = f"""=== USER LIVE FINANCIAL LEDGER DATA ===
{json.dumps(context_payload, indent=2)}

=== INCOMING TELEGRAM MESSAGE ===
{text}

Return JSON with action:"""

    try:
        raw_ai_text = gemini_parser.execute_ai_completion(
            prompt=user_query,
            system_instruction=system_prompt,
            image_bytes=image_bytes,
            mime_type=mime_type
        )

        clean_text = raw_ai_text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text)

        match = re.search(r'\{.*\}', clean_text, re.DOTALL)
        parsed_intent = json.loads(match.group(0)) if match else json.loads(clean_text)

        action = parsed_intent.get("action", "COPILOT_REPLY")

        # Action A: Log Expense to Excel
        if action == "LOG_EXPENSE" and "expense" in parsed_intent:
            exp = parsed_intent["expense"]
            date_val = exp.get("date") or today_str
            amt_val = float(exp.get("amount") or 0.0)
            cat_val = exp.get("category") or "Miscellaneous"
            pay_val = exp.get("payment_method") or "Amex Card"
            desc_val = exp.get("description") or "Telegram Purchase"

            if amt_val > 0:
                excel_manager.add_expense(
                    date=date_val,
                    amount=amt_val,
                    category=cat_val,
                    payment_method=pay_val,
                    description=desc_val,
                    user_id=user_id
                )

                new_summary = excel_manager.get_summary_stats(user_id=user_id)
                budgets = excel_manager.get_budgets(user_id=user_id)
                cat_budget = budgets.get(cat_val, 0.0)
                
                cat_spend = 0.0
                for c in new_summary.get("category_breakdown", []):
                    if c.get("category", "").lower() == cat_val.lower():
                        cat_spend = c.get("amount", 0.0)
                        break

                budget_info = f"\n🎯 *Category Budget:* ${cat_spend:,.2f} / ${cat_budget:,.2f}" if cat_budget > 0 else ""

                reply = (
                    f"✅ *Expense Logged to Excel!*\n\n"
                    f"💳 *Amount:* `${amt_val:,.2f}`\n"
                    f"🏷️ *Category:* {cat_val}\n"
                    f"🏬 *Merchant:* {desc_val}\n"
                    f"📅 *Date:* {date_val}\n"
                    f"💵 *Payment:* {pay_val}"
                    f"{budget_info}\n\n"
                    f"📊 *{new_summary.get('active_month_label', 'Month')} Total:* `${new_summary.get('current_month_spend', 0.0):,.2f}` "
                    f"(Remaining: *${new_summary.get('remaining_budget', 0.0):,.2f}*)"
                )

                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "📊 Month Summary", "callback_data": "cmd_summary"},
                            {"text": "💰 View Budgets", "callback_data": "cmd_budgets"}
                        ],
                        [
                            {"text": "🌐 Open Web App", "url": "https://expenz-io.onrender.com"}
                        ]
                    ]
                }
                send_telegram_message(chat_id, reply, reply_markup=keyboard)
                return {"status": "expense_logged"}

        # Action B: Copilot Response
        reply_content = parsed_intent.get("reply") or clean_text
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📊 Summary", "callback_data": "cmd_summary"},
                    {"text": "🧾 Recent", "callback_data": "cmd_recent"}
                ]
            ]
        }
        send_telegram_message(chat_id, reply_content, reply_markup=keyboard)
        return {"status": "copilot_replied"}

    except Exception as e:
        print(f"Telegram processing error: {e}")
        send_telegram_message(chat_id, f"💬 Received: \"{text}\"\n\n_Tip: To log an expense, type e.g.:_\n• `Spent $35 at Starbucks on Amex`\n• Or snap and send a photo of your receipt!")
        return {"status": "fallback"}

def handle_start_command(chat_id, user_id=None):
    summary = excel_manager.get_summary_stats(user_id=user_id)
    month_label = summary.get("active_month_label", "Current Month")
    spend = summary.get("current_month_spend", 0.0)
    budget = summary.get("total_monthly_budget", 0.0)
    remaining = summary.get("remaining_budget", 0.0)

    msg = (
        f"👋 *Welcome to Expenz AI on Telegram!*\n\n"
        f"I am your personal financial assistant with direct live sync to your Excel ledger.\n\n"
        f"📊 *{month_label} Overview:*\n"
        f"• Total Spent: *${spend:,.2f}*\n"
        f"• Monthly Budget: *${budget:,.2f}*\n"
        f"• Remaining: *${remaining:,.2f}*\n\n"
        f"⚡ *What you can do:*\n"
        f"1️⃣ *Log an expense naturally:*\n"
        f"   _\"$42.50 at Chipotle on Amex for lunch\"_\n"
        f"   _\"Paid $120 for groceries yesterday\"_\n"
        f"2️⃣ *Snap receipt photos:* Send any bill photo\n"
        f"3️⃣ *Ask Copilot questions:*\n"
        f"   _\"How much did I spend on dining this month?\"_\n"
        f"   _\"What was my largest purchase?\"_\n\n"
        f"Quick commands: /summary, /budget, /recent"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 August Summary", "callback_data": "cmd_summary"},
                {"text": "💰 Category Budgets", "callback_data": "cmd_budgets"}
            ],
            [
                {"text": "🧾 Recent Expenses", "callback_data": "cmd_recent"},
                {"text": "🌐 Open Expenz Web App", "url": "https://expenz-io.onrender.com"}
            ]
        ]
    }
    send_telegram_message(chat_id, msg, reply_markup=keyboard)
    return {"status": "start_command_sent"}

def handle_summary_command(chat_id, user_id=None):
    summary = excel_manager.get_summary_stats(user_id=user_id)
    month_label = summary.get("active_month_label", "Current Month")
    spend = summary.get("current_month_spend", 0.0)
    budget = summary.get("total_monthly_budget", 0.0)
    remaining = summary.get("remaining_budget", 0.0)
    pct = summary.get("budget_usage_pct", 0.0)
    count = summary.get("current_month_count", 0)

    cats = summary.get("category_breakdown", [])
    cat_text = ""
    for c in cats[:5]:
        cat_text += f"\n• {c.get('category')}: *${c.get('amount', 0):,.2f}* ({c.get('percentage', 0)}%)"

    msg = (
        f"📊 *{month_label} Financial Summary*\n\n"
        f"💸 *Total Spent:* `${spend:,.2f}`\n"
        f"🎯 *Total Budget:* `${budget:,.2f}`\n"
        f"💰 *Remaining:* `${remaining:,.2f}`\n"
        f"📈 *Budget Usage:* `{pct}%`\n"
        f"🧾 *Total Entries:* `{count}`\n\n"
        f"🏆 *Top Spending Categories:*{cat_text or ' No expenses recorded yet.'}"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "💰 View All Budgets", "callback_data": "cmd_budgets"},
                {"text": "🧾 Recent Expenses", "callback_data": "cmd_recent"}
            ]
        ]
    }
    send_telegram_message(chat_id, msg, reply_markup=keyboard)
    return {"status": "summary_sent"}

def handle_budgets_command(chat_id, user_id=None):
    summary = excel_manager.get_summary_stats(user_id=user_id)
    comparison = summary.get("budget_comparison", [])

    lines = []
    for item in comparison:
        spent = item.get("spent", 0.0)
        budget = item.get("budget", 0.0)
        pct = item.get("usage_pct", 0.0)
        status_emoji = "🔴" if pct > 100 else ("🟡" if pct > 80 else "🟢")
        lines.append(f"{status_emoji} *{item.get('category')}:* ${spent:,.2f} / ${budget:,.2f} (`{pct}%`)")

    msg = f"🎯 *Category Budgets for {summary.get('active_month_label', 'Month')}:*\n\n" + "\n".join(lines)
    send_telegram_message(chat_id, msg)
    return {"status": "budgets_sent"}

def handle_recent_command(chat_id, user_id=None):
    expenses = excel_manager.get_expenses(user_id=user_id)
    if not expenses:
        send_telegram_message(chat_id, "ℹ️ No recent expenses found in your Excel ledger.")
        return {"status": "no_expenses"}

    lines = []
    for e in expenses[:6]:
        lines.append(f"• *${e.get('amount', 0):,.2f}* — {e.get('description')} ({e.get('category')}) on `{e.get('date')}`")

    msg = f"🧾 *Last {len(lines)} Expenses Logged:*\n\n" + "\n".join(lines)
    send_telegram_message(chat_id, msg)
    return {"status": "recent_sent"}
