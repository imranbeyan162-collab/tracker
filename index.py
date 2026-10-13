import os
import sys

# Guarantee Vercel / serverless environment flag is set
os.environ["VERCEL"] = "1"

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from app import app
