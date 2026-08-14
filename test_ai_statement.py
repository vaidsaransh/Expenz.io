import io
import unittest
import gemini_parser
import excel_manager
from app import app

SAMPLE_AMEX_STATEMENT = """
AMERICAN EXPRESS CARD STATEMENT
Account Ending: -1004
Statement Period: Jul 12, 2026 - Aug 11, 2026

TRANSACTIONS:
Date       Description                               Amount
07/15/2026 WHOLEFDS SOMA 1024 SAN FRANCISCO CA       $84.30
07/18/2026 UBER TRIP HELP.UBER.COM CA                $28.50
07/22/2026 APPLE.COM/BILL 800-692-7753 CA            $9.99
07/25/2026 CHEVRON 0092384 SAN FRANCISCO CA          $45.00
07/29/2026 BLUE BOTTLE COFFEE SAN FRANCISCO CA       $14.25
08/02/2026 AUTOPAY PAYMENT RECEIVED - THANK YOU     -$350.00
08/05/2026 CVS PHARMACY #9382 SAN FRANCISCO CA       $32.10
08/08/2026 TRADER JOE'S #540 SAN FRANCISCO CA        $62.40
"""

class TestAIStatementParser(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_gemini_parse_statement(self):
        file_obj = io.BytesIO(SAMPLE_AMEX_STATEMENT.encode('utf-8'))
        transactions = gemini_parser.parse_statement(file_obj, filename="amex_statement.txt")
        print(f"\n[AI Result] Parsed {len(transactions)} transactions:")
        for t in transactions:
            print(f"  -> {t['date']} | {t['category']} | {t['amount']} | {t['description']} ({t['payment_method']})")
        
        self.assertGreater(len(transactions), 0)
        # Verify autopay payment received was ignored
        for t in transactions:
            self.assertNotIn("AUTOPAY", t["description"].upper())
            self.assertGreater(t["amount"], 0)

    def test_api_upload_statement_and_bulk_import(self):
        file_obj = io.BytesIO(SAMPLE_AMEX_STATEMENT.encode('utf-8'))
        res = self.client.post('/api/upload-statement', data={
            'file': (file_obj, 'amex_statement.txt')
        }, content_type='multipart/form-data')

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertGreater(data["count"], 0)

        # Test bulk import into Excel
        bulk_res = self.client.post('/api/expenses/bulk', json={
            "items": data["transactions"]
        })
        self.assertEqual(bulk_res.status_code, 200)
        bulk_data = bulk_res.get_json()
        self.assertTrue(bulk_data["success"])
        print(f"[Bulk Import Result] {bulk_data['message']}")

    def test_xlsx_statement_upload(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Statement"
        ws.append(["Transaction Date", "Details", "Category", "Amount ($)"])
        ws.append(["2026-08-01", "Delta Airlines Flight Booking", "Travel", 280.50])
        ws.append(["2026-08-03", "Marriott Hotel Stay", "Lodging", 195.00])
        ws.append(["2026-08-06", "PAYMENT THANK YOU - WEB", "Payment", -475.50])
        ws.append(["2026-08-07", "Lyft Ride Downtown", "Transport", 24.20])
        
        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)

        res = self.client.post('/api/upload-statement', data={
            'file': (bio, 'bank_statement.xlsx')
        }, content_type='multipart/form-data')

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        print(f"\n[XLSX Test Result] Extracted {data['count']} transactions from .xlsx:")
        for t in data["transactions"]:
            print(f"  -> {t['date']} | {t['category']} | {t['amount']} | {t['description']}")
        self.assertGreater(data["count"], 0)

if __name__ == '__main__':
    unittest.main()
