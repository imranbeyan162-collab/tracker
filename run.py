"""
Partner Tracker - Convenient Launcher Script
"""

import os
import sys
import webbrowser
from threading import Timer

# Ensure working directory is this file's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from database.db import init_db
from app import app

def open_browser():
    """Automatically launches the user's default web browser to the app."""
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == "__main__":
    print("=" * 60)
    print(" 🤝 PARTNER TRACKER - Two-Person Money & Task Tracker")
    print("=" * 60)
    print("[*] Checking and initializing database...")
    init_db(seed=True)
    print("[+] Database verified.")
    print("------------------------------------------------------------")
    print(" 🔑 Partner A Default PIN: 111111")
    print(" 🔑 Partner B Default PIN: 222222")
    print("------------------------------------------------------------")
    print("[*] Starting web server on http://127.0.0.1:5000 ...")
    print("    Press Ctrl+C to stop the server at any time.")
    print("=" * 60)

    # Schedule browser opening after 1.2 seconds
    Timer(1.2, open_browser).start()
    
    app.run(host="127.0.0.1", port=5000, debug=False)
