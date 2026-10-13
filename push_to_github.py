"""
Helper script to push to GitHub using a GitHub Personal Access Token (PAT).
Usage:
    python push_to_github.py
"""

import sys
import getpass
import dulwich.porcelain as dp
from dulwich.repo import Repo

REPO_URL = "https://github.com/imranbeyan162-collab/tracker.git"

def main():
    print("=" * 60)
    print(" 🚀 Partner Tracker - Push to GitHub")
    print("=" * 60)
    print(f"Target Repository: {REPO_URL}\n")
    print("GitHub requires a Personal Access Token (classic or fine-grained) with 'repo' scope.")
    print("Create one at: https://github.com/settings/tokens\n")
    
    token = input("Enter your GitHub Personal Access Token (PAT): ").strip()
    if not token:
        print("[!] No token provided. Push cancelled.")
        return

    auth_url = f"https://{token}@github.com/imranbeyan162-collab/tracker.git"

    print("\n[*] Pushing to origin main...")
    try:
        dp.push(".", auth_url, "refs/heads/main")
        print("\n[+] SUCCESS! All files have been pushed to:")
        print(f"    https://github.com/imranbeyan162-collab/tracker")
    except Exception as e:
        print(f"\n[!] Push failed: {e}")

if __name__ == "__main__":
    main()
