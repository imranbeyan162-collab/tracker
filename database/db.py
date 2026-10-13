"""
Database utilities and helper functions for Partner Tracker.
Handles SQLite connection, schema definition, seed data, and query helpers.
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


def init_db(seed=True):
    """Initializes tables and seeds initial data if database is empty."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users table (Partner A and Partner B)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        pin_hash TEXT NOT NULL,
        default_consequence TEXT NOT NULL,
        savings_goal_name TEXT NOT NULL DEFAULT 'Emergency & Growth Fund',
        savings_goal_target REAL NOT NULL DEFAULT 5000.0,
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

    conn.commit()

    # Seed initial users if they don't exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0 and seed:
        seed_initial_data(conn)

    conn.close()


def seed_initial_data(conn):
    """Seeds default partners and realistic sample entries."""
    cursor = conn.cursor()
    today = date.today()

    # Default PINs:
    # Partner A: 111111
    # Partner B: 222222
    pin_a = generate_password_hash("111111")
    pin_b = generate_password_hash("222222")

    cursor.execute("""
    INSERT INTO users (id, name, pin_hash, default_consequence, savings_goal_name, savings_goal_target, currency)
    VALUES 
    ('partner_a', 'Partner A', ?, 'Cook a 3-course dinner for Partner B', 'Q4 Expansion & Inventory', 3000.0, '$'),
    ('partner_b', 'Partner B', ?, 'Wash dishes & clean workspace for a week', 'Marketing Equipment Fund', 2500.0, '$')
    """, (pin_a, pin_b))

    # Helper dates
    d0 = today.strftime("%Y-%m-%d")
    d_yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    d_minus3 = (today - timedelta(days=3)).strftime("%Y-%m-%d")
    d_minus5 = (today - timedelta(days=5)).strftime("%Y-%m-%d")
    d_minus8 = (today - timedelta(days=8)).strftime("%Y-%m-%d")
    d_plus2 = (today + timedelta(days=2)).strftime("%Y-%m-%d")
    d_plus4 = (today + timedelta(days=4)).strftime("%Y-%m-%d")
    d_overdue = (today - timedelta(days=2)).strftime("%Y-%m-%d")

    # Sample Transactions for Partner A
    cursor.executemany("""
    INSERT INTO transactions (user_id, date, type, category, amount, currency, note)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        ('partner_a', d_minus8, 'Income', 'Product Sales', 1250.00, '$', 'Batch #1 online storefront sales'),
        ('partner_a', d_minus5, 'Expense', 'Packaging & Supplies', 180.50, '$', 'Eco-friendly mailer boxes & tape'),
        ('partner_a', d_minus3, 'Savings', 'Emergency Fund', 300.00, '$', 'Weekly reserve transfer'),
        ('partner_a', d_yesterday, 'Income', 'Consulting Client', 650.00, '$', 'Client onboarding milestone 1'),
        ('partner_a', d0, 'Investment', 'Equipment', 400.00, '$', 'Label printer & packaging station'),
        ('partner_a', d0, 'Expense', 'Software & Tools', 49.00, '$', 'Design software monthly subscription')
    ])

    # Sample Transactions for Partner B
    cursor.executemany("""
    INSERT INTO transactions (user_id, date, type, category, amount, currency, note)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        ('partner_b', d_minus8, 'Income', 'Wholesale Order', 980.00, '$', 'Local boutique wholesale supply'),
        ('partner_b', d_minus5, 'Expense', 'Digital Ads', 210.00, '$', 'Social media target campaign'),
        ('partner_b', d_minus3, 'Savings', 'Growth Reserve', 250.00, '$', 'Weekly business savings transfer'),
        ('partner_b', d_yesterday, 'Expense', 'Shipping Costs', 85.00, '$', 'Courier pickups for bulk delivery'),
        ('partner_b', d0, 'Income', 'Online Store', 540.00, '$', 'Weekend direct retail sales'),
        ('partner_b', d0, 'Investment', 'Stocks', 350.00, '$', 'Index fund contribution')
    ])

    # Sample Bills
    cursor.executemany("""
    INSERT INTO bills (user_id, name, amount, currency, due_date, is_paid, recurring_interval)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        ('partner_a', 'Shopify Store Hosting', 39.00, '$', d_plus4, 0, 'Monthly'),
        ('partner_a', 'Domain Renewal (partnerbiz.com)', 18.00, '$', d_overdue, 0, 'Yearly'),  # Overdue demo!
        ('partner_a', 'Accounting Software', 25.00, '$', d_minus8, 1, 'Monthly'),
        ('partner_b', 'Google Workspace Email', 12.00, '$', d_plus2, 0, 'Monthly'),
        ('partner_b', 'Warehouse Mini-Storage', 120.00, '$', d_plus4, 0, 'Monthly'),
        ('partner_b', 'Payment Processing Fee', 45.00, '$', d_minus5, 1, 'Monthly')
    ])

    # Sample Investments
    cursor.executemany("""
    INSERT INTO investments (user_id, asset_name, amount_invested, current_value, currency, purchase_date, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        ('partner_a', 'High-Speed Thermal Printer', 400.00, 420.00, '$', d0, 'Resale value holding strong with 2-year warranty'),
        ('partner_a', 'Bulk Inventory Stock (Batch 2)', 1100.00, 1550.00, '$', d_minus8, 'Expected gross retail value after packaging'),
        ('partner_b', 'Business ETF Growth Portfolio', 350.00, 385.00, '$', d0, 'Small cap index investment fund'),
        ('partner_b', 'High-Yield Business Stash', 800.00, 816.00, '$', d_minus8, '4.8% APY interest yield stash')
    ])

    # Current week identifier
    curr_week = f"{today.year}-W{today.isocalendar()[1]:02d}"

    # Sample Tasks
    cursor.executemany("""
    INSERT INTO tasks (user_id, week_identifier, title, details, due_date, is_done, done_date, is_archived, consequence_applied)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        ('partner_a', curr_week, 'Package & ship pending customer orders', 'All orders from weekend queue', d_yesterday, 1, d_yesterday, 0, 0),
        ('partner_a', curr_week, 'Update supplier cost comparison spreadsheet', 'Need 3 wholesale quotes', d0, 0, None, 0, 0),
        ('partner_a', curr_week, 'Reconcile weekly bank receipts', 'Match invoices to entries', d_plus2, 0, None, 0, 0),
        ('partner_a', curr_week, 'Launch new product mockup photos', 'Prepare 5 instagram slides', d_plus4, 0, None, 0, 0),
        
        ('partner_b', curr_week, 'Set up weekly ad campaign A/B test', 'Test carousel vs single video ad', d_yesterday, 1, d_yesterday, 0, 0),
        ('partner_b', curr_week, 'Reach out to 5 local retail shops', 'Send wholesale product catalog', d0, 1, d0, 0, 0),
        ('partner_b', curr_week, 'Update inventory restock alerts', 'Check stock below 15 units', d_plus2, 0, None, 0, 0),
        ('partner_b', curr_week, 'Draft email newsletter to subscribers', 'Highlight special flash sale', d_plus4, 0, None, 0, 0)
    ])

    # Sample Penalties (One completed, one pending to showcase feature)
    cursor.executemany("""
    INSERT INTO penalties (user_id, task_id, consequence, reason, status, created_date, completed_date)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        ('partner_a', None, 'Cook a 3-course dinner for Partner B', 'Missed task: "File monthly tax estimate" (Last Week)', 'Pending', d_minus3, None),
        ('partner_b', None, 'Wash dishes & clean workspace for a week', 'Missed task: "Send bulk quote to supplier" (Last Week)', 'Completed', d_minus8, d_yesterday)
    ])

    conn.commit()


