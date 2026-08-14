"""
Expenz.io - Telegram AI Financial Copilot & Live Excel Controller
100% Free forever • Live Excel Ledger Sync • Voice/Receipt Parsing • Natural Language Edits & Insights
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
TELEGRAM_USERS_FILE = os.path.join(BASE_DIR, ".telegram_users.json")
RAILWAY_URL = "https://web-production-9ad68.up.railway.app"

# In-memory review cache for multi-step interactive confirmations: { chat_id: { expense_dict, timestamp } }
PENDING_REVIEWS = {}

def get_user_id_for_chat(chat_id):
    """Retrieves synced workspace/user ID for given Telegram chat."""
    if not chat_id:
        return 'default'
    try:
        if os.path.exists(TELEGRAM_USERS_FILE):
            with open(TELEGRAM_USERS_FILE, "r") as f:
                data = json.load(f)
                return data.get(str(chat_id), 'default')
    except Exception:
        pass
    return 'default'

def set_user_id_for_chat(chat_id, user_id):
    """Binds Telegram chat ID to a workspace / sync code."""
    if not chat_id:
        return 'default'
    clean_id = "".join(c for c in str(user_id or '') if c.isalnum() or c in ("-", "_")).strip()
    clean_id = clean_id[:64] or 'default'
    
    data = {}
    try:
        if os.path.exists(TELEGRAM_USERS_FILE):
            with open(TELEGRAM_USERS_FILE, "r") as f:
                data = json.load(f)
    except Exception:
        data = {}
        
    data[str(chat_id)] = clean_id
    try:
        with open(TELEGRAM_USERS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("Failed to save .telegram_users.json:", e)
    return clean_id

def get_telegram_bot_token():
    """Get stored Telegram Bot Token from environment or config file."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token and os.path.exists(TELEGRAM_TOKEN_FILE):
        try:
            with open(TELEGRAM_TOKEN_FILE, "r") as f:
                token = f.read().strip()
        except Exception:
            token = ""
    return token or "8741729287:AAEOx_wmCPVvgHFVzcCoeRm1VQzLqkg7xzg"

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
        return r.json() if r.status_code == 200 else False
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False

def edit_telegram_message(chat_id, message_id, text, reply_markup=None, bot_token=None):
    """Edits an existing Telegram message in place."""
    token = bot_token or get_telegram_bot_token()
    if not token:
        return False
    
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Error editing Telegram message: {e}")
        return False

def answer_callback_query(callback_query_id, text=None, bot_token=None):
    """Acknowledges an inline button callback query."""
    token = bot_token or get_telegram_bot_token()
    if not token:
        return False
    try:
        requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery", json={
            "callback_query_id": callback_query_id,
            "text": text or ""
        }, timeout=5)
    except Exception:
        pass

