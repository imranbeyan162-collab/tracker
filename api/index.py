import os
import sys
import urllib.parse
import json

# Guarantee Vercel / serverless environment flag is set
os.environ["VERCEL"] = "1"

# Add project root directory to sys.path so app, database, templates, and static are resolved
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app import app

class VercelPathFix:
    """
    Translates Vercel rewrite parameter (?path=/route) into standard WSGI PATH_INFO
    so Flask routes match the user's actual requested URL.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # Immediate diagnostic endpoint to inspect WSGI environment
        qs = environ.get("QUERY_STRING", "")
        params = urllib.parse.parse_qs(qs)
        
        if environ.get("PATH_INFO") == "/debug" or params.get("path") == ["/debug"] or environ.get("HTTP_X_DEBUG") == "1":
            status = "200 OK"
            headers = [("Content-Type", "application/json")]
            start_response(status, headers)
            info = {
                "REQUEST_METHOD": environ.get("REQUEST_METHOD"),
                "PATH_INFO": environ.get("PATH_INFO"),
                "QUERY_STRING": qs,
                "CONTENT_TYPE": environ.get("CONTENT_TYPE"),
                "CONTENT_LENGTH": environ.get("CONTENT_LENGTH"),
                "HTTP_X_MATCHED_PATH": environ.get("HTTP_X_MATCHED_PATH"),
                "HTTP_X_FORWARDED_URI": environ.get("HTTP_X_FORWARDED_URI"),
                "HTTP_COOKIE": environ.get("HTTP_COOKIE"),
            }
            return [json.dumps(info, indent=2).encode("utf-8")]

        if "path" in params and params["path"]:
            orig_path = params["path"][0]
            if not orig_path.startswith("/"):
                orig_path = "/" + orig_path
            environ["PATH_INFO"] = orig_path
        elif environ.get("PATH_INFO", "") in ("/api/index", "/api/index/"):
            environ["PATH_INFO"] = "/"
            
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFix(app.wsgi_app)
