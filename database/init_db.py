"""
Standalone script to initialize or reset the SQLite database.
Run this script:
    python database/init_db.py
"""

import sys
import os

# Add parent directory to sys.path so database package can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from database.db import init_db, DB_PATH

if __name__ == "__main__":
    print(f"[*] Initializing Partner Tracker SQLite Database at:\n    {DB_PATH}")
    init_db(seed=True)
    print("[+] Database initialized successfully with default users and sample data!")
    print("    Partner A PIN: 111111")
    print("    Partner B PIN: 222222")
