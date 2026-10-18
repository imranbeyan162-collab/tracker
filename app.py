"""
Imran & Mikiyas Venture Management Platform
Includes strict privacy gates, AI proof verification, PWA mobile integration,
and scheduled reminder notifications.
"""

import os
import io
import csv
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, Response, send_from_directory, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import (
    get_db_connection, init_db, check_and_apply_penalties,
    calculate_task_streak, get_user_financial_totals, get_chart_data,
    get_private_goals, get_private_tasks, get_all_categorized_goals,
    get_workspace_tasks, sync_db
)
from ai_verifier import verify_goal_evidence

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "imran_mikiyas_venture_secure_key_2026")

is_serverless = bool(
    os.environ.get("VERCEL")
    or os.environ.get("VERCEL_ENV")
    or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    or os.environ.get("LAMBDA_TASK_ROOT")
    or not os.access(os.path.dirname(os.path.abspath(__file__)), os.W_OK)
)

# Directory for proof evidence uploads
if is_serverless:
    UPLOAD_FOLDER = "/tmp/uploads/proofs"
else:
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", "proofs")

try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except Exception:
    pass

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    SESSION_COOKIE_NAME="tracker_session",
    SESSION_COOKIE_SECURE=is_serverless,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_PATH="/",
    PERMANENT_SESSION_LIFETIME=timedelta(days=60),
)

# Ensure clean database initialization
init_db(seed=False)


# Master Passwords (never displayed on screen)
DEFAULT_MASTER_PASSWORDS = [
    "imran&mikiyas@gmail",
    "imran&mikiyas@gmail.com",
    "imranandmicas@gmail.com",
    "imranandmikiyas@gmail.com",
    "imranandmikiyas@gmail",
    "imran&micas@gmail.com",
    "imran & mikiyas",
    "imran and mikiyas",
    "imranandmicas",
    "imran&mikiyas",
]


@app.before_request
def require_authentication_gate():
    """Gatekeeper: Blocks unauthenticated traffic, allowing public assets and login requests."""
    # Always allow static files, manifest, sw.js, and favicon
    if request.endpoint == "static" or request.path.startswith(("/static/", "/public/")):
        return None

    allowed_exact = (
        "/", "/index", "/login", "/login/", "/favicon.ico", "/manifest.json", "/sw.js",
        "/api/index", "/api/index/", "/api/index.py", "/debug"
    )
    if request.path in allowed_exact or request.endpoint in ("login", "debug_endpoint", "index"):
        return None

    # Dual-redundancy: Check signed session cookie or persistent partner cookie
    user = session.get("logged_in_user") or request.cookies.get("partner_user")
    if user in ("imran", "mikiyas"):
        if not session.get("logged_in_user"):
            session["logged_in_user"] = user
            session.permanent = True
        return None

    # If POST contains login credentials on any rewritten route, route straight to login handler
    if request.method == "POST":
        has_pin = False
        if request.is_json:
            j = request.get_json(silent=True) or {}
            has_pin = bool(j.get("pin") or j.get("password"))
        elif request.form.get("pin") or request.form.get("password"):
            has_pin = True
        if has_pin:
            return None

    return redirect(url_for("login"))




@app.context_processor
def inject_globals():
    """Injects current user and pending alerts into all templates."""
    today_str = date.today().strftime("%Y-%m-%d")
    current_user = None
    logged_id = session.get("logged_in_user")
    
    conn = get_db_connection()
    check_and_apply_penalties(conn)

    if logged_id:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (logged_id,))
        current_user = cursor.fetchone()

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM penalties WHERE status = 'Pending'")
    total_pending_penalties = cursor.fetchone()[0]
    conn.close()

    return {
        "current_user": current_user,
        "total_pending_penalties": total_pending_penalties,
        "today_str": today_str
    }


# ============================================================================
# PWA Routes (Mobile Installation)
# ============================================================================

@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")

@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

@app.route("/static/<path:filename>")
def serve_static_asset(filename):
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    return send_from_directory(static_dir, filename)

@app.route("/static/uploads/proofs/<path:filename>")
@app.route("/uploads/proofs/<path:filename>")
def serve_proof_upload(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)




# ============================================================================
# Security Gatekeeper & Login
# ============================================================================

