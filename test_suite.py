import unittest
import json
import os
import excel_manager
from app import app

class TestExpenseTracker(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        excel_manager.init_excel()

    def test_01_excel_init(self):
        self.assertTrue(os.path.exists(excel_manager.EXCEL_FILE))
        categories = excel_manager.get_categories()
        self.assertGreater(len(categories), 0)
        budgets = excel_manager.get_budgets()
        self.assertGreater(len(budgets), 0)

    def test_02_add_and_get_expense(self):
        res = self.client.post('/api/expenses', json={
            "date": "2026-08-13",
            "amount": 42.50,
            "category": "Food & Dining",
            "payment_method": "Credit Card",
            "description": "Test Dinner at Bistro"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        exp_id = data["data"]["id"]

        # Fetch and verify
        res_list = self.client.get('/api/expenses?search=Test%20Dinner')
        data_list = res_list.get_json()
        self.assertTrue(data_list["success"])
        self.assertTrue(any(e["id"] == exp_id for e in data_list["data"]))

        # Clean up test item
        del_res = self.client.delete(f'/api/expenses/{exp_id}')
        self.assertEqual(del_res.status_code, 200)

    def test_03_summary_stats(self):
        res = self.client.get('/api/summary')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        stats = data["data"]
        self.assertIn("current_month_spend", stats)
        self.assertIn("category_breakdown", stats)
        self.assertIn("timeline", stats)
        self.assertIn("budget_comparison", stats)

    def test_04_download_excel(self):
        res = self.client.get('/download-excel')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_05_clear_all_expenses(self):
        # Add a temporary expense
        self.client.post('/api/expenses', json={
            "date": "2026-08-13",
            "amount": 10.00,
            "category": "Food & Dining",
            "payment_method": "Cash",
            "description": "Temp snack"
        })
        # Clear all
        res = self.client.post('/api/expenses/clear-all')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Check that expenses count is 0
        res_list = self.client.get('/api/expenses')
        data_list = res_list.get_json()
        self.assertEqual(len(data_list["data"]), 0)

if __name__ == '__main__':
    unittest.main()
