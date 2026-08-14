import os
import json
import re
from datetime import datetime
from google import genai
from google.genai import types
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

STANDARD_CATEGORIES = [
    "Food & Dining",
    "Housing & Rent",
    "Utilities & Bills",
    "Transportation",
    "Shopping & Retail",
    "Entertainment & Leisure",
    "Healthcare & Wellness",
    "Education & Learning",
    "Personal Care",
    "Investments & Savings",
    "Refunds & Credits",
    "Miscellaneous"
]

EXTRACTION_SYSTEM_PROMPT = f"""
You are an expert financial document analyzer.
Analyze the provided statement (Bank Statement, Amex credit card bill, Excel spreadsheet, invoice, or receipt) and extract all expense and refund transactions.

Rules for Extraction:
1. Extract every purchase, debit, merchant fee, and merchant return/statement credit.
2. HANDLING CREDITS VS BILL PAYMENTS:
   - MERCHANT REFUNDS, RETURNS & CREDITS (e.g. Amazon refund, Airline cancellation credit, merchant dispute credit, cash back rewards): DO EXTRACT THESE. Classify them under 'Refunds & Credits' or the original purchase category, and clearly note '(Refund / Credit)' in description (e.g. "Amazon.com (Refund Credit)").
   - CREDIT CARD BILL PAYMENTS & SETTLEMENTS (e.g. "AUTOPAY PAYMENT RECEIVED - THANK YOU", "ONLINE PAYMENT RECEIVED", "DIRECT DEBIT PYMT"): DO NOT INCLUDE THESE (these are balance pay-downs from bank checking accounts, not purchases or merchant returns).
3. Standardize the Date into 'YYYY-MM-DD' format.
4. Extract the exact numerical Amount as a positive float (e.g. 45.20).
5. Clean up the Merchant / Description name (e.g. change "WHOLEFDS MKT 1024 SAN FRANCISCO CA" to "Whole Foods Market").
6. Classify each transaction into EXACTLY ONE of the following categories:
   {json.dumps(STANDARD_CATEGORIES)}
7. Identify Payment Method (e.g., "Amex Card", "Credit Card", "Debit Card", "Bank Transfer", "Cash", "UPI / Online").
8. Return ONLY a valid JSON array of objects with the exact schema:
[
  {{
    "date": "YYYY-MM-DD",
    "amount": 25.50,
    "category": "Food & Dining",
    "payment_method": "Amex Card",
    "description": "Starbucks Coffee"
  }}
]
"""

def normalize_date_string(date_raw):
    if not date_raw:
        return datetime.now().strftime("%Y-%m-%d")
    date_str = str(date_raw).strip().split('T')[0].split(' ')[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y", "%d-%m-%Y", "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d-%b-%Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    # Regex matching
    match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', str(date_raw))
    if match:
        y, m, d = match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    match2 = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', str(date_raw))
    if match2:
        m, d, y = match2.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return datetime.now().strftime("%Y-%m-%d")

def extract_text_from_pdf(file_stream_or_path):
    try:
        if hasattr(file_stream_or_path, 'seek'):
            file_stream_or_path.seek(0)
        reader = PdfReader(file_stream_or_path)
        text = ""
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += f"\n--- Page {i+1} ---\n" + page_text
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

def extract_text_from_excel(file_stream_or_path):
    # Try openpyxl first
    try:
        if hasattr(file_stream_or_path, 'seek'):
            file_stream_or_path.seek(0)
        import openpyxl
        wb = openpyxl.load_workbook(file_stream_or_path, data_only=True)
        text_lines = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            text_lines.append(f"\n--- Sheet: {sheet_name} ---")
            for row in ws.iter_rows(values_only=True):
                if any(row):
                    row_str = " | ".join(str(c) if c is not None else "" for c in row)
                    text_lines.append(row_str)
        if text_lines:
            return "\n".join(text_lines)
    except Exception as e:
        print(f"openpyxl failed: {e}")

    # Fallback to pandas
    try:
        if hasattr(file_stream_or_path, 'seek'):
            file_stream_or_path.seek(0)
        import pandas as pd
        excel_data = pd.read_excel(file_stream_or_path, sheet_name=None)
        text_lines = []
        for sheet_name, df in excel_data.items():
            text_lines.append(f"\n--- Sheet: {sheet_name} ---")
            text_lines.append(df.to_string(index=False))
        return "\n".join(text_lines)
    except Exception as e2:
        print(f"pandas failed: {e2}")
        return ""

def clean_json_response(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    
    # Try matching array first
    match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
            
    # Try matching object with items/transactions key
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ["transactions", "expenses", "items", "data"]:
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]
            # Single object wrapped in dict
            return [parsed]
    except Exception:
        pass
        
def get_gemini_api_key(passed_key=None):
    if passed_key and str(passed_key).strip():
        return str(passed_key).strip()
    
    for key_name in ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY"]:
        val = os.environ.get(key_name, "")
        if val and str(val).strip():
            return str(val).strip()
            
    # Check .env
    if os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() in ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY"]:
                            clean_v = v.strip().strip('"').strip("'")
                            if clean_v: 
                                return clean_v
        except Exception:
            pass
            
    # Check local .api_key file
    cfg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".api_key")
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r") as f:
                val = f.read().strip()
                if val: 
                    return val
        except Exception:
            pass
            
    return ""

