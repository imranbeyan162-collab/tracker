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
    init_db(seed=False)
    print("[+] Database verified (Clean Slate).")
    print("------------------------------------------------------------")
    print("[*] Starting executive web server on http://127.0.0.1:5000 ...")
    print("    Press Ctrl+C to stop the server at any time.")
    import socket
    local_ip = "127.0.0.1"
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        pass
    print("------------------------------------------------------------")
    print(f" 💻 Laptop access:        http://127.0.0.1:5000")
    print(f" 📱 Mobile Phone (Wi-Fi): http://{local_ip}:5000")
    print("=" * 60)

    # Schedule browser opening after 1.2 seconds
    Timer(1.2, open_browser).start()
    
    app.run(host="0.0.0.0", port=5000, debug=False)

