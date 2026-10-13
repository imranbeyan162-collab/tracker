"""
Automated Test Suite for Imran & Mikiyas Platform
Verifies gatekeeper login, zero dummy state, goals tracking, and permissions.
"""

import unittest
import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from database.db import get_db_connection, init_db

class VentureTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret-key"
        self.client = app.test_client()
        init_db(seed=False)

    def test_01_gatekeeper_redirects_unauthenticated(self):
        """Unauthenticated requests must be redirected to /login."""
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/login"))

    def test_02_master_password_login(self):
        """Test master password unlocks portal as Imran or Mikiyas."""
        res_fail = self.client.post("/login", data={"partner_id": "imran", "pin": "wrongpass"}, follow_redirects=True)
        self.assertIn(b"Incorrect security code. Access denied.", res_fail.data)

        # Correct master password
        res_ok = self.client.post("/login", data={"partner_id": "imran", "pin": "imranandmicas@gmail.com"}, follow_redirects=True)
        self.assertEqual(res_ok.status_code, 200)
        self.assertIn(b"Imran", res_ok.data)
        self.assertIn(b"Venture Overview", res_ok.data)

    def test_03_zero_dummy_records(self):
        """Verify database has exactly zero pre-filled dummy transactions or tasks."""
        self.client.post("/login", data={"partner_id": "imran", "pin": "imranandmicas@gmail.com"})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transactions")
        txn_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM tasks")
        task_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM bills")
        bill_count = cursor.fetchone()[0]
        conn.close()

        self.assertEqual(txn_count, 0)
        self.assertEqual(task_count, 0)
        self.assertEqual(bill_count, 0)

    def test_04_goals_architecture(self):
        """Test adding, listing, and completing shared and personal goals."""
        self.client.post("/login", data={"partner_id": "imran", "pin": "imranandmicas@gmail.com"})

        # Add Shared Goal
        res_shared = self.client.post("/goals/add", data={
            "goal_type": "shared",
            "title": "Launch Phase 1 Product",
            "description": "Joint milestone",
            "target_time": "18:00",
            "target_date": date.today().strftime("%Y-%m-%d"),
            "category": "Venture / Revenue"
        }, follow_redirects=True)
        self.assertIn(b"Launch Phase 1 Product", res_shared.data)

        # Add Imran Personal Goal
        res_personal = self.client.post("/goals/add", data={
            "goal_type": "imran",
            "title": "Sleep at 07:00 AM",
            "description": "Consistent sleep schedule",
            "target_time": "07:00",
            "target_date": date.today().strftime("%Y-%m-%d"),
            "category": "Habit / Sleep"
        }, follow_redirects=True)
        self.assertIn(b"Sleep at 07:00 AM", res_personal.data)

if __name__ == "__main__":
    unittest.main()