def handle_login_request():
    """Unified handler for all authentication requests regardless of rewritten route."""
    user = session.get("logged_in_user") or request.cookies.get("partner_user")
    if user in ("imran", "mikiyas") and request.method == "GET":
        if not session.get("logged_in_user"):
            session["logged_in_user"] = user
            session.permanent = True
        return redirect("/tasks")

    if request.method == "GET":
        return render_template("login.html")

    # Parse POST payload (supports application/json, form data, and raw data)
    json_data = request.get_json(silent=True) if request.is_json else None
    if not json_data and request.data:
        try:
            import json as _json
            json_data = _json.loads(request.data.decode("utf-8"))
        except Exception:
            json_data = None

    partner_id = (json_data.get("partner_id") if json_data else request.form.get("partner_id")) or "imran"
    pin = ""
    if json_data:
        pin = json_data.get("pin") or json_data.get("password") or ""
    if not pin:
        pin = request.form.get("pin") or request.form.get("password") or ""
    pin = str(pin).strip()

    is_json_client = request.is_json or (
        request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html
    )

    if not pin:
        if is_json_client:
            return jsonify({"success": False, "error": "Password required to access workspace."}), 400
        flash("Password required to access workspace.", "danger")
        return render_template("login.html")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (partner_id,))
    user_row = cursor.fetchone()
    conn.close()

    is_master_match = any(pin.lower() == p.lower() for p in DEFAULT_MASTER_PASSWORDS)
    is_hash_match = user_row and check_password_hash(user_row["pin_hash"], pin)

    if is_master_match or is_hash_match:
        session["logged_in_user"] = partner_id
        session.permanent = True
        flash(f"Workspace unlocked. Welcome, {user_row['name'] if user_row else partner_id.capitalize()}.", "success")

        if is_json_client:
            resp = jsonify({"success": True, "redirect": "/tasks"})
        else:
            resp = redirect("/tasks")

        resp.set_cookie(
            "partner_user",
            partner_id,
            max_age=60 * 60 * 24 * 60,
            path="/",
            samesite="Lax",
            secure=is_serverless,
            httponly=False,
        )
        return resp
    else:
        if is_json_client:
            return jsonify({"success": False, "error": "Incorrect security code. Access denied."}), 401
        flash("Incorrect security code. Access denied.", "danger")
        return render_template("login.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Access portal login asking for the private password."""
    return handle_login_request()


@app.errorhandler(404)
def page_not_found(e):
    return jsonify({
        "error": "404 Not Found",
        "path": request.path,
        "full_path": request.full_path,
        "environ_path_info": request.environ.get("PATH_INFO"),
        "headers": {k: str(v) for k, v in request.environ.items() if k.startswith("HTTP_") or "URI" in k or "PATH" in k}
    }), 404


@app.route("/debug")
def debug_endpoint():
    """Diagnostic endpoint to inspect environment and routing."""
    return jsonify({
        "status": "ok",
        "method": request.method,
        "path": request.path,
        "full_path": request.full_path,
        "cookies": dict(request.cookies),
        "session_user": session.get("logged_in_user"),
        "partner_cookie": request.cookies.get("partner_user"),
        "environ": {k: str(request.environ.get(k)) for k in (
            "PATH_INFO", "SCRIPT_NAME", "REQUEST_URI", "QUERY_STRING",
            "HTTP_X_FORWARDED_URI", "HTTP_X_MATCHED_PATH"
        ) if k in request.environ}
    })



@app.route("/logout")
def logout():
    session.pop("logged_in_user", None)
    flash("Session terminated. Workspace locked.", "info")
    resp = redirect(url_for("login"))
    resp.delete_cookie("partner_user", path="/")
    return resp



@app.route("/switch-partner", methods=["POST"])
def switch_partner():
    target_id = request.form.get("partner_id")
    if target_id in ("imran", "mikiyas"):
        session["logged_in_user"] = target_id
        flash(f"Switched partner context to {target_id.capitalize()}.", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/change-pin", methods=["POST"])
def change_pin():
    logged_id = session.get("logged_in_user")
    current_pin = request.form.get("current_pin", "").strip()
    new_pin = request.form.get("new_pin", "").strip()
    confirm_pin = request.form.get("confirm_pin", "").strip()

    if not current_pin or not new_pin or not confirm_pin:
        flash("All fields are required.", "danger")
        return redirect(url_for("settings_view"))

    if new_pin != confirm_pin:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("settings_view"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT pin_hash FROM users WHERE id = ?", (logged_id,))
    user = cursor.fetchone()

    is_master_match = any(current_pin.lower() == p.lower() for p in DEFAULT_MASTER_PASSWORDS)
    is_hash_match = user and check_password_hash(user["pin_hash"], current_pin)

    if not (is_master_match or is_hash_match):
        conn.close()
        flash("Current password verification failed.", "danger")
        return redirect(url_for("settings_view"))

    new_hash = generate_password_hash(new_pin)
    cursor.execute("UPDATE users SET pin_hash = ? WHERE id = ?", (new_hash, logged_id))
    conn.commit()
    conn.close()

    flash("Password updated successfully.", "success")
    return redirect(url_for("settings_view"))


# ============================================================================
# Overview Dashboard
# ============================================================================

@app.route("/")
@app.route("/index")
def index():
    if not (session.get("logged_in_user") or request.cookies.get("partner_user")):
        return handle_login_request()
    return tasks_board()


# ============================================================================
# Goals Architecture (Strict Privacy & AI Proof Validation)
# ============================================================================

@app.route("/goals")
def goals_view():
    """Venture & Personal Goals Hub."""
    viewer_id = session.get("logged_in_user", "imran")
    conn = get_db_connection()
    categorized = get_all_categorized_goals(conn)
    conn.close()

    return render_template(
        "goals.html",
        active_page="goals",
        shared_goals=categorized["shared"],
        imran_goals=categorized["imran"],
        mikiyas_goals=categorized["mikiyas"],
        viewer_id=viewer_id
    )


@app.route("/goals/add", methods=["POST"])
def add_goal():
    viewer_id = session.get("logged_in_user", "imran")
    goal_type = request.form.get("goal_type", "shared")
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("goals_view")

    if goal_type in ("shared", "imran", "mikiyas"):
        actual_type = goal_type
    else:
        actual_type = viewer_id

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    target_time = request.form.get("target_time", "").strip()
    target_date = request.form.get("target_date", "").strip()
    category = request.form.get("category", "General")

    if not title:
        flash("Goal title is required.", "danger")
        return redirect(redirect_to)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO goals (goal_type, title, description, target_time, target_date, category, is_completed, reminder_enabled)
    VALUES (?, ?, ?, ?, ?, ?, 0, 1)
    """, (actual_type, title, description, target_time, target_date, category))
    conn.commit()
    conn.close()

    flash(f"Goal '{title}' registered.", "success")
    return redirect(redirect_to)


@app.route("/goals/verify-proof/<int:goal_id>", methods=["POST"])
def verify_goal_proof(goal_id):
    """
    AI GOAL AUDIT:
    Accepts uploaded screenshot/photo proof and description.
    AI evaluates whether proof matches goal criteria before approving.
    """
    proof_text = request.form.get("proof_text", "").strip()
    file = request.files.get("proof_image")
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("goals_view")

    image_rel_path = None
    image_full_path = None

    if file and file.filename:
        filename = secure_filename(f"goal_{goal_id}_{int(datetime.now().timestamp())}_{file.filename}")
        image_full_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(image_full_path)
        image_rel_path = f"/static/uploads/proofs/{filename}"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
    goal = cursor.fetchone()

    if not goal:
        conn.close()
        flash("Goal not found.", "danger")
        return redirect(redirect_to)

    # Run AI Validator
    is_approved, feedback = verify_goal_evidence(
        goal["title"],
        goal["description"],
        proof_text,
        image_full_path
    )

    new_completed = 1 if is_approved else 0
    ai_status = "Approved" if is_approved else "Rejected"

    cursor.execute("""
    UPDATE goals 
    SET proof_image = COALESCE(?, proof_image),
        proof_text = ?,
        ai_verified = ?,
        ai_status = ?,
        ai_feedback = ?,
        is_completed = ?
    WHERE id = ?
    """, (image_rel_path, proof_text, 1 if is_approved else 0, ai_status, feedback, new_completed, goal_id))
    conn.commit()
    conn.close()

    if is_approved:
        flash(f"AI VERIFICATION PASSED: {feedback}", "success")
    else:
        flash(f"AI VERIFICATION REJECTED: {feedback}", "danger")

    return redirect(redirect_to)


@app.route("/goals/toggle/<int:goal_id>", methods=["POST"])
def toggle_goal_status(goal_id):
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("goals_view")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE goals SET is_completed = 1 - is_completed WHERE id = ?", (goal_id,))
    conn.commit()
    conn.close()
    return redirect(redirect_to)


@app.route("/goals/delete/<int:goal_id>", methods=["POST"])
def delete_goal(goal_id):
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("goals_view")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    conn.commit()
    conn.close()
    flash("Goal removed.", "info")
    return redirect(redirect_to)


# ============================================================================
# Tasks Workspace (Linear-style Quick Add, Instant Filters & AI Verification)
# ============================================================================

@app.route("/tasks")
def tasks_board():
    viewer_id = session.get("logged_in_user", "imran")
    tab = request.args.get("tab", "all")

    conn = get_db_connection()
    today_str = date.today().strftime("%Y-%m-%d")
    streak_count = calculate_task_streak(conn, viewer_id)

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks ORDER BY is_done ASC, due_date ASC, id DESC")
    all_raw_tasks = cursor.fetchall()
    conn.close()

    total_count = len(all_raw_tasks)
    done_count = sum(1 for t in all_raw_tasks if t["is_done"])
    rate = int((done_count / total_count * 100)) if total_count > 0 else 0

    counts = {
        "all": total_count,
        "today": sum(1 for t in all_raw_tasks if t["due_date"] == today_str and not t["is_done"]),
        "shared": sum(1 for t in all_raw_tasks if (t["task_type"] == "shared" or t["assigned_to"] == "shared")),
        "imran": sum(1 for t in all_raw_tasks if (t["assigned_to"] == "imran" or (t["user_id"] == "imran" and t["assigned_to"] != "shared" and t["task_type"] != "shared"))),
        "mikiyas": sum(1 for t in all_raw_tasks if (t["assigned_to"] == "mikiyas" or (t["user_id"] == "mikiyas" and t["assigned_to"] != "shared" and t["task_type"] != "shared"))),
        "completed": done_count
    }

    if tab == "today":
        tasks = [t for t in all_raw_tasks if t["due_date"] == today_str]
    elif tab == "shared":
        tasks = [t for t in all_raw_tasks if (t["task_type"] == "shared" or t["assigned_to"] == "shared")]
    elif tab == "imran":
        tasks = [t for t in all_raw_tasks if (t["assigned_to"] == "imran" or (t["user_id"] == "imran" and t["assigned_to"] != "shared" and t["task_type"] != "shared"))]
    elif tab == "mikiyas":
        tasks = [t for t in all_raw_tasks if (t["assigned_to"] == "mikiyas" or (t["user_id"] == "mikiyas" and t["assigned_to"] != "shared" and t["task_type"] != "shared"))]
    elif tab == "completed":
        tasks = [t for t in all_raw_tasks if t["is_done"]]
    else:
        tasks = all_raw_tasks

    return render_template(
        "tasks.html",
        active_page="tasks",
        active_tab=tab,
        tasks=tasks,
        counts=counts,
        stats={"done_count": done_count, "total_count": total_count, "rate": rate},
        streak_count=streak_count,
        today_str=today_str,
        viewer_id=viewer_id
    )


@app.route("/tasks/<partner_id>")
def tasks_view(partner_id):
    """Alias pointing to partner-specific tasks filter."""
    if partner_id in ("imran", "mikiyas", "shared", "today", "all", "completed"):
        return redirect(url_for("tasks_board", tab=partner_id))
    return redirect(url_for("tasks_board"))


@app.route("/tasks/add", methods=["GET", "POST"])
@app.route("/tasks/quick-add", methods=["GET", "POST"])
def add_task():
    """Ultra-fast Linear-style task adder."""
    if request.method == "GET":
        return redirect(url_for("tasks_board"))

    viewer_id = session.get("logged_in_user", "imran")
    title = request.form.get("title", "").strip()
    assigned_to = request.form.get("assigned_to", "shared")
    due_date = request.form.get("due_date", date.today().strftime("%Y-%m-%d")).strip()
    priority = request.form.get("priority", "Normal")
    details = request.form.get("details", "").strip()
    redirect_to = request.form.get("redirect_to")
    if not redirect_to or redirect_to.startswith("/tasks/add") or redirect_to.startswith("/tasks/quick-add"):
        redirect_to = url_for("tasks_board")

    today = date.today()
    week_identifier = f"{today.year}-W{today.isocalendar()[1]:02d}"
    task_type = "shared" if assigned_to == "shared" else "personal"
    user_id = viewer_id if assigned_to == "shared" else assigned_to

    if not title:
        flash("Task title required.", "danger")
        return redirect(redirect_to)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO tasks (user_id, task_type, week_identifier, title, details, due_date, priority, assigned_to, is_done)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
    """, (user_id, task_type, week_identifier, title, details, due_date, priority, assigned_to))
    conn.commit()
    conn.close()

    flash(f"Task '{title}' scheduled.", "success")
    return redirect(redirect_to)


@app.route("/tasks/toggle/<int:task_id>", methods=["POST"])
def toggle_task_done(task_id):
    redirect_to = request.form.get("redirect_to")
    if not redirect_to or "/tasks/toggle" in redirect_to:
        redirect_to = url_for("tasks_board")
    today_str = date.today().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_done FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if task:
        new_status = 0 if task["is_done"] else 1
        done_date = today_str if new_status == 1 else None
        cursor.execute("UPDATE tasks SET is_done = ?, done_date = ? WHERE id = ?", (new_status, done_date, task_id))
        conn.commit()
    conn.close()

    return redirect(redirect_to)


@app.route("/tasks/verify-proof/<int:task_id>", methods=["POST"])
def verify_task_proof(task_id):
    """AI Milestone proof verification."""
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("tasks_board")
    proof_text = request.form.get("proof_text", "").strip()
    file = request.files.get("proof_image")

    image_rel_path = None
    image_full_path = None

    if file and file.filename:
        filename = secure_filename(f"task_{task_id}_{int(datetime.now().timestamp())}_{file.filename}")
        image_full_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(image_full_path)
        image_rel_path = f"/static/uploads/proofs/{filename}"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()

    if not task:
        conn.close()
        flash("Task not found.", "danger")
        return redirect(redirect_to)

    is_approved, feedback = verify_goal_evidence(
        task["title"],
        task["details"],
        proof_text,
        image_full_path
    )

    new_completed = 1 if is_approved else 0
    ai_status = "Approved" if is_approved else "Rejected"
    today_str = date.today().strftime("%Y-%m-%d") if is_approved else None

    cursor.execute("""
    UPDATE tasks 
    SET proof_image = COALESCE(?, proof_image),
        proof_text = ?,
        ai_verified = ?,
        ai_status = ?,
        ai_feedback = ?,
        is_done = ?,
        done_date = ?
    WHERE id = ?
    """, (image_rel_path, proof_text, 1 if is_approved else 0, ai_status, feedback, new_completed, today_str, task_id))
    conn.commit()
    conn.close()

    if is_approved:
        flash(f"AI VERIFICATION PASSED: {feedback}", "success")
    else:
        flash(f"AI VERIFICATION REJECTED: {feedback}", "danger")

    return redirect(redirect_to)


@app.route("/tasks/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    redirect_to = request.form.get("redirect_to")
    if not redirect_to or "/tasks/delete" in redirect_to:
        redirect_to = url_for("tasks_board")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

    flash("Task removed.", "info")
    return redirect(redirect_to)


@app.route("/tasks/archive-week", methods=["POST"])
def archive_week():
    viewer_id = session.get("logged_in_user", "imran")
    week_id = request.form.get("week_id")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET is_archived = 1 WHERE user_id = ? AND week_identifier = ?", (viewer_id, week_id))
    conn.commit()
    check_and_apply_penalties(conn)
    conn.close()

    flash(f"Week {week_id} archived.", "success")
    return redirect(url_for("tasks_board"))


# ============================================================================
# Financial Ledger & Savings Views
# ============================================================================

@app.route("/finance")
@app.route("/money")
@app.route("/save")
def finance_view():
    """Consolidated Venture Capital, Margin & Savings Hub."""
    viewer_id = session.get("logged_in_user", "imran")
    partner_filter = request.args.get("partner", "all")

    conn = get_db_connection()
    cursor = conn.cursor()

    fin_totals = get_user_financial_totals(conn, user_id=None)
    a_fin = get_user_financial_totals(conn, user_id="imran")
    b_fin = get_user_financial_totals(conn, user_id="mikiyas")

    cursor.execute("SELECT SUM(savings_goal_target) FROM users")
    target_row = cursor.fetchone()
    savings_target = (target_row[0] or 0.0) if target_row else 0.0
    if savings_target <= 0:
        savings_target = 5000.0

    savings_pct = min(100, int((fin_totals["savings"] / savings_target) * 100)) if savings_target > 0 else 0

    if partner_filter in ("imran", "mikiyas"):
        cursor.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC, id DESC", (partner_filter,))
    else:
        cursor.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC")
    transactions = cursor.fetchall()

    cursor.execute("SELECT * FROM bills ORDER BY is_paid ASC, due_date ASC")
    bills = cursor.fetchall()

    cursor.execute("SELECT * FROM investments ORDER BY purchase_date DESC")
    investments = cursor.fetchall()

    conn.close()

    return render_template(
        "finance.html",
        active_page="finance",
        fin_totals=fin_totals,
        a_fin=a_fin,
        b_fin=b_fin,
        savings_target=savings_target,
        savings_pct=savings_pct,
        transactions=transactions,
        bills=bills,
        investments=investments,
        active_partner_filter=partner_filter,
        viewer_id=viewer_id
    )


@app.route("/money/<partner_id>")
def money_view(partner_id):
    """Direct alias to partner space or filtered finance view."""
    return redirect(url_for("partner_space", partner_id=partner_id))


# ============================================================================
# Dedicated Partner Cockpits (Imran's Space & Mikiyas's Space)
# ============================================================================

@app.route("/partner/<partner_id>")
@app.route("/imran")
@app.route("/mikiyas")
def partner_space(partner_id=None):
    if not partner_id:
        partner_id = "imran" if request.path == "/imran" else "mikiyas"
    if partner_id not in ("imran", "mikiyas"):
        partner_id = "imran"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (partner_id,))
    partner = cursor.fetchone()

    # Personal goals
    cursor.execute("SELECT * FROM goals WHERE goal_type = ? ORDER BY is_completed ASC, id DESC", (partner_id,))
    personal_goals = cursor.fetchall()

    # Shared venture goals
    cursor.execute("SELECT * FROM goals WHERE goal_type = 'shared' ORDER BY is_completed ASC, id DESC")
    shared_goals = cursor.fetchall()

    # Assigned tasks (tasks assigned directly or personal)
    cursor.execute("""
    SELECT * FROM tasks 
    WHERE (assigned_to = ? OR (user_id = ? AND assigned_to != 'shared' AND task_type != 'shared'))
    ORDER BY is_done ASC, due_date ASC, id DESC
    """, (partner_id, partner_id))
    partner_tasks = cursor.fetchall()

    tasks_total = len(partner_tasks)
    tasks_done = sum(1 for t in partner_tasks if t["is_done"])
    task_rate = int((tasks_done / tasks_total * 100)) if tasks_total > 0 else 0

    streak_count = calculate_task_streak(conn, partner_id)
    fin_totals = get_user_financial_totals(conn, user_id=partner_id)

    savings_goal = partner["savings_goal_target"] if partner and partner["savings_goal_target"] > 0 else 2500.0
    savings_pct = min(100, int((fin_totals["savings"] / savings_goal) * 100)) if savings_goal > 0 else 0

    conn.close()

    return render_template(
        "partner.html",
        active_page=f"partner_{partner_id}",
        partner=partner,
        personal_goals=personal_goals,
        shared_goals=shared_goals,
        partner_tasks=partner_tasks,
        tasks_done=tasks_done,
        tasks_total=tasks_total,
        task_rate=task_rate,
        streak_count=streak_count,
        fin_totals=fin_totals,
        savings_pct=savings_pct
    )


# ============================================================================
# Ledger Transactions & Financial Operations
# ============================================================================

@app.route("/money/add", methods=["POST"])
def add_transaction():
    viewer_id = session.get("logged_in_user", "imran")
    partner_id = request.form.get("partner_id") or viewer_id
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("finance_view")

    date_val = request.form.get("date", date.today().strftime("%Y-%m-%d"))
    type_val = request.form.get("type")
    category = request.form.get("category", "").strip()
    amount_str = request.form.get("amount", "").strip()
    note = request.form.get("note", "").strip()

    if not date_val or not type_val or not category or not amount_str:
        flash("All fields are required.", "danger")
        return redirect(redirect_to)

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Amount must be greater than zero.", "danger")
            return redirect(redirect_to)
    except ValueError:
        flash("Invalid numerical amount.", "danger")
        return redirect(redirect_to)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO transactions (user_id, date, type, category, amount, currency, note)
    VALUES (?, ?, ?, ?, ?, '$', ?)
    """, (partner_id, date_val, type_val, category, amount, note))
    conn.commit()
    conn.close()

    flash(f"{type_val} entry of ${amount:.2f} logged for {partner_id.capitalize()}.", "success")
    return redirect(redirect_to)


@app.route("/money/edit", methods=["POST"])
def edit_transaction():
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("finance_view")
    txn_id = request.form.get("txn_id")
    date_val = request.form.get("date")
    type_val = request.form.get("type")
    category = request.form.get("category", "").strip()
    amount_str = request.form.get("amount", "").strip()
    note = request.form.get("note", "").strip()

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Amount must be greater than zero.", "danger")
            return redirect(redirect_to)
    except ValueError:
        flash("Invalid numerical amount.", "danger")
        return redirect(redirect_to)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE transactions 
    SET date = ?, type = ?, category = ?, amount = ?, note = ?
    WHERE id = ?
    """, (date_val, type_val, category, amount, note, txn_id))
    conn.commit()
    conn.close()

    flash("Transaction updated.", "success")
    return redirect(redirect_to)


@app.route("/money/delete/<int:txn_id>", methods=["POST"])
def delete_transaction(txn_id):
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("finance_view")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
    conn.commit()
    conn.close()

    flash("Entry removed.", "info")
    return redirect(redirect_to)


# ============================================================================
# Bills & Investments
# ============================================================================

@app.route("/bills/add", methods=["POST"])
def add_bill():
    viewer_id = session.get("logged_in_user", "imran")
    partner_id = request.form.get("partner_id") or viewer_id
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("finance_view")

    name = request.form.get("name", "").strip()
    amount_str = request.form.get("amount", "").strip()
    due_date = request.form.get("due_date", date.today().strftime("%Y-%m-%d")).strip()
    interval = request.form.get("recurring_interval", "Monthly")

    try:
        amount = float(amount_str)
    except ValueError:
        flash("Invalid numerical amount.", "danger")
        return redirect(redirect_to)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO bills (user_id, name, amount, currency, due_date, is_paid, recurring_interval)
    VALUES (?, ?, ?, '$', ?, 0, ?)
    """, (partner_id, name, amount, due_date, interval))
    conn.commit()
    conn.close()

    flash(f"Obligation '{name}' logged.", "success")
    return redirect(redirect_to)


@app.route("/bills/toggle/<int:bill_id>", methods=["POST"])
def toggle_bill_paid(bill_id):
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("finance_view")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bills SET is_paid = 1 - is_paid WHERE id = ?", (bill_id,))
    conn.commit()
    conn.close()
    return redirect(redirect_to)


@app.route("/bills/delete/<int:bill_id>", methods=["POST"])
def delete_bill(bill_id):
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("finance_view")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
    conn.commit()
    conn.close()
    return redirect(redirect_to)


@app.route("/investments/add", methods=["POST"])
def add_investment():
    viewer_id = session.get("logged_in_user", "imran")
    partner_id = request.form.get("partner_id") or viewer_id
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("finance_view")

    asset_name = request.form.get("asset_name", "").strip()
    invested_str = request.form.get("amount_invested", "").strip()
    current_str = request.form.get("current_value", "").strip()
    purchase_date = request.form.get("purchase_date", date.today().strftime("%Y-%m-%d"))
    notes = request.form.get("notes", "").strip()

    try:
        amount_invested = float(invested_str)
        current_value = float(current_str)
    except ValueError:
        flash("Invalid numerical amount.", "danger")
        return redirect(redirect_to)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO investments (user_id, asset_name, amount_invested, current_value, currency, purchase_date, notes)
    VALUES (?, ?, ?, ?, '$', ?, ?)
    """, (partner_id, asset_name, amount_invested, current_value, purchase_date, notes))
    conn.commit()
    conn.close()

    flash(f"Asset '{asset_name}' logged.", "success")
    return redirect(redirect_to)


