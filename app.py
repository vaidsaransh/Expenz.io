import os
from flask import Flask, render_template, request, jsonify, send_file
import excel_manager
import gemini_parser

app = Flask(__name__)
app.config['SECRET_KEY'] = 'modern-expense-tracker-secret-key-2026'

# Ensure Excel file is initialized on startup
excel_manager.init_excel()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/summary', methods=['GET'])
def get_summary():
    try:
        month = request.args.get('month')
        stats = excel_manager.get_summary_stats(month=month)
        return jsonify({"success": True, "data": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    try:
        month = request.args.get('month')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        category = request.args.get('category')
        search = request.args.get('search')
        payment_method = request.args.get('payment_method')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))

        all_expenses = excel_manager.get_expenses(
            start_date=start_date,
            end_date=end_date,
            category=category,
            search=search,
            payment_method=payment_method,
            month=month
        )
        
        total_items = len(all_expenses)
        total_pages = max(1, (total_items + limit - 1) // limit)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_items = all_expenses[start_idx:end_idx]

        return jsonify({
            "success": True,
            "data": paginated_items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_items": total_items,
                "total_pages": total_pages
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/expenses', methods=['POST'])
def create_expense():
    try:
        data = request.get_json() or {}
        date = data.get('date')
        amount = data.get('amount')
        category = data.get('category')
        payment_method = data.get('payment_method', 'Credit Card')
        description = data.get('description', '').strip()

        if not date:
            return jsonify({"success": False, "error": "Date is required"}), 400
        if amount is None or float(amount) <= 0:
            return jsonify({"success": False, "error": "Amount must be greater than zero"}), 400
        if not category:
            return jsonify({"success": False, "error": "Category is required"}), 400

        new_expense = excel_manager.add_expense(
            date=date,
            amount=float(amount),
            category=category,
            payment_method=payment_method,
            description=description
        )
        return jsonify({"success": True, "data": new_expense, "message": "Expense logged successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/expenses/bulk', methods=['POST'])
def create_bulk_expenses():
    try:
        data = request.get_json() or {}
        items = data.get('items', [])
        if not items:
            return jsonify({"success": False, "error": "No items provided"}), 400

        added_records = excel_manager.bulk_add_expenses(items)
        imported_month = added_records[0]["date"][:7] if added_records and len(added_records[0].get("date", "")) >= 7 else None
        return jsonify({
            "success": True,
            "count": len(added_records),
            "data": added_records,
            "imported_month": imported_month,
            "message": f"Successfully imported {len(added_records)} expenses into Excel!"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/expenses/<expense_id>', methods=['PUT'])
def update_expense(expense_id):
    try:
        data = request.get_json() or {}
        date = data.get('date')
        amount = data.get('amount')
        category = data.get('category')
        payment_method = data.get('payment_method', 'Credit Card')
        description = data.get('description', '').strip()

        if not date or amount is None or not category:
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        success = excel_manager.update_expense(
            expense_id=expense_id,
            date=date,
            amount=float(amount),
            category=category,
            payment_method=payment_method,
            description=description
        )
        if success:
            return jsonify({"success": True, "message": "Expense updated successfully!"})
        else:
            return jsonify({"success": False, "error": "Expense not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/expenses/<expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    try:
        if str(expense_id).lower() in ['all', 'clear-all']:
            excel_manager.clear_all_expenses()
            return jsonify({"success": True, "message": "All expense records cleared from Excel!"})

        success = excel_manager.delete_expense(expense_id)
        if success:
            return jsonify({"success": True, "message": "Expense deleted successfully!"})
        else:
            return jsonify({"success": False, "error": "Expense not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/expenses/clear-all', methods=['POST', 'DELETE'])
def clear_all_expenses():
    try:
        excel_manager.clear_all_expenses()
        return jsonify({"success": True, "message": "All expenses have been reset and cleared from Excel!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/budgets', methods=['GET', 'POST'])
def manage_budgets():
    if request.method == 'GET':
        budgets = excel_manager.get_budgets()
        return jsonify({"success": True, "data": budgets})
    else:
        try:
            data = request.get_json() or {}
            budgets = data.get('budgets', {})
            excel_manager.save_budgets(budgets)
            return jsonify({"success": True, "message": "Budgets saved successfully!"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/categories', methods=['GET'])
def get_categories():
    categories = excel_manager.get_categories()
    return jsonify({"success": True, "data": categories})

@app.route('/api/upload-statement', methods=['POST'])
def upload_statement():
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "No selected file"}), 400

        # Parse with Gemini LLM
        parsed_transactions = gemini_parser.parse_statement(file, filename=file.filename)
        detected_month = parsed_transactions[0]["date"][:7] if parsed_transactions and len(parsed_transactions[0].get("date", "")) >= 7 else None
        
        return jsonify({
            "success": True,
            "filename": file.filename,
            "count": len(parsed_transactions),
            "detected_month": detected_month,
            "transactions": parsed_transactions
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/insights', methods=['POST', 'GET'])
def generate_insights():
    try:
        month = request.args.get('month') or (request.get_json() or {}).get('month')
        summary = excel_manager.get_summary_stats(month=month)
        expenses = excel_manager.get_expenses(month=summary.get("active_month"))
        
        insights = gemini_parser.generate_financial_insights(
            month_label=summary.get("active_month_label", "Selected Month"),
            summary_data=summary,
            expenses_data=expenses
        )
        return jsonify({
            "success": True,
            "period": summary.get("active_month_label"),
            "data": insights
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/download-excel')
def download_excel():
    excel_path = excel_manager.EXCEL_FILE
    if os.path.exists(excel_path):
        return send_file(
            excel_path,
            as_attachment=True,
            download_name="Expense_Budget_Tracker.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"🚀 Modern Expense & Budget Tracker running on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)