def download_telegram_photo(file_id, bot_token=None):
    """Downloads photo bytes from Telegram using file_id."""
    token = bot_token or get_telegram_bot_token()
    if not token or not file_id:
        return None, None

    try:
        get_file_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
        r = requests.get(get_file_url, timeout=10)
        file_info = r.json()
        if not file_info.get("ok"):
            return None, None
        
        file_path = file_info["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        
        img_res = requests.get(download_url, timeout=20)
        if img_res.status_code == 200:
            mime = "image/jpeg" if file_path.endswith(".jpg") or file_path.endswith(".jpeg") else "image/png"
            return img_res.content, mime
    except Exception as e:
        print(f"Failed to download Telegram photo: {e}")
    
    return None, None

TELEGRAM_MASTER_AI_PROMPT = """
You are "Expenz AI", an elite personal finance copilot and intelligent financial advisor for Expenz.io on Telegram.
Today's date is {today_date}.
Active Month: {active_month_label}.

You have complete live access to the user's Excel spreadsheet, categories, budgets, and spending ledger.

STANDARD CATEGORIES:
{categories_list}

STANDARD PAYMENT METHODS:
["Amex Card", "Credit Card", "Debit Card", "Cash", "Bank Transfer", "UPI / Online", "Apple Pay / Google Pay"]

USER LIVE FINANCIAL CONTEXT:
{financial_context}

INCOMING USER MESSAGE (OR RECEIPT CAPTION):
{user_message}

DECIDE THE APPROPRIATE ACTION:

1. "REVIEW_EXPENSE": Use this if:
   - The user explicitly asked to "review", "confirm", "check first", "draft", or "verify before adding" (e.g. "Add this expense please. Review before adding.").
   - Or if user uploaded a receipt with "review" in the text.
   Extract:
   - "expense": {{ "date": "YYYY-MM-DD", "amount": float, "category": string, "payment_method": string, "description": string }}

2. "LOG_EXPENSE": The user wants to directly log an expense without requesting a pre-review (e.g. "Spent $35 on gas", "$42 at Chipotle").
   Extract:
   - "expense": {{ "date": "YYYY-MM-DD", "amount": float, "category": string, "payment_method": string, "description": string }}

3. "EDIT_EXPENSE": The user wants to edit, update, or change an existing logged expense (e.g. "Change the last Walmart expense to $15.50", "Make expense #12 $45", "Update Chipotle category to Dining").
   Extract:
   - "target_search": description/merchant to find the expense (e.g. "Walmart")
   - "target_id": integer expense ID if mentioned (or null)
   - "updates": {{ "amount": float, "category": string, "date": string, "payment_method": string, "description": string }}

4. "DELETE_EXPENSE": The user wants to delete or remove an expense (e.g. "Delete the Starbucks expense", "Remove expense #4").
   Extract:
   - "target_search": merchant name or criteria (e.g. "Starbucks")
   - "target_id": integer ID if specified (or null)

5. "UPDATE_BUDGET": The user wants to modify a category budget limit (e.g. "Increase dining budget to $600", "Set groceries budget to $400").
   Extract:
   - "category": category name
   - "new_budget": float

6. "GET_INSIGHTS": The user asked for financial insights, health score, spending audit, recommendations, or tips (e.g. "How am I doing?", "Give me insights", "Audit my budget", "/insights").
   Provide:
   - "reply": Rich markdown diagnostic with Budget Health Score (0-100), top risk areas, smart savings recommendations, and projected month-end balance.

7. "COPILOT_CHAT": The user is asking a financial question, seeking financial guidance, comparing spending across months, checking highest spends, or conversing.
   Provide:
   - "reply": Highly intelligent, conversational, accurate response citing live ledger figures with clean formatting.

Return ONLY a valid JSON object matching the chosen action:
"""

def process_telegram_update(update_json, user_id=None):
    """
    Main webhook entry point for all Telegram updates.
    """
    if not update_json:
        return {"status": "empty"}

    # 1. Handle Inline Keyboard Button Taps
    if "callback_query" in update_json:
        cb = update_json["callback_query"]
        cb_id = cb["id"]
        chat_id = cb["message"]["chat"]["id"]
        msg_id = cb["message"]["message_id"]
        data = cb.get("data", "")
        
        user_id = user_id or get_user_id_for_chat(chat_id)

        answer_callback_query(cb_id)

        if data == "confirm_add_pending":
            return execute_confirm_pending_expense(chat_id, msg_id, user_id=user_id)
        elif data == "cancel_add_pending":
            PENDING_REVIEWS.pop(chat_id, None)
            edit_telegram_message(chat_id, msg_id, "❌ *Expense discarded.* Nothing was logged to Excel.")
            return {"status": "review_cancelled"}
        elif data == "cmd_summary":
            return handle_summary_command(chat_id, user_id=user_id)
        elif data == "cmd_budgets":
            return handle_budgets_command(chat_id, user_id=user_id)
        elif data == "cmd_recent":
            return handle_recent_command(chat_id, user_id=user_id)
        elif data == "cmd_insights":
            return handle_insights_command(chat_id, user_id=user_id)
        elif data == "cmd_help":
            return handle_start_command(chat_id, user_id=user_id)

    message = update_json.get("message")
    if not message:
        return {"status": "no_message"}

    chat_id = message["chat"]["id"]
    text = (message.get("text") or message.get("caption") or "").strip()
    photo_list = message.get("photo")

    # Resolve active workspace for this Telegram chat
    user_id = user_id or get_user_id_for_chat(chat_id)

    # 2. Workspace Linking Command: /link or /sync
    if text.startswith("/link") or text.startswith("/sync"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1 and parts[1].strip():
            new_code = parts[1].strip()
            bound_id = set_user_id_for_chat(chat_id, new_code)
            
            fp = excel_manager.get_excel_file_path(bound_id)
            excel_manager.init_excel(fp)
            
            summary = excel_manager.get_summary_stats(user_id=bound_id)
            msg = (
                f"🔗 *Workspace Linked Successfully!*\n\n"
                f"Your Telegram bot is now synced to workspace: *`{bound_id}`*\n\n"
                f"📱 *Cross-Device Active:* All expenses, receipt photos, and Copilot chats are now linked directly to the same ledger as your iPhone and laptop.\n\n"
                f"📊 *{summary.get('active_month_label', 'Month')} Total:* `${summary.get('current_month_spend', 0.0):,.2f}`\n"
                f"🎯 *Monthly Budget:* `${summary.get('total_monthly_budget', 0.0):,.2f}`"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "📊 Month Summary", "callback_data": "cmd_summary"},
                        {"text": "🧾 Recent Expenses", "callback_data": "cmd_recent"}
                    ],
                    [
                        {"text": "🌐 Open Web App", "url": f"{RAILWAY_URL}"}
                    ]
                ]
            }
            send_telegram_message(chat_id, msg, reply_markup=keyboard)
            return {"status": "workspace_linked", "user_id": bound_id}
        else:
            current_id = get_user_id_for_chat(chat_id)
            msg = (
                f"🔗 *Current Synced Workspace:* *`{current_id}`*\n\n"
                f"To link your Telegram bot to your iPhone & laptop sync code, send:\n"
                f"• `/link <your-sync-code>` (e.g. `/link usr_fy4w6q1y`)\n\n"
                f"You can find your sync code in the web app under the **Sync** button."
            )
            send_telegram_message(chat_id, msg)
            return {"status": "link_info_sent"}

    # 3. Direct Bot Commands
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1 and parts[1].strip():
            new_code = parts[1].strip()
            user_id = set_user_id_for_chat(chat_id, new_code)
            fp = excel_manager.get_excel_file_path(user_id)
            excel_manager.init_excel(fp)
        return handle_start_command(chat_id, user_id=user_id)
    elif text.startswith("/help"):
        return handle_start_command(chat_id, user_id=user_id)
    elif text.startswith("/summary") or text.startswith("/overview"):
        return handle_summary_command(chat_id, user_id=user_id)
    elif text.startswith("/budget") or text.startswith("/budgets"):
        return handle_budgets_command(chat_id, user_id=user_id)
    elif text.startswith("/recent") or text.startswith("/expenses"):
        return handle_recent_command(chat_id, user_id=user_id)
    elif text.startswith("/insights") or text.startswith("/audit"):
        return handle_insights_command(chat_id, user_id=user_id)

    # 3. Handle Photo / Receipt
    image_bytes = None
    mime_type = None
    if photo_list:
        highest_res = photo_list[-1]
        file_id = highest_res["file_id"]
        image_bytes, mime_type = download_telegram_photo(file_id)
        if not text:
            text = "Please analyze this receipt photo. Extract the merchant, total amount, date, and category."

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
        "budget_comparison": summary.get("budget_comparison", []),
        "recent_expenses": all_expenses[:35] if all_expenses else []
    }

    system_prompt = TELEGRAM_MASTER_AI_PROMPT.format(
        today_date=today_str,
        active_month_label=summary.get("active_month_label", "Current Month"),
        categories_list=json.dumps(cat_names, indent=2),
        financial_context=json.dumps(context_payload, indent=2),
        user_message=text
    )

    try:
        raw_ai_text = gemini_parser.execute_ai_completion(
            prompt="Analyze the user request and return the JSON action:",
            system_instruction=system_prompt,
            image_bytes=image_bytes,
            mime_type=mime_type
        )

        clean_text = raw_ai_text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text)

        match = re.search(r'\{.*\}', clean_text, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else json.loads(clean_text)

        action = parsed.get("action", "COPILOT_CHAT")

        # --- ACTION 1: REVIEW FIRST (With Interactive Confirm/Cancel Buttons) ---
        if action == "REVIEW_EXPENSE" and "expense" in parsed:
            exp = parsed["expense"]
            date_val = exp.get("date") or today_str
            amt_val = float(exp.get("amount") or 0.0)
            cat_val = exp.get("category") or "Miscellaneous"
            pay_val = exp.get("payment_method") or "Amex Card"
            desc_val = exp.get("description") or "Receipt Purchase"

            PENDING_REVIEWS[chat_id] = {
                "date": date_val,
                "amount": amt_val,
                "category": cat_val,
                "payment_method": pay_val,
                "description": desc_val,
                "timestamp": datetime.now().timestamp()
            }

            review_msg = (
                f"🧐 *Review Expense Details Before Adding:*\n\n"
                f"💳 *Amount:* `${amt_val:,.2f}`\n"
                f"🏷️ *Category:* {cat_val}\n"
                f"🏬 *Merchant:* {desc_val}\n"
                f"📅 *Date:* {date_val}\n"
                f"💵 *Payment Method:* {pay_val}\n\n"
                f"_Would you like me to log this to your Excel spreadsheet?_"
            )

            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Confirm & Log to Excel", "callback_data": "confirm_add_pending"},
                        {"text": "❌ Cancel", "callback_data": "cancel_add_pending"}
                    ]
                ]
            }
            send_telegram_message(chat_id, review_msg, reply_markup=keyboard)
            return {"status": "review_prompted"}

        # --- ACTION 2: DIRECT EXPENSE LOGGING ---
        elif action == "LOG_EXPENSE" and "expense" in parsed:
            exp = parsed["expense"]
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
                            {"text": "💡 Insights", "callback_data": "cmd_insights"},
                            {"text": "🌐 Open Web App", "url": RAILWAY_URL}
                        ]
                    ]
                }
                send_telegram_message(chat_id, reply, reply_markup=keyboard)
                return {"status": "expense_logged"}

        # --- ACTION 3: NATURAL LANGUAGE EDIT / UPDATE ---
        elif action == "EDIT_EXPENSE":
            target_id = parsed.get("target_id")
            target_search = (parsed.get("target_search") or "").lower()
            updates = parsed.get("updates") or {}

            matched_exp = None
            if target_id:
                for e in all_expenses:
                    if str(e.get("id")) == str(target_id):
                        matched_exp = e
                        break
            elif target_search:
                for e in all_expenses:
                    if target_search in str(e.get("description", "")).lower() or target_search in str(e.get("category", "")).lower():
                        matched_exp = e
                        break

            if matched_exp:
                new_date = updates.get("date") or matched_exp["date"]
                new_amt = float(updates.get("amount") or matched_exp["amount"])
                new_cat = updates.get("category") or matched_exp["category"]
                new_pay = updates.get("payment_method") or matched_exp["payment_method"]
                new_desc = updates.get("description") or matched_exp["description"]

                excel_manager.update_expense(
                    expense_id=matched_exp["id"],
                    date=new_date,
                    amount=new_amt,
                    category=new_cat,
                    payment_method=new_pay,
                    description=new_desc,
                    user_id=user_id
                )

                reply = (
                    f"✏️ *Expense #{matched_exp['id']} Updated in Excel!*\n\n"
                    f"• *Merchant:* `{matched_exp['description']}` ➔ *`{new_desc}`*\n"
                    f"• *Amount:* `${matched_exp['amount']:,.2f}` ➔ *`${new_amt:,.2f}`*\n"
                    f"• *Category:* `{matched_exp['category']}` ➔ *`{new_cat}`*\n"
                    f"• *Date:* `{new_date}`"
                )
                send_telegram_message(chat_id, reply)
                return {"status": "expense_edited"}
            else:
                send_telegram_message(chat_id, f"⚠️ Couldn't locate an expense matching *\"{target_search}\"*. Use /recent to see recent IDs.")
                return {"status": "edit_not_found"}

        # --- ACTION 4: NATURAL LANGUAGE DELETE ---
        elif action == "DELETE_EXPENSE":
            target_id = parsed.get("target_id")
            target_search = (parsed.get("target_search") or "").lower()

            matched_exp = None
            if target_id:
                for e in all_expenses:
                    if str(e.get("id")) == str(target_id):
                        matched_exp = e
                        break
            elif target_search:
                for e in all_expenses:
                    if target_search in str(e.get("description", "")).lower():
                        matched_exp = e
                        break

            if matched_exp:
                excel_manager.delete_expense(matched_exp["id"], user_id=user_id)
                reply = f"🗑️ *Deleted Expense #{matched_exp['id']}:* ${matched_exp['amount']:,.2f} for *{matched_exp['description']}* from Excel."
                send_telegram_message(chat_id, reply)
                return {"status": "expense_deleted"}
            else:
                send_telegram_message(chat_id, f"⚠️ Could not find an expense matching *\"{target_search}\"*. Try `/recent` to view latest expenses.")
                return {"status": "delete_not_found"}

        # --- ACTION 5: BUDGET LIMIT UPDATE ---
        elif action == "UPDATE_BUDGET":
            cat_name = parsed.get("category")
            new_budget = float(parsed.get("new_budget") or 0.0)
            if cat_name and new_budget >= 0:
                current_budgets = excel_manager.get_budgets(user_id=user_id)
                current_budgets[cat_name] = new_budget
                excel_manager.update_budgets(current_budgets, user_id=user_id)
                reply = f"🎯 *Budget Updated:* Set *{cat_name}* monthly limit to *${new_budget:,.2f}*."
                send_telegram_message(chat_id, reply)
                return {"status": "budget_updated"}

        # --- ACTION 6: FINANCIAL INSIGHTS ---
        elif action == "GET_INSIGHTS":
            return handle_insights_command(chat_id, user_id=user_id)

        # --- ACTION 7: INTELLIGENT COPILOT CHAT ---
        reply_content = parsed.get("reply") or clean_text
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📊 Summary", "callback_data": "cmd_summary"},
                    {"text": "💡 Insights", "callback_data": "cmd_insights"}
                ],
                [
                    {"text": "🧾 Recent Expenses", "callback_data": "cmd_recent"},
                    {"text": "🌐 Web App", "url": RAILWAY_URL}
                ]
            ]
        }
        send_telegram_message(chat_id, reply_content, reply_markup=keyboard)
        return {"status": "copilot_replied"}

    except Exception as e:
        print(f"Telegram processing error: {e}")
        send_telegram_message(
            chat_id,
            f"💬 Received your message: \"{text}\"\n\n"
            f"💡 *Try these commands or phrasing:*\n"
            f"• _\"Spent $45 at Walmart on Amex\"_\n"
            f"• _\"Add $10 for coffee. Review before adding.\"_\n"
            f"• _\"Change last Walmart expense to $12\"_\n"
            f"• _\"What's my biggest spend this month?\"_\n"
            f"• `/summary` or `/insights`"
        )
        return {"status": "fallback"}