@app.route("/investments/edit", methods=["POST"])
def edit_investment():
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("finance_view")
    inv_id = request.form.get("inv_id")
    asset_name = request.form.get("asset_name", "").strip()
    invested_str = request.form.get("amount_invested", "").strip()
    current_str = request.form.get("current_value", "").strip()
    notes = request.form.get("notes", "").strip()

    try:
        amount_invested = float(invested_str)
        current_value = float(current_str)
    except ValueError:
        flash("Invalid numerical values.", "danger")
        return redirect(redirect_to)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE investments
    SET asset_name = ?, amount_invested = ?, current_value = ?, notes = ?
    WHERE id = ?
    """, (asset_name, amount_invested, current_value, notes, inv_id))
    conn.commit()
    conn.close()

    flash("Valuation updated.", "success")
    return redirect(redirect_to)


@app.route("/investments/delete/<int:inv_id>", methods=["POST"])
def delete_investment(inv_id):
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("finance_view")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM investments WHERE id = ?", (inv_id,))
    conn.commit()
    conn.close()
    return redirect(redirect_to)


@app.route("/savings-goal/update", methods=["POST"])
def update_savings_goal():
    viewer_id = session.get("logged_in_user", "imran")
    partner_id = request.form.get("partner_id") or viewer_id
    redirect_to = request.form.get("redirect_to") or request.referrer or url_for("finance_view")

    goal_name = request.form.get("goal_name", "").strip()
    target_str = request.form.get("target_amount", "").strip()

    try:
        target = float(target_str)
    except ValueError:
        flash("Invalid target number.", "danger")
        return redirect(redirect_to)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET savings_goal_name = ?, savings_goal_target = ? WHERE id = ?", (goal_name, target, partner_id))
    conn.commit()
    conn.close()

    flash("Target updated.", "success")
    return redirect(redirect_to)


@app.route("/export-csv")
def export_csv():
    user_id = request.args.get("user_id", "combined")
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id in ("imran", "mikiyas"):
        cursor.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC, id DESC", (user_id,))
        filename = f"venture_{user_id}_{date.today().strftime('%Y%m%d')}.csv"
    else:
        cursor.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC")
        filename = f"venture_consolidated_{date.today().strftime('%Y%m%d')}.csv"

    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Partner", "Date", "Type", "Category", "Amount", "Currency", "Note", "Created At"])

    for row in rows:
        writer.writerow([
            row["id"],
            "Imran" if row["user_id"] == "imran" else "Mikiyas",
            row["date"],
            row["type"],
            row["category"],
            f"{row['amount']:.2f}",
            row["currency"],
            row["note"] or "",
            row["created_at"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================================================
# Penalties Ledger
# ============================================================================

@app.route("/penalties")
def penalties_view():
    conn = get_db_connection()
    check_and_apply_penalties(conn)
    cursor = conn.cursor()
    viewer_id = session.get("logged_in_user", "imran")

    cursor.execute("SELECT * FROM users WHERE id = 'imran'")
    partner_a = cursor.fetchone()

    cursor.execute("SELECT * FROM users WHERE id = 'mikiyas'")
    partner_b = cursor.fetchone()

    cursor.execute("SELECT * FROM penalties WHERE user_id = 'imran' AND status = 'Pending' ORDER BY id DESC")
    a_pending_penalties = cursor.fetchall()
    cursor.execute("SELECT * FROM penalties WHERE user_id = 'imran' AND status = 'Completed' ORDER BY completed_date DESC, id DESC LIMIT 10")
    a_completed_penalties = cursor.fetchall()

    cursor.execute("SELECT * FROM penalties WHERE user_id = 'mikiyas' AND status = 'Pending' ORDER BY id DESC")
    b_pending_penalties = cursor.fetchall()
    cursor.execute("SELECT * FROM penalties WHERE user_id = 'mikiyas' AND status = 'Completed' ORDER BY completed_date DESC, id DESC LIMIT 10")
    b_completed_penalties = cursor.fetchall()

    conn.close()

    return render_template(
        "penalties.html",
        active_page="penalties",
        partner_a=partner_a,
        partner_b=partner_b,
        a_pending_penalties=a_pending_penalties,
        a_completed_penalties=a_completed_penalties,
        a_pending_count=len(a_pending_penalties),
        b_pending_penalties=b_pending_penalties,
        b_completed_penalties=b_completed_penalties,
        b_pending_count=len(b_pending_penalties),
        viewer_id=viewer_id
    )


@app.route("/penalties/complete/<int:penalty_id>", methods=["POST"])
def complete_penalty(penalty_id):
    today_str = date.today().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE penalties SET status = 'Completed', completed_date = ? WHERE id = ?", (today_str, penalty_id))
    conn.commit()
    conn.close()

    flash("Consequence fulfilled.", "success")
    return redirect(url_for("penalties_view"))


@app.route("/settings/update-consequence", methods=["POST"])
def update_consequence():
    logged_id = session.get("logged_in_user")
    consequence = request.form.get("consequence", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET default_consequence = ? WHERE id = ?", (consequence, logged_id))
    conn.commit()
    conn.close()

    flash("Consequence rule saved.", "success")
    return redirect(url_for("settings_view"))


# ============================================================================
# Consolidated Overview
# ============================================================================

@app.route("/combined")
def combined_view():
    conn = get_db_connection()
    cursor = conn.cursor()

    combined_fin = get_user_financial_totals(conn, user_id=None)
    a_fin = get_user_financial_totals(conn, user_id="imran")
    b_fin = get_user_financial_totals(conn, user_id="mikiyas")

    cursor.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC LIMIT 20")
    transactions = cursor.fetchall()

    cursor.execute("SELECT * FROM bills ORDER BY is_paid ASC, due_date ASC")
    bills = cursor.fetchall()

    cursor.execute("SELECT * FROM investments ORDER BY purchase_date DESC")
    investments = cursor.fetchall()
    total_portfolio_val = sum(float(inv["current_value"]) for inv in investments)

    conn.close()

    return render_template(
        "combined.html",
        active_page="combined",
        combined_fin=combined_fin,
        a_fin=a_fin,
        b_fin=b_fin,
        transactions=transactions,
        bills=bills,
        investments=investments,
        total_portfolio_val=total_portfolio_val
    )


# ============================================================================
# Settings Page
# ============================================================================

@app.route("/settings")
def settings_view():
    return render_template("settings.html", active_page="settings")


# ============================================================================
# Vercel Serverless WSGI Path Normalization Middleware
# ============================================================================

class VercelPathFix:
    """
    Translates Vercel Edge rewrites (?path=$1 and edge headers) into standard WSGI PATH_INFO
    so Flask routes match the user's actual requested URL.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        import urllib.parse
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

        # 2. Check edge proxy headers in priority order
        if not path_candidate or path_candidate in ("/api/index", "/api/index.py", "/api/index/", "/api", "/app"):
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
                    if clean and clean not in ("/api/index", "/api/index.py", "/api/index/", "/api", "/app"):
                        path_candidate = clean if clean.startswith("/") else "/" + clean
                        break

        if path_candidate:
            environ["PATH_INFO"] = path_candidate
        elif environ.get("PATH_INFO", "") in ("/api/index", "/api/index.py", "/api/index/", "/api", "/app"):
            environ["PATH_INFO"] = "/"

        # Remove internal ?path= from QUERY_STRING so Flask request.args is clean
        if "path" in params:
            clean_params = {k: v for k, v in params.items() if k != "path"}
            environ["QUERY_STRING"] = urllib.parse.urlencode(clean_params, doseq=True)

        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathFix(app.wsgi_app)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
