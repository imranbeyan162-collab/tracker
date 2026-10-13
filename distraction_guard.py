"""
Distraction Guard Daemon for Windows
Monitors active application window titles and processes.
When distracting apps (e.g., TikTok, Instagram, YouTube Shorts) are opened,
it automatically closes them so you stay focused on your goals.

Run with:
    python distraction_guard.py
or double-click run_distraction_guard.bat
"""

import sys
import os
import time
import subprocess
import ctypes
from ctypes import wintypes

# Common distracting window title keywords and process names
BLOCKED_KEYWORDS = ["tiktok", "tik tok", "instagram", "youtube shorts", "reels"]

user32 = ctypes.windll.user32

def get_window_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length > 0:
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value
    return ""

def close_window(hwnd):
    # WM_CLOSE = 0x0010
    user32.PostMessageW(hwnd, 0x0010, 0, 0)

def scan_and_close_distractions():
    closed_count = 0

    # Callback for EnumWindows
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_windows_callback(hwnd, lParam):
        nonlocal closed_count
        if user32.IsWindowVisible(hwnd):
            title = get_window_text(hwnd).lower()
            for blocked in BLOCKED_KEYWORDS:
                if blocked in title:
                    print(f"[!] DISTRACTION DETECTED: '{title}' -> Closing window...")
                    close_window(hwnd)
                    closed_count += 1
                    break
        return True

    cb = WNDENUMPROC(enum_windows_callback)
    user32.EnumWindows(cb, 0)
    return closed_count

def main():
    print("=" * 60)
    print(" 🛡️ FOCUS & DISTRACTION GUARD ACTIVE")
    print("=" * 60)
    print("Monitoring Windows for distracting apps (TikTok, Instagram, etc.)...")
    print("Keep this running in the background while working on goals.")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            scan_and_close_distractions()
            time.sleep(2)
        except KeyboardInterrupt:
            print("\nFocus Guard stopped.")
            break
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    main()
