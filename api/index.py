import os
import sys

# Guarantee Vercel / serverless environment flag is set
os.environ["VERCEL"] = "1"

# Add project root directory to sys.path so app, database, templates, and static are resolved
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app import app