def check_and_apply_penalties(conn):
    """
    Checks for tasks whose due_date is in the past (< today) and is_done == 0.
    Automatically generates a penalty on the owner's page with their designated consequence.
    """
    today_str = date.today().strftime("%Y-%m-%d")
    cursor = conn.cursor()

    # Find overdue incomplete tasks where consequence hasn't been triggered yet
    cursor.execute("""
    SELECT t.id, t.user_id, t.title, t.due_date, u.default_consequence 
    FROM tasks t
    JOIN users u ON t.user_id = u.id
    WHERE t.due_date < ? AND t.is_done = 0 AND t.consequence_applied = 0
    """, (today_str,))
    overdue_tasks = cursor.fetchall()

    for task in overdue_tasks:
        reason = f"Missed task: '{task['title']}' (Due {task['due_date']})"
        consequence = task['default_consequence'] or "Do an agreed partner chore"
        cursor.execute("""
        INSERT INTO penalties (user_id, task_id, consequence, reason, status, created_date)
        VALUES (?, ?, ?, ?, 'Pending', ?)
        """, (task['user_id'], task['id'], consequence, reason, today_str))

        cursor.execute("UPDATE tasks SET consequence_applied = 1 WHERE id = ?", (task['id'],))

    conn.commit()


def calculate_task_streak(conn, user_id):
    """
    Calculates consecutive days where all tasks due were completed.
    Walks backwards from today/yesterday.
    """
    cursor = conn.cursor()
    today = date.today()
    streak = 0
    
    # Check consecutive past days
    for day_offset in range(1, 30):
        check_date = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        
        # Were there tasks due on this date?
        cursor.execute("SELECT COUNT(*), SUM(is_done) FROM tasks WHERE user_id = ? AND due_date = ?", (user_id, check_date))
        total, done = cursor.fetchone()
        
        if total == 0:
            # If no tasks were due on that day, streak continues if there's completed tasks before
            continue
        elif done == total:
            streak += 1
        else:
            break
            
    # Check today's tasks
    today_str = today.strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*), SUM(is_done) FROM tasks WHERE user_id = ? AND due_date = ?", (user_id, today_str))
    total_today, done_today = cursor.fetchone()
    if total_today > 0 and done_today == total_today:
        streak += 1

    return streak


def get_user_financial_totals(conn, user_id=None):
    """
    Computes running totals:
    - Income (money received)
    - Expense (money spent)
    - Savings (money saved)
    - Investment (money invested)
    - Net (Income - Expense)
    """
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
    """
    Aggregates data for charts:
    - Monthly Income vs Expense (last 6 months)
    - Expense breakdown by category
    """
    cursor = conn.cursor()
    params = []
    user_filter = ""
    if user_id:
        user_filter = "WHERE user_id = ?"
        params.append(user_id)

    # 1. Monthly Income vs Expenses
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

    # 2. Expense categories
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
