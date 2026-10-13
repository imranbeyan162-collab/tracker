"""
Automated Test Suite for Partner Tracker
Verifies authentication, financial tracking, task workflows, CSV export, and penalty triggers.
"""

import unittest
import os
import sys
from datetime import date, timedelta

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from database.db import get_db_connection, init_db

class PartnerTrackerTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret-key"
        self.client = app.test_client()
        init_db(seed=True)

    def test_01_homepage_renders(self):
        """Test home dashboard renders with summary metrics."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Business Dashboard", response.data)
        self.assertIn(b"Partner A", response.data)
        self.assertIn(b"Partner B", response.data)

    def test_02_read_only_access(self):
        """Test that unauthenticated users can view money and tasks in read-only mode."""
        res_money = self.client.get("/money/partner_a")
        self.assertEqual(res_money.status_code, 200)
        self.assertIn(b"Read-Only Mode", res_money.data)

        res_tasks = self.client.get("/tasks/partner_a")
        self.assertEqual(res_tasks.status_code, 200)
        self.assertIn(b"Read-Only View", res_tasks.data)

    def test_03_partner_login_and_logout(self):
        """Test authentication using hashed PIN code."""
        # Incorrect PIN
        res_fail = self.client.post("/login", data={"partner_id": "partner_a", "pin": "999999"}, follow_redirects=True)
        self.assertIn(b"Incorrect PIN code", res_fail.data)

        # Correct PIN
        res_ok = self.client.post("/login", data={"partner_id": "partner_a", "pin": "111111"}, follow_redirects=True)
        self.assertIn(b"Welcome back, Partner A", res_ok.data)

        # Logout
        res_logout = self.client.get("/logout", follow_redirects=True)
        self.assertIn(b"viewing (read-only) mode", res_logout.data)

    def test_04_money_transaction_workflow(self):
        """Test adding, editing, and deleting a money transaction with authentication."""
        # Login as Partner A
        self.client.post("/login", data={"partner_id": "partner_a", "pin": "111111"})

        today_str = date.today().strftime("%Y-%m-%d")
        # Add Income
        res_add = self.client.post("/money/add", data={
            "partner_id": "partner_a",
            "date": today_str,
            "type": "Income",
            "category": "Affiliate Commission",
            "amount": "275.50",
            "note": "Online referral payout"
        }, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)
        self.assertIn(b"Affiliate Commission", res_add.data)

        # Verify in DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM transactions WHERE category = 'Affiliate Commission'")
        txn = cursor.fetchone()
        self.assertIsNotNone(txn)
        txn_id = txn["id"]

        # Edit entry
        res_edit = self.client.post("/money/edit", data={
            "partner_id": "partner_a",
            "txn_id": txn_id,
            "date": today_str,
            "type": "Income",
            "category": "Affiliate Commission Bonus",
            "amount": "300.00",
            "note": "Updated amount"
        }, follow_redirects=True)
        self.assertIn(b"Affiliate Commission Bonus", res_edit.data)

        # Delete entry
        res_del = self.client.post(f"/money/delete/{txn_id}", data={"partner_id": "partner_a"}, follow_redirects=True)
        self.assertIn(b"Transaction deleted", res_del.data)
        conn.close()

    def test_05_input_validation(self):
        """Test validation rejects negative or invalid amounts."""
        self.client.post("/login", data={"partner_id": "partner_a", "pin": "111111"})
        res = self.client.post("/money/add", data={
            "partner_id": "partner_a",
            "date": date.today().strftime("%Y-%m-%d"),
            "type": "Expense",
            "category": "Invalid Test",
            "amount": "-50.00",
            "note": "Bad amount"
        }, follow_redirects=True)
        self.assertIn(b"Amount must be greater than zero", res.data)

    def test_06_csv_export(self):
        """Test exporting transactions to CSV."""
        res_a = self.client.get("/export-csv?user_id=partner_a")
        self.assertEqual(res_a.status_code, 200)
        self.assertEqual(res_a.mimetype, "text/csv")
        self.assertIn(b"Partner A", res_a.data)

        res_comb = self.client.get("/export-csv?user_id=combined")
        self.assertEqual(res_comb.status_code, 200)
        self.assertIn(b"Partner B", res_comb.data)

    def test_07_bill_tracking(self):
        """Test adding and toggling bill paid/unpaid status."""
        self.client.post("/login", data={"partner_id": "partner_b", "pin": "222222"})
        res_add = self.client.post("/bills/add", data={
            "partner_id": "partner_b",
            "name": "Figma Pro Subscription",
            "amount": "15.00",
            "due_date": (date.today() + timedelta(days=10)).strftime("%Y-%m-%d"),
            "recurring_interval": "Monthly"
        }, follow_redirects=True)
        self.assertIn(b"Figma Pro Subscription", res_add.data)

    def test_08_task_and_penalty_accountability(self):
        """Test weekly task addition, toggling, and penalty system."""
        self.client.post("/login", data={"partner_id": "partner_a", "pin": "111111"})
        today = date.today()
        curr_week = f"{today.year}-W{today.isocalendar()[1]:02d}"

        # Add task
        res_task = self.client.post("/tasks/add", data={
            "partner_id": "partner_a",
            "week_id": curr_week,
            "title": "Inventory physical audit",
            "details": "Count all boxes",
            "due_date": today.strftime("%Y-%m-%d")
        }, follow_redirects=True)
        self.assertIn(b"Inventory physical audit", res_task.data)

        # Check penalties page
        res_pen = self.client.get("/penalties")
        self.assertEqual(res_pen.status_code, 200)
        self.assertIn(b"Accountability &amp; Consequence Board", res_pen.data)

if __name__ == "__main__":
    unittest.main()