def execute_confirm_pending_expense(chat_id, message_id, user_id=None):
    """Logs the pending reviewed expense after user taps Confirm."""
    pending = PENDING_REVIEWS.pop(chat_id, None)
    if not pending:
        edit_telegram_message(chat_id, message_id, "⚠️ Review session expired. Please send the expense or receipt again.")
        return {"status": "review_expired"}

    date_val = pending["date"]
    amt_val = pending["amount"]
    cat_val = pending["category"]
    pay_val = pending["payment_method"]
    desc_val = pending["description"]

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

    confirmed_text = (
        f"✅ *Confirmed & Logged to Excel!*\n\n"
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
                {"text": "🌐 Open Web App", "url": RAILWAY_URL}
            ]
        ]
    }
    edit_telegram_message(chat_id, message_id, confirmed_text, reply_markup=keyboard)
    return {"status": "pending_confirmed"}

def handle_start_command(chat_id, user_id=None):
    user_id = user_id or get_user_id_for_chat(chat_id)
    summary = excel_manager.get_summary_stats(user_id=user_id)
    month_label = summary.get("active_month_label", "Current Month")
    spend = summary.get("current_month_spend", 0.0)
    budget = summary.get("total_monthly_budget", 0.0)
    remaining = summary.get("remaining_budget", 0.0)

    workspace_badge = f"🔗 *Synced Workspace:* `{user_id}`" if user_id and user_id != 'default' else "🔗 *Workspace:* `Default Master Ledger`"

    msg = (
        f"👋 *Welcome to Expenz AI on Telegram!*\n"
        f"{workspace_badge}\n\n"
        f"📊 *{month_label} Overview:*\n"
        f"• Total Spent: *${spend:,.2f}*\n"
        f"• Monthly Budget: *${budget:,.2f}*\n"
        f"• Remaining: *${remaining:,.2f}*\n\n"
        f"⚡ *What you can do:*\n"
        f"1️⃣ *Log or Review Expenses naturally:*\n"
        f"   _\"$42.50 at Chipotle on Amex for lunch\"_\n"
        f"   _\"Add $10.14 for Walmart. Review before adding.\"_\n"
        f"2️⃣ *Snap & Send Receipts:* Send any bill photo\n"
        f"3️⃣ *Edit or Delete Expenses via Text:*\n"
        f"   _\"Change the last Walmart expense to $15\"_\n"
        f"   _\"Delete expense #8\"_\n"
        f"4️⃣ *Cross-Device Sync:* Type `/link <sync_code>` to sync with iPhone/Mac!\n\n"
        f"Commands: /summary, /budget, /insights, /recent, /link"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 Summary", "callback_data": "cmd_summary"},
                {"text": "💡 Financial Insights", "callback_data": "cmd_insights"}
            ],
            [
                {"text": "💰 Category Budgets", "callback_data": "cmd_budgets"},
                {"text": "🧾 Recent Expenses", "callback_data": "cmd_recent"}
            ],
            [
                {"text": "🌐 Open Expenz Web App", "url": RAILWAY_URL}
            ]
        ]
    }
    send_telegram_message(chat_id, msg, reply_markup=keyboard)
    return {"status": "start_sent"}

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
                {"text": "💡 Financial Insights", "callback_data": "cmd_insights"},
                {"text": "💰 Category Budgets", "callback_data": "cmd_budgets"}
            ],
            [
                {"text": "🧾 Recent Expenses", "callback_data": "cmd_recent"},
                {"text": "🌐 Open Web App", "url": RAILWAY_URL}
            ]
        ]
    }
    send_telegram_message(chat_id, msg, reply_markup=keyboard)
    return {"status": "summary_sent"}

