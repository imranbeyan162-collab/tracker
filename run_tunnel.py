import subprocess
import time
import re
import sys
import os

TUNNEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunnel_url.txt")

def start_tunnel():
    print("[*] Launching secure public tunnel for Partner Tracker...")
    cmd = [
        "ssh",
        "-R", "80:127.0.0.1:5000",
        "nokey@localhost.run",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3"
    ]
    
    while True:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding="utf-8", errors="replace")
            for line in proc.stdout:
                line_str = line.strip()
                if line_str:
                    try:
                        print(line_str)
                    except Exception:
                        pass
                # Look for https://....lhr.life
                match = re.search(r"https://[a-zA-Z0-9-]+\.lhr\.life", line_str)
                if match:
                    public_url = match.group(0)
                    with open(TUNNEL_FILE, "w", encoding="utf-8") as f:
                        f.write(public_url)
                    print("\n" + "=" * 65)
                    print(f"[+] LIVE GLOBAL PUBLIC URL: {public_url}")
                    print("=" * 65 + "\n")
            proc.wait()
            print("[!] Tunnel connection closed, restarting in 3 seconds...")
            time.sleep(3)
        except Exception as e:
            print(f"[!] Tunnel error: {e}, retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    start_tunnel()
