"""
Expenz.io - WhatsApp Assistant & Live Ledger Connector
Integrates Twilio WhatsApp Sandbox to log expenses, parse receipt photos, and chat with AI Copilot via WhatsApp.
"""

import os
import re
import json
import requests
from datetime import datetime
import excel_manager
import gemini_parser

WHATSAPP_INTENT_PROMPT = """
You are "Expenz WhatsApp AI", the personal finance assistant for Expenz.io.
Today's date is {today_date}.
Active Month: {active_month_label}.

The user sent a message on WhatsApp (text or receipt description).
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
  }},
  "reply_note": "Short friendly note (e.g. 'Got it! Added $34.50 for Chipotle Lunch under Food & Dining.')"
}}

If ASK_COPILOT or SUMMARY:
{{
  "action": "COPILOT_REPLY",
  "reply": "Your WhatsApp-formatted response using *bold* for emphasis, clean emojis, and concise bullet points."
}}
"""

def generate_twiml_response(reply_text):
    """Generates TwiML XML string for Twilio WhatsApp Webhook response."""
    safe_text = (reply_text or "Message received.").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{safe_text}</Message>
</Response>"""

def process_whatsapp_message(from_number, body_text="", media_url=None, media_content_type=None, user_id=None):
    """
    Processes incoming WhatsApp text/image message and returns TwiML XML.
    """
    body_text = (body_text or "").strip()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Quick Help / Command routing
    if body_text.lower() in ("help", "start", "hi", "hello", "?", "menu"):
        summary = excel_manager.get_summary_stats(user_id=user_id)
        month_label = summary.get("active_month_label", "Current Month")
        spend = summary.get("current_month_spend", 0.0)
        budget = summary.get("total_monthly_budget", 0.0)
        remaining = summary.get("remaining_budget", 0.0)
        
        reply = (
            f"👋 *Welcome to Expenz.io on WhatsApp!*\n\n"
            f"📊 *{month_label} Overview:*\n"
            f"• Spent: *${spend:,.2f}*\n"
            f"• Budget: *${budget:,.2f}*\n"
            f"• Remaining: *${remaining:,.2f}*\n\n"
            f"💬 *How to use me:*\n"
            f"1️⃣ *Log an expense:* Just text naturally:\n"
            f"   _\"$42.50 at Chipotle on Amex for lunch\"_\n"
            f"   _\"Paid $120 for groceries yesterday\"_\n"
            f"2️⃣ *Send a receipt photo:* Snap and send a bill/receipt.\n"
            f"3️⃣ *Ask Copilot:* Ask any question:\n"
            f"   _\"How much budget is left in Dining?\"_\n"
            f"   _\"What was my biggest expense this week?\"_\n"
            f"   _\"Send monthly summary\"_\n\n"
            f"🌐 Live Web App: https://expenz-io.onrender.com"
        )
        return generate_twiml_response(reply)

    # 2. Prepare Ledger Context for AI
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

    # 3. Handle Receipt Photo if attached
    image_bytes = None
    mime_type = None
    if media_url:
        try:
            r = requests.get(media_url, timeout=20)
            if r.status_code == 200:
                image_bytes = r.content
                mime_type = media_content_type or "image/jpeg"
                if not body_text:
                    body_text = "Please analyze this receipt photo and log the total amount, merchant, date, and category."
        except Exception as e:
            print("Failed to download WhatsApp media:", e)

    system_prompt = WHATSAPP_INTENT_PROMPT.format(
        today_date=today_str,
        active_month_label=summary.get("active_month_label", "Current Month"),
        categories_list=json.dumps(cat_names, indent=2)
    )

    user_query = f"""=== USER LIVE FINANCIAL LEDGER DATA ===
{json.dumps(context_payload, indent=2)}

=== INCOMING WHATSAPP MESSAGE FROM USER ===
{body_text}

Return JSON with action:"""

    try:
        raw_ai_text = gemini_parser.execute_ai_completion(
            prompt=user_query,
            system_instruction=system_prompt,
            image_bytes=image_bytes,
            mime_type=mime_type
        )
        
        # Clean JSON
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
            desc_val = exp.get("description") or "WhatsApp Purchase"
            
            if amt_val > 0:
                # Add row to live Excel spreadsheet
                added_rec = excel_manager.add_expense(
                    date=date_val,
                    amount=amt_val,
                    category=cat_val,
                    payment_method=pay_val,
                    description=desc_val,
                    user_id=user_id
                )
                
                # Fetch updated stats for feedback
                new_summary = excel_manager.get_summary_stats(user_id=user_id)
                cat_spend = 0.0
                for c in new_summary.get("category_breakdown", []):
                    if c.get("category", "").lower() == cat_val.lower():
                        cat_spend = c.get("amount", 0.0)
                        break
                
                budgets = excel_manager.get_budgets(user_id=user_id)
                cat_budget = budgets.get(cat_val, 0.0)
                budget_info = f" ({cat_val} total: *${cat_spend:,.2f} / ${cat_budget:,.2f}*)" if cat_budget > 0 else ""

                reply = (
                    f"✅ *Expense Logged into Excel!*\n\n"
                    f"💳 *Amount:* ${amt_val:,.2f}\n"
                    f"🏷️ *Category:* {cat_val}{budget_info}\n"
                    f"🏬 *Merchant:* {desc_val}\n"
                    f"📅 *Date:* {date_val}\n"
                    f"💵 *Payment:* {pay_val}\n\n"
                    f"📊 *{new_summary.get('active_month_label', 'Month')} Total:* ${new_summary.get('current_month_spend', 0.0):,.2f} "
                    f"(Remaining Budget: *${new_summary.get('remaining_budget', 0.0):,.2f}*)"
                )
                return generate_twiml_response(reply)

        # Action B: Copilot Query / Advice Reply
        reply_content = parsed_intent.get("reply") or parsed_intent.get("reply_note")
        if not reply_content:
            reply_content = clean_text
            
        return generate_twiml_response(reply_content)

    except Exception as e:
        print(f"WhatsApp processing error: {e}")
        # Fallback simple parser
        return generate_twiml_response(
            f"💬 I received your message: \"{body_text}\".\n\n"
            f"Tip: To log an expense, format like:\n"
            f"• _\"$35 at Starbucks on Amex\"_\n"
            f"• Or send a photo of your receipt!"
        )