def parse_statement(file_obj, filename="", custom_api_key=None):
    """
    Parses statement file using the Gemini API client.
    """
    ext = os.path.splitext(filename.lower())[1] if filename else ""
    api_key = get_gemini_api_key(custom_api_key)
    if not api_key:
        raise ValueError("Gemini API key is not configured. Please set your key in Settings or environment variables.")

    client = genai.Client(api_key=api_key)
    models_to_try = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.7-flash"]

    raw_response_text = ""
    last_error = None

    if ext == ".pdf":
        extracted_text = extract_text_from_pdf(file_obj)
        if not extracted_text or len(extracted_text.strip()) < 10:
            raise ValueError("Could not extract readable text from PDF statement.")
        
        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nHere is the raw text from the statement:\n\n{extracted_text}"
        for model_name in models_to_try:
            try:
                chat = client.chats.create(model=model_name)
                res = chat.send_message(prompt)
                raw_response_text = res.text
                if raw_response_text:
                    break
            except Exception as err:
                last_error = err
                continue

    elif ext in [".xlsx", ".xls"]:
        extracted_text = extract_text_from_excel(file_obj)
        if not extracted_text or len(extracted_text.strip()) < 10:
            raise ValueError("Could not extract readable tabular data from the Excel spreadsheet.")
        
        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nHere is the data from the Excel file ({filename}):\n\n{extracted_text}"
        for model_name in models_to_try:
            try:
                chat = client.chats.create(model=model_name)
                res = chat.send_message(prompt)
                raw_response_text = res.text
                if raw_response_text:
                    break
            except Exception as err:
                last_error = err
                continue

    elif ext in [".csv", ".txt"]:
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        
        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nHere is the statement content ({filename}):\n\n{content}"
        for model_name in models_to_try:
            try:
                chat = client.chats.create(model=model_name)
                res = chat.send_message(prompt)
                raw_response_text = res.text
                if raw_response_text:
                    break
            except Exception as err:
                last_error = err
                continue

    elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        file_bytes = file_obj.read()
        mime_type = "image/png" if ext == ".png" else "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/webp"
        
        image_part = types.Part.from_bytes(
            data=file_bytes,
            mime_type=mime_type
        )
        for model_name in models_to_try:
            try:
                chat = client.chats.create(model=model_name)
                res = chat.send_message([EXTRACTION_SYSTEM_PROMPT, image_part])
                raw_response_text = res.text
                if raw_response_text:
                    break
            except Exception as err:
                last_error = err
                continue
    else:
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nStatement Content:\n\n{content}"
        for model_name in models_to_try:
            try:
                chat = client.chats.create(model=model_name)
                res = chat.send_message(prompt)
                raw_response_text = res.text
                if raw_response_text:
                    break
            except Exception as err:
                last_error = err
                continue

    if not raw_response_text:
        raise ValueError(f"Failed to analyze statement with Gemini: {last_error}")

    parsed_transactions = clean_json_response(raw_response_text)
    
    valid_items = []
    if isinstance(parsed_transactions, list):
        for item in parsed_transactions:
            if not isinstance(item, dict):
                continue
            try:
                amt = float(item.get("amount", 0))
                if amt <= 0:
                    continue
                cat = str(item.get("category", "Miscellaneous")).strip()
                if cat not in STANDARD_CATEGORIES:
                    cat = "Miscellaneous"
                
                date_str = normalize_date_string(item.get("date"))
                desc = str(item.get("description", "Purchase")).strip()
                pay = str(item.get("payment_method", "Amex Card")).strip()
                
                valid_items.append({
                    "date": date_str,
                    "amount": round(amt, 2),
                    "category": cat,
                    "payment_method": pay,
                    "description": desc
                })
            except Exception:
                continue

    return valid_items

