"""
Database utilities and helper functions for Imran & Mikiyas Venture Tracker.
Handles SQLite connection, schema definition, and query helpers.
Zero dummy data - clean state for user input.
"""

import sqlite3
import os
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# Path to database file (supporting both local dev and Vercel serverless /tmp)
if os.environ.get("VERCEL"):
    DB_DIR = "/tmp"
    DB_PATH = os.path.join(DB_DIR, "partner_tracker.db")
    repo_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "partner_tracker.db")
    if not os.path.exists(DB_PATH) and os.path.exists(repo_db):
        try:
            import shutil
            shutil.copy2(repo_db, DB_PATH)
        except Exception:
            pass
else:
    DB_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(DB_DIR, "partner_tracker.db")


def get_db_connection():
    """Returns an active SQLite connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(seed=False):
    """Initializes tables with clean state (no dummy records)."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users table (Imran and Mikiyas)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        pin_hash TEXT NOT NULL,
        default_consequence TEXT NOT NULL DEFAULT '',
        savings_goal_name TEXT NOT NULL DEFAULT 'Capital Growth Fund',
        savings_goal_target REAL NOT NULL DEFAULT 0.0,
        currency TEXT NOT NULL DEFAULT '$'
    )
    """)

    # 2. Money Transactions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        date TEXT NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('Income', 'Expense', 'Savings', 'Investment')),
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT '$',
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # 3. Recurring and one-off Bills table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT '$',
        due_date TEXT NOT NULL,
        is_paid INTEGER NOT NULL DEFAULT 0,
        recurring_interval TEXT DEFAULT 'Monthly',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # 4. Investments Portfolio table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS investments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        asset_name TEXT NOT NULL,
        amount_invested REAL NOT NULL,
        current_value REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT '$',
        purchase_date TEXT NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # 5. Weekly Tasks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        week_identifier TEXT NOT NULL,
        title TEXT NOT NULL,
        details TEXT,
        due_date TEXT NOT NULL,
        is_done INTEGER NOT NULL DEFAULT 0,
        done_date TEXT,
        is_archived INTEGER NOT NULL DEFAULT 0,
        consequence_applied INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # 6. Consequences / Penalties table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS penalties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        task_id INTEGER,
        consequence TEXT NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Completed')),
        created_date TEXT NOT NULL,
        completed_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE SET NULL
    )
    """)

    # 7. Goals table (Shared goals and personal goals for Imran & Mikiyas)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_type TEXT NOT NULL CHECK(goal_type IN ('shared', 'imran', 'mikiyas')),
        title TEXT NOT NULL,
        description TEXT,
        target_time TEXT,
        target_date TEXT,
        category TEXT DEFAULT 'General',
        is_completed INTEGER NOT NULL DEFAULT 0,
        reminder_enabled INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()

    # Ensure Imran and Mikiyas exist with requested default credentials
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        create_clean_users(conn)
    else:
        # Check if users need migration to Imran & Mikiyas
        cursor.execute("SELECT id FROM users")
        u_ids = [r[0] for r in cursor.fetchall()]
        if 'imran' not in u_ids or 'mikiyas' not in u_ids:
            # Recreate with Imran & Mikiyas cleanly
            cursor.execute("DELETE FROM users")
            create_clean_users(conn)

    conn.close()


def create_clean_users(conn):
    """Creates the two partners with the specified master password."""
    cursor = conn.cursor()
    # Default master password: imranandmicas@gmail.com
    master_hash = generate_password_hash("imranandmicas@gmail.com")

    cursor.execute("""
    INSERT INTO users (id, name, pin_hash, default_consequence, savings_goal_name, savings_goal_target, currency)
    VALUES 
    ('imran', 'Imran', ?, 'Complete an agreed accountability task', 'Personal Reserve', 0.0, '$'),
    ('mikiyas', 'Mikiyas', ?, 'Complete an agreed accountability task', 'Personal Reserve', 0.0, '$')
    """, (master_hash, master_hash))
    conn.commit()


