"""
Partner Tracker - Two-Person Money and Task Tracker
Main Flask Application Entrypoint
"""

import os
import io
import csv
from datetime import datetime, date, timedelta
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, Response
)
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import (
    get_db_connection, init_db, check_and_apply_penalties,
    calculate_task_streak, get_user_financial_totals, get_chart_data
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "partner_tracker_secure_session_key_2026")

# Ensure database tables exist on startup
init_db(seed=True)


@app.context_processor
def inject_globals():
    """Injects current authenticated partner and global counts into all templates."""
    today_str = date.today().strftime("%Y-%m-%d")
    current_user = None
    logged_id = session.get("logged_in_user")
    
    conn = get_db_connection()
    # Auto-check and trigger penalties for overdue tasks
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
# Authentication & PIN Management
# ============================================================================

@app.route("/login", methods=["POST"])
def login():
    """Handles partner login using personal 6-digit PIN."""
    partner_id = request.form.get("partner_id")
    pin = request.form.get("pin", "").strip()

    if not partner_id or not pin:
        flash("Please select a partner and enter your PIN code.", "danger")
        return redirect(request.referrer or url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (partner_id,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user["pin_hash"], pin):
        session["logged_in_user"] = partner_id
        flash(f"Welcome back, {user['name']}! Full edit mode unlocked.", "success")
    else:
        flash("Incorrect PIN code. Viewing remains in read-only mode.", "danger")

    return redirect(request.referrer or url_for("index"))


@app.route("/logout")
def logout():
    """Logs out partner and switches interface back to read-only viewing."""
    session.pop("logged_in_user", None)
    flash("You have logged out. The app is now in viewing (read-only) mode.", "info")
    return redirect(request.referrer or url_for("index"))


@app.route("/change-pin", methods=["POST"])
def change_pin():
    """Changes the logged-in partner's PIN code."""
    logged_id = session.get("logged_in_user")
    if not logged_id:
        flash("You must be logged in to change your PIN.", "danger")
        return redirect(url_for("index"))

    current_pin = request.form.get("current_pin", "").strip()
    new_pin = request.form.get("new_pin", "").strip()
    confirm_pin = request.form.get("confirm_pin", "").strip()

    if not current_pin or not new_pin or not confirm_pin:
        flash("All PIN fields are required.", "danger")
        return redirect(url_for("settings_view"))

    if new_pin != confirm_pin:
        flash("New PIN and confirmation PIN do not match.", "danger")
        return redirect(url_for("settings_view"))

    if len(new_pin) < 4:
        flash("PIN must be at least 4 digits.", "danger")
        return redirect(url_for("settings_view"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT pin_hash FROM users WHERE id = ?", (logged_id,))
    user = cursor.fetchone()

    if not user or not check_password_hash(user["pin_hash"], current_pin):
        conn.close()
        flash("Current PIN is incorrect.", "danger")
        return redirect(url_for("settings_view"))

    new_hash = generate_password_hash(new_pin)
    cursor.execute("UPDATE users SET pin_hash = ? WHERE id = ?", (new_hash, logged_id))
    conn.commit()
    conn.close()

    flash("Your PIN code was successfully updated!", "success")
    return redirect(url_for("settings_view"))


# ============================================================================
# Home / Dashboard
# ============================================================================

@app.route("/")
def index():
    """Main dashboard summarizing both partners' finances and task progress."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Financial totals
    combined_fin = get_user_financial_totals(conn, user_id=None)
    a_fin = get_user_financial_totals(conn, user_id="partner_a")
    b_fin = get_user_financial_totals(conn, user_id="partner_b")

    # Current week identifier
    today = date.today()
    curr_week = f"{today.year}-W{today.isocalendar()[1]:02d}"

    # Task stats for Partner A
    cursor.execute("SELECT COUNT(*), SUM(is_done) FROM tasks WHERE user_id = 'partner_a' AND week_identifier = ?", (curr_week,))
    a_total, a_done = cursor.fetchone()
    a_total_tasks = a_total or 0
    a_done_tasks = a_done or 0
    a_task_rate = int((a_done_tasks / a_total_tasks * 100)) if a_total_tasks > 0 else 0

    # Task stats for Partner B
    cursor.execute("SELECT COUNT(*), SUM(is_done) FROM tasks WHERE user_id = 'partner_b' AND week_identifier = ?", (curr_week,))
    b_total, b_done = cursor.fetchone()
    b_total_tasks = b_total or 0
    b_done_tasks = b_done or 0
    b_task_rate = int((b_done_tasks / b_total_tasks * 100)) if b_total_tasks > 0 else 0

    # Pending penalties
    cursor.execute("SELECT COUNT(*) FROM penalties WHERE user_id = 'partner_a' AND status = 'Pending'")
    a_pending_penalties = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM penalties WHERE user_id = 'partner_b' AND status = 'Pending'")
    b_pending_penalties = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        active_page="home",
        combined_fin=combined_fin,
        a_fin=a_fin,
        b_fin=b_fin,
        a_total_tasks=a_total_tasks,
        a_done_tasks=a_done_tasks,
        a_task_rate=a_task_rate,
        b_total_tasks=b_total_tasks,
        b_done_tasks=b_done_tasks,
        b_task_rate=b_task_rate,
        a_pending_penalties=a_pending_penalties,
        b_pending_penalties=b_pending_penalties
    )


# ============================================================================
# Money Tracker Views & Operations
# ============================================================================

@app.route("/money/<partner_id>")
def money_view(partner_id):
    """Displays financial hub for a specific partner."""
    if partner_id not in ("partner_a", "partner_b"):
        return redirect(url_for("money_view", partner_id="partner_a"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (partner_id,))
    partner = cursor.fetchone()

    # Financial totals
    fin_totals = get_user_financial_totals(conn, user_id=partner_id)

    # Calculate Savings Goal percentage
    savings_pct = 0
    if partner["savings_goal_target"] > 0:
        savings_pct = min(100, int((fin_totals["savings"] / partner["savings_goal_target"]) * 100))

    # Transactions
    cursor.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC, id DESC", (partner_id,))
    transactions = cursor.fetchall()

    # Recurring Bills
    cursor.execute("SELECT * FROM bills WHERE user_id = ? ORDER BY is_paid ASC, due_date ASC", (partner_id,))
    bills = cursor.fetchall()

    # Investments
    cursor.execute("SELECT * FROM investments WHERE user_id = ? ORDER BY purchase_date DESC", (partner_id,))
    investments = cursor.fetchall()

    # Chart data
    chart_data = get_chart_data(conn, user_id=partner_id)

    conn.close()

    can_edit = (session.get("logged_in_user") == partner_id)

    return render_template(
        "money.html",
        active_page="money",
        partner=partner,
        fin_totals=fin_totals,
        savings_pct=savings_pct,
        transactions=transactions,
        bills=bills,
        investments=investments,
        chart_data=chart_data,
        can_edit=can_edit
    )


@app.route("/money/add", methods=["POST"])
def add_transaction():
    """Adds a new money transaction entry."""
    partner_id = request.form.get("partner_id")
    if session.get("logged_in_user") != partner_id:
        flash("Authentication required: you can only add entries for your own page.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    date_val = request.form.get("date")
    type_val = request.form.get("type")
    category = request.form.get("category", "").strip()
    amount_str = request.form.get("amount", "").strip()
    note = request.form.get("note", "").strip()

    # Input validation
    if not date_val or not type_val or not category or not amount_str:
        flash("All required fields must be filled out.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Amount must be greater than zero.", "danger")
            return redirect(url_for("money_view", partner_id=partner_id))
    except ValueError:
        flash("Invalid numeric amount entered.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO transactions (user_id, date, type, category, amount, currency, note)
    VALUES (?, ?, ?, ?, ?, '$', ?)
    """, (partner_id, date_val, type_val, category, amount, note))
    conn.commit()
    conn.close()

    flash(f"{type_val} entry of ${amount:.2f} recorded successfully!", "success")
    return redirect(url_for("money_view", partner_id=partner_id))


@app.route("/money/edit", methods=["POST"])
def edit_transaction():
    """Updates an existing money transaction."""
    partner_id = request.form.get("partner_id")
    if session.get("logged_in_user") != partner_id:
        flash("Authentication required: you can only edit entries for your own page.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

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
            return redirect(url_for("money_view", partner_id=partner_id))
    except ValueError:
        flash("Invalid numeric amount.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE transactions 
    SET date = ?, type = ?, category = ?, amount = ?, note = ?
    WHERE id = ? AND user_id = ?
    """, (date_val, type_val, category, amount, note, txn_id, partner_id))
    conn.commit()
    conn.close()

    flash("Transaction entry updated successfully!", "success")
    return redirect(url_for("money_view", partner_id=partner_id))


@app.route("/money/delete/<int:txn_id>", methods=["POST"])
def delete_transaction(txn_id):
    """Deletes a money transaction entry."""
    partner_id = request.form.get("partner_id")
    if session.get("logged_in_user") != partner_id:
        flash("Authentication required: you can only delete entries on your own page.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (txn_id, partner_id))
    conn.commit()
    conn.close()

    flash("Transaction deleted.", "info")
    return redirect(url_for("money_view", partner_id=partner_id))


# ============================================================================
# Bills & Subscriptions
# ============================================================================

@app.route("/bills/add", methods=["POST"])
def add_bill():
    """Adds a recurring bill."""
    partner_id = request.form.get("partner_id")
    if session.get("logged_in_user") != partner_id:
        flash("Authentication required to add bills.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    name = request.form.get("name", "").strip()
    amount_str = request.form.get("amount", "").strip()
    due_date = request.form.get("due_date", "").strip()
    interval = request.form.get("recurring_interval", "Monthly")

    if not name or not amount_str or not due_date:
        flash("Please provide name, amount, and due date.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    try:
        amount = float(amount_str)
    except ValueError:
        flash("Invalid amount.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO bills (user_id, name, amount, currency, due_date, is_paid, recurring_interval)
    VALUES (?, ?, ?, '$', ?, 0, ?)
    """, (partner_id, name, amount, due_date, interval))
    conn.commit()
    conn.close()

    flash(f"Bill '{name}' added successfully!", "success")
    return redirect(url_for("money_view", partner_id=partner_id))


@app.route("/bills/toggle/<int:bill_id>", methods=["POST"])
def toggle_bill_paid(bill_id):
    """Toggles bill payment status."""
    partner_id = request.form.get("partner_id")
    if session.get("logged_in_user") != partner_id:
        flash("Authentication required to modify bills.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bills SET is_paid = 1 - is_paid WHERE id = ? AND user_id = ?", (bill_id, partner_id))
    conn.commit()
    conn.close()

    return redirect(url_for("money_view", partner_id=partner_id))


@app.route("/bills/delete/<int:bill_id>", methods=["POST"])
def delete_bill(bill_id):
    """Deletes a bill."""
    partner_id = request.form.get("partner_id")
    if session.get("logged_in_user") != partner_id:
        flash("Authentication required.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bills WHERE id = ? AND user_id = ?", (bill_id, partner_id))
    conn.commit()
    conn.close()

    flash("Bill removed.", "info")
    return redirect(url_for("money_view", partner_id=partner_id))


# ============================================================================
# Investments & Capital Assets
# ============================================================================

@app.route("/investments/add", methods=["POST"])
def add_investment():
    """Adds a tracked investment or business asset."""
    partner_id = request.form.get("partner_id")
    if session.get("logged_in_user") != partner_id:
        flash("Authentication required to add investments.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    asset_name = request.form.get("asset_name", "").strip()
    invested_str = request.form.get("amount_invested", "").strip()
    current_str = request.form.get("current_value", "").strip()
    purchase_date = request.form.get("purchase_date")
    notes = request.form.get("notes", "").strip()

    try:
        amount_invested = float(invested_str)
        current_value = float(current_str)
    except ValueError:
        flash("Please enter valid numeric amounts.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO investments (user_id, asset_name, amount_invested, current_value, currency, purchase_date, notes)
    VALUES (?, ?, ?, ?, '$', ?, ?)
    """, (partner_id, asset_name, amount_invested, current_value, purchase_date, notes))
    conn.commit()
    conn.close()

    flash(f"Investment '{asset_name}' recorded!", "success")
    return redirect(url_for("money_view", partner_id=partner_id))


@app.route("/investments/edit", methods=["POST"])
def edit_investment():
    """Updates an investment's current value and info."""
    partner_id = request.form.get("partner_id")
    if session.get("logged_in_user") != partner_id:
        flash("Authentication required to update investments.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    inv_id = request.form.get("inv_id")
    asset_name = request.form.get("asset_name", "").strip()
    invested_str = request.form.get("amount_invested", "").strip()
    current_str = request.form.get("current_value", "").strip()
    notes = request.form.get("notes", "").strip()

    try:
        amount_invested = float(invested_str)
        current_value = float(current_str)
    except ValueError:
        flash("Invalid numbers.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE investments
    SET asset_name = ?, amount_invested = ?, current_value = ?, notes = ?
    WHERE id = ? AND user_id = ?
    """, (asset_name, amount_invested, current_value, notes, inv_id, partner_id))
    conn.commit()
    conn.close()

    flash("Investment details updated!", "success")
    return redirect(url_for("money_view", partner_id=partner_id))


@app.route("/investments/delete/<int:inv_id>", methods=["POST"])
def delete_investment(inv_id):
    """Deletes an investment record."""
    partner_id = request.form.get("partner_id")
    if session.get("logged_in_user") != partner_id:
        flash("Authentication required.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM investments WHERE id = ? AND user_id = ?", (inv_id, partner_id))
    conn.commit()
    conn.close()

    flash("Investment removed.", "info")
    return redirect(url_for("money_view", partner_id=partner_id))


# ============================================================================
# Savings Goal
# ============================================================================

@app.route("/savings-goal/update", methods=["POST"])
def update_savings_goal():
    """Updates the partner's savings goal name and target."""
    partner_id = request.form.get("partner_id")
    if session.get("logged_in_user") != partner_id:
        flash("Authentication required to edit savings goal.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    goal_name = request.form.get("goal_name", "").strip()
    target_str = request.form.get("target_amount", "").strip()

    try:
        target = float(target_str)
        if target <= 0:
            flash("Target must be greater than zero.", "danger")
            return redirect(url_for("money_view", partner_id=partner_id))
    except ValueError:
        flash("Invalid target number.", "danger")
        return redirect(url_for("money_view", partner_id=partner_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET savings_goal_name = ?, savings_goal_target = ? WHERE id = ?", (goal_name, target, partner_id))
    conn.commit()
    conn.close()

    flash("Savings goal successfully updated!", "success")
    return redirect(url_for("money_view", partner_id=partner_id))


# ============================================================================
# CSV Export
# ============================================================================

@app.route("/export-csv")
def export_csv():
    """Exports money entries to CSV format."""
    user_id = request.args.get("user_id", "combined")
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id in ("partner_a", "partner_b"):
        cursor.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC, id DESC", (user_id,))
        filename = f"partner_tracker_{user_id}_{date.today().strftime('%Y%m%d')}.csv"
    else:
        cursor.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC")
        filename = f"partner_tracker_combined_{date.today().strftime('%Y%m%d')}.csv"

    rows = cursor.fetchall()
    conn.close()

    # Generate CSV in-memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Partner", "Date", "Type", "Category", "Amount", "Currency", "Note", "Created At"])

    for row in rows:
        writer.writerow([
            row["id"],
            "Partner A" if row["user_id"] == "partner_a" else "Partner B",
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
# Task Tracker Views & Operations
# ============================================================================

@app.route("/tasks/<partner_id>")
def tasks_view(partner_id):
    """Weekly task tracker for each partner with daily check-ins and streaks."""
    if partner_id not in ("partner_a", "partner_b"):
        return redirect(url_for("tasks_view", partner_id="partner_a"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (partner_id,))
    partner = cursor.fetchone()

    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    current_week_id = f"{today.year}-W{today.isocalendar()[1]:02d}"

    # Find all available weeks for this partner in archive
    cursor.execute("SELECT DISTINCT week_identifier FROM tasks WHERE user_id = ? ORDER BY week_identifier DESC", (partner_id,))
    existing_weeks = [r[0] for r in cursor.fetchall()]
    if current_week_id not in existing_weeks:
        existing_weeks.insert(0, current_week_id)

    selected_week = request.args.get("week", current_week_id)
    if selected_week not in existing_weeks:
        selected_week = current_week_id

    # Tasks for selected week
    cursor.execute("SELECT * FROM tasks WHERE user_id = ? AND week_identifier = ? ORDER BY due_date ASC, id ASC", (partner_id, selected_week))
    all_tasks = cursor.fetchall()

    # Daily check-in tasks: tasks due today
    today_tasks = [t for t in all_tasks if t["due_date"] == today_str]

    # Weekly completion stats
    total_tasks_count = len(all_tasks)
    done_tasks_count = len([t for t in all_tasks if t["is_done"]])
    completion_rate = int((done_tasks_count / total_tasks_count * 100)) if total_tasks_count > 0 else 0

    # Discipline streak
    streak_count = calculate_task_streak(conn, partner_id)

    conn.close()

    can_edit = (session.get("logged_in_user") == partner_id)

    return render_template(
        "tasks.html",
        active_page="tasks",
        partner=partner,
        selected_week=selected_week,
        current_week_id=current_week_id,
        available_weeks=existing_weeks,
        all_tasks=all_tasks,
        today_tasks=today_tasks,
        total_tasks_count=total_tasks_count,
        done_tasks_count=done_tasks_count,
        completion_rate=completion_rate,
        streak_count=streak_count,
        can_edit=can_edit
    )


@app.route("/tasks/add", methods=["POST"])
def add_task():
    """Adds a new task for the week."""
    partner_id = request.form.get("partner_id")
    if session.get("logged_in_user") != partner_id:
        flash("Authentication required to add tasks.", "danger")
        return redirect(url_for("tasks_view", partner_id=partner_id))

    week_id = request.form.get("week_id")
    title = request.form.get("title", "").strip()
    details = request.form.get("details", "").strip()
    due_date = request.form.get("due_date", "").strip()

    if not title or not due_date:
        flash("Task name and due date are required.", "danger")
        return redirect(url_for("tasks_view", partner_id=partner_id, week=week_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO tasks (user_id, week_identifier, title, details, due_date, is_done)
    VALUES (?, ?, ?, ?, ?, 0)
    """, (partner_id, week_id, title, details, due_date))
    conn.commit()
    conn.close()

    flash(f"Task '{title}' scheduled for {due_date}!", "success")
    return redirect(url_for("tasks_view", partner_id=partner_id, week=week_id))


@app.route("/tasks/toggle/<int:task_id>", methods=["POST"])
def toggle_task_done(task_id):
    """Toggles task done status (Daily check-in / weekly execution)."""
    partner_id = request.form.get("partner_id")
    week_id = request.form.get("week_id")

    if session.get("logged_in_user") != partner_id:
        flash("Authentication required to mark tasks done.", "danger")
        return redirect(url_for("tasks_view", partner_id=partner_id, week=week_id))

    today_str = date.today().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT is_done FROM tasks WHERE id = ? AND user_id = ?", (task_id, partner_id))
    task = cursor.fetchone()
    if task:
        new_status = 0 if task["is_done"] else 1
        done_date = today_str if new_status == 1 else None
        cursor.execute("UPDATE tasks SET is_done = ?, done_date = ? WHERE id = ?", (new_status, done_date, task_id))
        conn.commit()

    conn.close()
    return redirect(url_for("tasks_view", partner_id=partner_id, week=week_id))


@app.route("/tasks/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    """Deletes a task."""
    partner_id = request.form.get("partner_id")
    week_id = request.form.get("week_id")

    if session.get("logged_in_user") != partner_id:
        flash("Authentication required.", "danger")
        return redirect(url_for("tasks_view", partner_id=partner_id, week=week_id))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, partner_id))
    conn.commit()
    conn.close()

    flash("Task removed.", "info")
    return redirect(url_for("tasks_view", partner_id=partner_id, week=week_id))


@app.route("/tasks/archive-week", methods=["POST"])
def archive_week():
    """Archives the current week and triggers any missed task penalties."""
    partner_id = request.form.get("partner_id")
    week_id = request.form.get("week_id")

    if session.get("logged_in_user") != partner_id:
        flash("Authentication required.", "danger")
        return redirect(url_for("tasks_view", partner_id=partner_id))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Mark past incomplete tasks in this week as having consequences applied
    cursor.execute("UPDATE tasks SET is_archived = 1 WHERE user_id = ? AND week_identifier = ?", (partner_id, week_id))
    conn.commit()

    # Run penalty check to record consequences for any incomplete tasks
    check_and_apply_penalties(conn)
    conn.close()

    flash(f"Week {week_id} archived successfully! New week list is ready.", "success")
    return redirect(url_for("tasks_view", partner_id=partner_id))


# ============================================================================
# Penalties & Consequences Board
# ============================================================================

@app.route("/penalties")
def penalties_view():
    """Consequence and penalty board showing pending and completed penalties."""
    conn = get_db_connection()
    check_and_apply_penalties(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = 'partner_a'")
    partner_a = cursor.fetchone()

    cursor.execute("SELECT * FROM users WHERE id = 'partner_b'")
    partner_b = cursor.fetchone()

    # Partner A penalties
    cursor.execute("SELECT * FROM penalties WHERE user_id = 'partner_a' AND status = 'Pending' ORDER BY id DESC")
    a_pending_penalties = cursor.fetchall()

    cursor.execute("SELECT * FROM penalties WHERE user_id = 'partner_a' AND status = 'Completed' ORDER BY completed_date DESC, id DESC LIMIT 10")
    a_completed_penalties = cursor.fetchall()

    # Partner B penalties
    cursor.execute("SELECT * FROM penalties WHERE user_id = 'partner_b' AND status = 'Pending' ORDER BY id DESC")
    b_pending_penalties = cursor.fetchall()

    cursor.execute("SELECT * FROM penalties WHERE user_id = 'partner_b' AND status = 'Completed' ORDER BY completed_date DESC, id DESC LIMIT 10")
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
        b_pending_count=len(b_pending_penalties)
    )


@app.route("/penalties/complete/<int:penalty_id>", methods=["POST"])
def complete_penalty(penalty_id):
    """Owner marks penalty completed after performing it."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM penalties WHERE id = ?", (penalty_id,))
    penalty = cursor.fetchone()

    if not penalty:
        conn.close()
        flash("Penalty record not found.", "danger")
        return redirect(url_for("penalties_view"))

    # Security check: owner with their code must be logged in
    if session.get("logged_in_user") != penalty["user_id"]:
        conn.close()
        flash("Only the owning partner can mark their penalty completed with their login code.", "danger")
        return redirect(url_for("penalties_view"))

    today_str = date.today().strftime("%Y-%m-%d")
    cursor.execute("UPDATE penalties SET status = 'Completed', completed_date = ? WHERE id = ?", (today_str, penalty_id))
    conn.commit()
    conn.close()

    flash("Awesome job honoring your accountability! Consequence marked completed.", "success")
    return redirect(url_for("penalties_view"))


@app.route("/settings/update-consequence", methods=["POST"])
def update_consequence():
    """Updates the logged-in partner's default agreed consequence."""
    logged_id = session.get("logged_in_user")
    if not logged_id:
        flash("You must be logged in to update your consequence.", "danger")
        return redirect(url_for("index"))

    consequence = request.form.get("consequence", "").strip()
    if not consequence:
        flash("Consequence cannot be blank.", "danger")
        return redirect(url_for("settings_view"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET default_consequence = ? WHERE id = ?", (consequence, logged_id))
    conn.commit()
    conn.close()

    flash("Your default consequence was updated successfully!", "success")
    return redirect(url_for("settings_view"))


# ============================================================================
# Combined Shared Summary
# ============================================================================

@app.route("/combined")
def combined_view():
    """Consolidated financial summary of both partners' money, bills, and investments."""
    conn = get_db_connection()
    cursor = conn.cursor()

    combined_fin = get_user_financial_totals(conn, user_id=None)
    a_fin = get_user_financial_totals(conn, user_id="partner_a")
    b_fin = get_user_financial_totals(conn, user_id="partner_b")

    # All transactions
    cursor.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC LIMIT 20")
    transactions = cursor.fetchall()

    # All bills
    cursor.execute("SELECT * FROM bills ORDER BY is_paid ASC, due_date ASC")
    bills = cursor.fetchall()

    # All investments
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
    """Settings page for PIN changes and consequence rules."""
    return render_template("settings.html", active_page="settings")


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