FINANCIAL_INSIGHTS_PROMPT = """
You are an elite, modern financial advisor and spending analyst.
Analyze the user's spending data, category breakdown, and monthly budget targets for the active month.

Provide a high-value, intelligent financial assessment:
1. "health_score": Integer 0 to 100 assessing overall budget health (100 = optimal, < 60 = high risk/overspending).
2. "status": One of "Excellent", "Healthy", "Caution", or "Critical".
3. "headline": A crisp, encouraging, punchy 1-sentence assessment of their financial discipline.
4. "observations": Array of 3-4 bullet points highlighting specific trends, top spend areas, and anomalies.
5. "recommendations": Array of 3 specific, actionable recommendations to reduce expenses and save money.
6. "alerts": Array of warning strings for categories that exceeded or are nearing their budget limit (empty array if none).
7. "projected_monthly_savings": A realistic estimated dollar amount ($) they could save by following your tips.

Return ONLY a valid JSON object matching this schema:
{
  "health_score": 85,
  "status": "Healthy",
  "headline": "Great control over fixed costs, with minor savings potential in Dining.",
  "observations": [
    "Your top expense category this month is Food & Dining ($320).",
    "You have used 48% of your overall monthly budget limit."
  ],
  "recommendations": [
    "Prepare meals at home 2 more days per week to save ~$120/mo.",
    "Review recurring subscription renewals in Entertainment."
  ],
  "alerts": [
    "Dining spend has reached 85% of its $400 budget allowance."
  ],
  "projected_monthly_savings": 140.00
}
"""

def generate_financial_insights(month_label, summary_data, expenses_data, custom_api_key=None):
    """
    Generates intelligent financial insights for the selected month using Gemini.
    """
    api_key = get_gemini_api_key(custom_api_key)
    if not api_key:
        raise ValueError("Gemini API key is not configured. Please set your key in Settings or environment variables.")

    client = genai.Client(api_key=api_key)
    models_to_try = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.7-flash"]

    # Prepare financial payload for Gemini
    payload = {
        "period": month_label,
        "total_spent": summary_data.get("current_month_spend", 0.0),
        "total_budget": summary_data.get("total_monthly_budget", 0.0),
        "remaining_budget": summary_data.get("remaining_budget", 0.0),
        "budget_usage_pct": summary_data.get("budget_usage_pct", 0.0),
        "daily_average": summary_data.get("daily_avg_spend", 0.0),
        "category_breakdown": summary_data.get("category_breakdown", []),
        "budget_comparison": summary_data.get("budget_comparison", []),
        "recent_expenses": expenses_data[:20] if expenses_data else []
    }

    prompt = f"{FINANCIAL_INSIGHTS_PROMPT}\n\nHere is the financial data for {month_label}:\n\n{json.dumps(payload, indent=2)}"

    raw_response_text = ""
    last_error = None

    for model_name in models_to_try:
        try:
            chat = client.chats.create(model=model_name)
            res = chat.send_message(prompt)
            raw_response_text = res.text
            if raw_response_text:
                break
        except Exception as err:
            last_error = err
            continue

    if not raw_response_text:
        raise ValueError(f"Failed to generate financial insights with Gemini: {last_error}")

    text = raw_response_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    try:
        return json.loads(text)
    except Exception:
        return {
            "health_score": 75,
            "status": "Healthy",
            "headline": f"Financial overview generated for {month_label}.",
            "observations": [
                f"Total spend for {month_label} is ${summary_data.get('current_month_spend', 0.0):.2f}.",
                f"Budget utilization is at {summary_data.get('budget_usage_pct', 0.0)}%."
            ],
            "recommendations": [
                "Continue tracking daily expenses to maintain budget limits.",
                "Review categories nearing 80% utilization."
            ],
            "alerts": [],
            "projected_monthly_savings": 50.00
        }
