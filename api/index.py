import os
import sys
import urllib.parse

# Guarantee Vercel / serverless environment flag is set
os.environ["VERCEL"] = "1"

# Add project root directory to sys.path so app, database, templates, and static are resolved
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app import app


class VercelPathFix:
    """
    Translates Vercel Edge rewrites (?path=$1 and edge headers) into standard WSGI PATH_INFO
    so Flask routes match the user's actual requested URL.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs = environ.get("QUERY_STRING", "")
        params = urllib.parse.parse_qs(qs)
        
        path_candidate = None

        # 1. Check query parameter passed from vercel.json rewrite: ?path=$1
        if "path" in params and params["path"]:
            p = params["path"][0]
            if p:
                path_candidate = p if p.startswith("/") else "/" + p
            else:
                path_candidate = "/"
                
        # 2. Check Vercel edge headers
        if not path_candidate or path_candidate in ("/api/index", "/api/index.py", "/api/index/", "/api"):
            for header_key in (
                "HTTP_X_MATCHED_PATH",
                "HTTP_X_FORWARDED_URI",
                "HTTP_X_VERCEL_FORWARDED_PATH",
                "HTTP_X_REAL_PATH",
                "REQUEST_URI",
            ):
                h_val = environ.get(header_key, "")
                if h_val:
                    clean = h_val.split("?")[0].strip()
                    if clean and clean not in ("/api/index", "/api/index.py", "/api/index/", "/api"):
                        path_candidate = clean if clean.startswith("/") else "/" + clean
                        break

        if path_candidate:
            environ["PATH_INFO"] = path_candidate
        elif environ.get("PATH_INFO", "") in ("/api/index", "/api/index.py", "/api/index/", "/api"):
            environ["PATH_INFO"] = "/"

        # Remove internal ?path= from QUERY_STRING so Flask request.args is clean
        if "path" in params:
            clean_params = {k: v for k, v in params.items() if k != "path"}
            environ["QUERY_STRING"] = urllib.parse.urlencode(clean_params, doseq=True)

        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathFix(app.wsgi_app)
