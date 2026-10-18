import os
import sys

# Guarantee Vercel / serverless environment flag is set
os.environ["VERCEL"] = "1"

# Add project root directory to sys.path so app, database, templates, and static are resolved
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app import app


class VercelPathFix:
    """
    Translates Vercel Edge rewrite headers (HTTP_X_MATCHED_PATH, HTTP_X_FORWARDED_URI, etc.)
    into standard WSGI PATH_INFO so Flask routes match the user's actual requested URL.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path_candidate = None

        # Edge proxy headers providing the user's actual requested path
        for header_key in (
            "HTTP_X_MATCHED_PATH",
            "HTTP_X_FORWARDED_URI",
            "HTTP_X_VERCEL_FORWARDED_PATH",
            "HTTP_X_REAL_PATH",
            "REQUEST_URI",
        ):
            raw = environ.get(header_key, "")
            if raw:
                clean = raw.split("?")[0].strip()
                if clean and clean not in ("/api/index", "/api/index.py", "/api/index/", "/api"):
                    path_candidate = clean if clean.startswith("/") else "/" + clean
                    break

        if path_candidate:
            environ["PATH_INFO"] = path_candidate
        elif environ.get("PATH_INFO", "") in ("/api/index", "/api/index.py", "/api/index/", "/api"):
            environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathFix(app.wsgi_app)