def handle_insights_command(chat_id, user_id=None):
    """Generates and delivers structured AI financial health audit directly in Telegram."""
    summary = excel_manager.get_summary_stats(user_id=user_id)
    expenses = excel_manager.get_expenses(user_id=user_id)
    
    month_label = summary.get("active_month_label", "Current Month")
    insights = gemini_parser.generate_financial_insights(month_label, summary, expenses)
    score = insights.get("health_score", 85)
    status = insights.get("status", "Healthy")
    summary_text = insights.get("headline") or insights.get("summary") or "Your budget is pacing steadily."
    
    score_emoji = "🟢" if score >= 80 else ("🟡" if score >= 60 else "🔴")

    obs = insights.get("observations") or insights.get("key_observations") or []
    recs = insights.get("recommendations") or []
    obs_lines = "\n".join([f"• {o}" for o in obs[:3]])
    rec_lines = "\n".join([f"• {r}" for r in recs[:3]])
    savings = float(insights.get("projected_monthly_savings") or insights.get("potential_monthly_savings") or 0.0)

    msg = (
        f"🧠 *AI Financial Health & Insights*\n\n"
        f"{score_emoji} *Financial Health Score:* `{score}/100` ({status})\n\n"
        f"📝 *Diagnosis:*\n{summary_text}\n\n"
        f"🔍 *Key Observations:*\n{obs_lines or '• Budget pacing is within normal parameters.'}\n\n"
        f"💡 *Recommendations:*\n{rec_lines or '• Keep tracking daily expenses!'}\n\n"
        f"💵 *Estimated Monthly Savings Potential:* *${savings:,.2f}*"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 Month Summary", "callback_data": "cmd_summary"},
                {"text": "💰 View Budgets", "callback_data": "cmd_budgets"}
            ],
            [
                {"text": "🌐 Open Web App", "url": RAILWAY_URL}
            ]
        ]
    }
    send_telegram_message(chat_id, msg, reply_markup=keyboard)
    return {"status": "insights_sent"}

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
        lines.append(f"• `#{e.get('id')}` *${e.get('amount', 0):,.2f}* — {e.get('description')} ({e.get('category')}) on `{e.get('date')}`")

    msg = f"🧾 *Last {len(lines)} Expenses Logged:*\n\n" + "\n".join(lines) + "\n\n_Tip: You can say \"Change #1 to $20\" or \"Delete #1\" anytime!_"
    send_telegram_message(chat_id, msg)
    return {"status": "recent_sent"}
