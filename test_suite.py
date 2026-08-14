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

    def test_06_filter_verification_and_live_excel(self):
        self.client.post('/api/expenses/clear-all')
        # Insert 3 test expenses across 2 categories and 2 months
        self.client.post('/api/expenses', json={"date": "2026-08-10", "amount": 50.0, "category": "Food & Dining", "description": "Burger"})
        self.client.post('/api/expenses', json={"date": "2026-08-12", "amount": 30.0, "category": "Transportation", "description": "Gas"})
        self.client.post('/api/expenses', json={"date": "2026-07-20", "amount": 100.0, "category": "Food & Dining", "description": "July Grocery"})

        # Verify month filter
        res_aug = self.client.get('/api/expenses?month=2026-08')
        data_aug = res_aug.get_json()
        self.assertEqual(len(data_aug["data"]), 2)

        res_jul = self.client.get('/api/expenses?month=2026-07')
        data_jul = res_jul.get_json()
        self.assertEqual(len(data_jul["data"]), 1)

        # Verify category filter
        res_cat = self.client.get('/api/expenses?category=Transportation')
        data_cat = res_cat.get_json()
        self.assertEqual(len(data_cat["data"]), 1)
        self.assertEqual(data_cat["data"][0]["category"], "Transportation")

        # Verify combined month + category filter
        res_combo = self.client.get('/api/expenses?month=2026-08&category=Food%20%26%20Dining')
        data_combo = res_combo.get_json()
        self.assertEqual(len(data_combo["data"]), 1)

        # Verify month=auto defaults to active month (August 2026 -> 2 items)
        res_auto = self.client.get('/api/expenses?month=auto')
        data_auto = res_auto.get_json()
        self.assertEqual(len(data_auto["data"]), 2)

        # Verify Excel file is updated live on disk directly
        import openpyxl
        wb = openpyxl.load_workbook(excel_manager.EXCEL_FILE, data_only=True)
        ws = wb["Expenses"]
        # Header + 3 rows = 4 rows
        self.assertEqual(ws.max_row, 4)

        # Clean up
        self.client.post('/api/expenses/clear-all')

    def test_07_ai_insights(self):
        # Add test expense
        self.client.post('/api/expenses', json={"date": "2026-08-10", "amount": 80.0, "category": "Food & Dining", "description": "Family Dinner"})
        
        res = self.client.post('/api/insights?month=2026-08')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("health_score", data["data"])
        self.assertIn("observations", data["data"])
        self.assertIn("recommendations", data["data"])

        # Clean up
        self.client.post('/api/expenses/clear-all')

    def test_08_multi_tenant_workspace_isolation(self):
        # User A logs an expense
        self.client.post('/api/expenses', 
            headers={"X-User-Id": "user_alice"},
            json={"date": "2026-08-01", "amount": 150.0, "category": "Shopping & Retail", "description": "Alice Shoes"}
        )
        
        # User B logs a different expense
        self.client.post('/api/expenses', 
            headers={"X-User-Id": "user_bob"},
            json={"date": "2026-08-02", "amount": 45.0, "category": "Food & Dining", "description": "Bob Pizza"}
        )

        # Verify Alice only sees Alice's expenses
        res_a = self.client.get('/api/expenses', headers={"X-User-Id": "user_alice"})
        data_a = res_a.get_json()
        self.assertEqual(data_a["pagination"]["total_items"], 1)
        self.assertEqual(data_a["data"][0]["description"], "Alice Shoes")

        # Verify Bob only sees Bob's expenses
        res_b = self.client.get('/api/expenses', headers={"X-User-Id": "user_bob"})
        data_b = res_b.get_json()
        self.assertEqual(data_b["pagination"]["total_items"], 1)
        self.assertEqual(data_b["data"][0]["description"], "Bob Pizza")

        # Clean up Alice and Bob ledgers
        self.client.post('/api/expenses/clear-all', headers={"X-User-Id": "user_alice"})
        self.client.post('/api/expenses/clear-all', headers={"X-User-Id": "user_bob"})

    def test_09_copilot_chat(self):
        # Log sample expense
        self.client.post('/api/expenses', 
            headers={"X-User-Id": "user_copilot_test"},
            json={"date": "2026-08-05", "amount": 65.0, "category": "Food & Dining", "description": "Italian Trattoria"}
        )

        res = self.client.post('/api/copilot/chat',
            headers={"X-User-Id": "user_copilot_test"},
            json={"message": "What is my top expense this month?", "history": [], "month": "2026-08"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("reply", data["data"])
        self.assertIn("suggested_followups", data["data"])

        # Clean up
        self.client.post('/api/expenses/clear-all', headers={"X-User-Id": "user_copilot_test"})

    def test_10_month_dependent_reset(self):
        uid = "user_month_reset_test"
        # Log expenses in July 2026 and August 2026
        self.client.post('/api/expenses', headers={"X-User-Id": uid},
            json={"date": "2026-07-15", "amount": 50.0, "category": "Food & Dining", "description": "July Lunch"}
        )
        self.client.post('/api/expenses', headers={"X-User-Id": uid},
            json={"date": "2026-08-10", "amount": 120.0, "category": "Shopping & Retail", "description": "August Shoes"}
        )
        self.client.post('/api/expenses', headers={"X-User-Id": uid},
            json={"date": "2026-08-20", "amount": 30.0, "category": "Transportation", "description": "August Train"}
        )

        # Clear ONLY August 2026
        res = self.client.post('/api/expenses/clear-all', headers={"X-User-Id": uid},
            json={"month": "2026-08"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["deleted_count"], 2)

        # Verify July expense still exists
        res_list = self.client.get('/api/expenses', headers={"X-User-Id": uid})
        data_list = res_list.get_json()
        self.assertEqual(data_list["pagination"]["total_items"], 1)
        self.assertEqual(data_list["data"][0]["description"], "July Lunch")

        # Now clear all
        res_all = self.client.post('/api/expenses/clear-all', headers={"X-User-Id": uid}, json={"month": "all"})
        self.assertEqual(res_all.status_code, 200)
        res_empty = self.client.get('/api/expenses', headers={"X-User-Id": uid})
        self.assertEqual(res_empty.get_json()["pagination"]["total_items"], 0)

if __name__ == '__main__':
    unittest.main()
