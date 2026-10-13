import os
import sys

# Guarantee Vercel / serverless environment flag is set
os.environ["VERCEL"] = "1"

# Add project root directory to sys.path so app, database, templates, and static are resolved
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from app import app

    class VercelPathMiddleware:
        def __init__(self, wsgi_app):
            self.wsgi_app = wsgi_app

        def __call__(self, environ, start_response):
            matched = environ.get('HTTP_X_MATCHED_PATH')
            if matched:
                environ['PATH_INFO'] = matched
            elif environ.get('PATH_INFO', '').startswith('/api/index'):
                subpath = environ['PATH_INFO'][len('/api/index'):]
                environ['PATH_INFO'] = subpath if subpath else '/'
            return self.wsgi_app(environ, start_response)

    app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
except Exception as e:
    import traceback
    from flask import Flask
    app = Flask(__name__)
    err_trace = traceback.format_exc()
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def catch_all(path):
        return f"<h1>Deployment Diagnostics</h1><pre>{err_trace}</pre>", 500


