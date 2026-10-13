"""
Script to initialize a clean database without any dummy data.
"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from database.db import DB_PATH, get_db_connection, create_clean_users

def reset_clean_db():
    # Remove existing database file if present to guarantee clean slate
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception:
            pass
            
    from database.db import init_db
    init_db(seed=False)
    print(f"[+] Clean database initialized at: {DB_PATH}")
    print("    Users: Imran & Mikiyas")
    print("    Default Master Password: imranandmicas@gmail.com")
    print("    Dummy records: 0 (Pure clean slate)")

if __name__ == "__main__":
    reset_clean_db()