def check_and_apply_penalties(conn):
    """Checks for tasks whose due_date is in the past and is_done == 0."""
    today_str = date.today().strftime("%Y-%m-%d")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT t.id, t.user_id, t.title, t.due_date, u.default_consequence 
    FROM tasks t
    JOIN users u ON t.user_id = u.id
    WHERE t.due_date < ? AND t.is_done = 0 AND t.consequence_applied = 0
    """, (today_str,))
    overdue_tasks = cursor.fetchall()

    for task in overdue_tasks:
        reason = f"Missed task: '{task['title']}' (Due {task['due_date']})"
        consequence = task['default_consequence'] or "Agreed accountability consequence"
        cursor.execute("""
        INSERT INTO penalties (user_id, task_id, consequence, reason, status, created_date)
        VALUES (?, ?, ?, ?, 'Pending', ?)
        """, (task['user_id'], task['id'], consequence, reason, today_str))

        cursor.execute("UPDATE tasks SET consequence_applied = 1 WHERE id = ?", (task['id'],))

    conn.commit()


def calculate_task_streak(conn, user_id):
    """Calculates consecutive days where all tasks due were completed."""
    cursor = conn.cursor()
    today = date.today()
    streak = 0
    
    for day_offset in range(1, 30):
        check_date = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        cursor.execute("SELECT COUNT(*), SUM(is_done) FROM tasks WHERE user_id = ? AND due_date = ?", (user_id, check_date))
        total, done = cursor.fetchone()
        
        if total == 0:
            continue
        elif done == total:
            streak += 1
        else:
            break
            
    today_str = today.strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*), SUM(is_done) FROM tasks WHERE user_id = ? AND due_date = ?", (user_id, today_str))
    total_today, done_today = cursor.fetchone()
    if total_today > 0 and done_today == total_today:
        streak += 1

    return streak


def get_user_financial_totals(conn, user_id=None):
    """Computes running totals: Income, Expense, Savings, Investment, Net."""
    cursor = conn.cursor()
    params = []
    where_clause = ""
    if user_id:
        where_clause = "WHERE user_id = ?"
        params.append(user_id)

    query = f"""
    SELECT 
        COALESCE(SUM(CASE WHEN type = 'Income' THEN amount ELSE 0 END), 0) AS total_income,
        COALESCE(SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END), 0) AS total_expense,
        COALESCE(SUM(CASE WHEN type = 'Savings' THEN amount ELSE 0 END), 0) AS total_savings,
        COALESCE(SUM(CASE WHEN type = 'Investment' THEN amount ELSE 0 END), 0) AS total_investments
    FROM transactions
    {where_clause}
    """
    cursor.execute(query, params)
    row = cursor.fetchone()
    
    income = float(row['total_income'])
    expense = float(row['total_expense'])
    savings = float(row['total_savings'])
    investments = float(row['total_investments'])
    net = income - expense

    return {
        'income': income,
        'expense': expense,
        'savings': savings,
        'investments': investments,
        'net': net
    }


def get_chart_data(conn, user_id=None):
    """Aggregates data for monthly charts and expense categories."""
    cursor = conn.cursor()
    params = []
    user_filter = ""
    if user_id:
        user_filter = "WHERE user_id = ?"
        params.append(user_id)

    monthly_query = f"""
    SELECT 
        substr(date, 1, 7) as month_str,
        COALESCE(SUM(CASE WHEN type = 'Income' THEN amount ELSE 0 END), 0) as income,
        COALESCE(SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END), 0) as expense
    FROM transactions
    {user_filter}
    GROUP BY month_str
    ORDER BY month_str ASC
    LIMIT 6
    """
    cursor.execute(monthly_query, params)
    monthly_rows = cursor.fetchall()
    
    months = [r['month_str'] for r in monthly_rows]
    monthly_income = [float(r['income']) for r in monthly_rows]
    monthly_expense = [float(r['expense']) for r in monthly_rows]

    cat_params = [user_id] if user_id else []
    cat_filter = "WHERE type = 'Expense' AND user_id = ?" if user_id else "WHERE type = 'Expense'"
    cat_query = f"""
    SELECT category, SUM(amount) as cat_total
    FROM transactions
    {cat_filter}
    GROUP BY category
    ORDER BY cat_total DESC
    """
    cursor.execute(cat_query, cat_params)
    cat_rows = cursor.fetchall()
    
    expense_categories = [r['category'] for r in cat_rows]
    expense_category_amounts = [float(r['cat_total']) for r in cat_rows]

    return {
        'months': months,
        'monthly_income': monthly_income,
        'monthly_expense': monthly_expense,
        'expense_categories': expense_categories,
        'expense_category_amounts': expense_category_amounts
    }


def get_goals(conn, goal_type=None):
    """Fetches goals filtered by type (shared, imran, mikiyas) or all."""
    cursor = conn.cursor()
    if goal_type:
        cursor.execute("SELECT * FROM goals WHERE goal_type = ? ORDER BY is_completed ASC, id DESC", (goal_type,))
    else:
        cursor.execute("SELECT * FROM goals ORDER BY is_completed ASC, id DESC")
    return cursor.fetchall()
