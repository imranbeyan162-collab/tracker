# 🤝 Partner Tracker: Two-Person Money and Task Tracker

**Partner Tracker** is a clean, modern, and privacy-focused web application built for two business partners (Partner A and Partner B) running a venture together. It centralizes shared finances, investments, recurring bills, weekly tasks, discipline streaks, and a fair accountability consequence system.

---

## 🌟 Key Features

1. **Dual-User Architecture (Open Viewing, Protected Writing)**:
   - Anyone can view the dashboard and see transparency across both partners.
   - Adding, editing, deleting, or marking tasks/penalties completed requires entering the partner's secret PIN code.
   - Partner A cannot alter Partner B's records, and vice versa.
2. **Money Tracker (Per-Partner & Shared Summary)**:
   - Tracks 4 core financial types: **Income**, **Expense**, **Savings**, and **Investment**.
   - Running totals for money received, money spent, money saved, and money invested.
   - Interactive visual charts:
     - **Monthly Income vs. Expenses** (Bar Chart).
     - **Expense Categories Breakdown** (Doughnut/Pie Chart).
   - **Recurring Bills Section**: Tracks due dates, intervals, and paid status. Unpaid bills past their due date are clearly highlighted in **Red**.
   - **Investments & Capital Assets**: Tracks asset purchase price, current manual valuation, dollar gain/loss, and ROI %.
   - **Savings Goal**: Custom savings fund with a real-time progress bar.
   - **1-Click Export to CSV** for records and bookkeeping.
3. **Combined Overview**:
   - Consolidated financials uniting Partner A and Partner B.
   - Visual contribution breakdown and joint asset valuation.
4. **Weekly Task Tracker & Daily Check-in**:
   - Plan weekly tasks with due dates and details.
   - **Daily Check-in View**: Quickly check off tasks scheduled for today.
   - **Weekly Completion Rate**: Visual percentage of completed tasks.
   - **Discipline Streak Counter**: Consecutive days with all due tasks completed.
   - Archive system to preserve history week over week.
5. **Accountability & Consequence System**:
   - Each partner defines their own agreed consequence (e.g., cooking dinner, cleaning workspace, fun treats).
   - Tasks left incomplete past their due date automatically trigger penalties.
   - Pending penalties counter prominently displayed on dashboards so both partners know what is owed.
   - Penalties must be marked completed by the owning partner after fulfillment.

---

## 📁 Project Structure

```
teen buisness track/
│
├── app.py                     # Flask controllers, API endpoints, routing & logic
├── run.py                     # Launcher script (auto-opens web browser)
├── run.bat                    # 1-Click Windows shortcut launcher
├── requirements.txt           # Python dependencies
├── README.md                  # Detailed documentation and user guide
│
├── database/
│   ├── db.py                  # SQLite schemas, connection pool, calculations
│   ├── init_db.py             # Database initialization and sample seed script
│   └── partner_tracker.db     # Local SQLite database file
│
├── static/
│   ├── css/
│   │   └── style.css          # Responsive styling, color coding, mobile UI
│   └── js/
│       └── main.js            # Modal controls, form helpers, delete guards
│
└── templates/
    ├── base.html              # Layout shell with navbar, alerts, modals
    ├── index.html             # Main dashboard overview
    ├── money.html             # Partner money hub, charts, bills, investments
    ├── combined.html          # Joint financial summary & comparisons
    ├── tasks.html             # Weekly task tracker & daily check-in
    ├── penalties.html         # Consequence & accountability board
    └── settings.html          # PIN change and personal consequence config
```

---

## 🚀 Quick Setup & How to Run

### Step 1: Install Dependencies
Open PowerShell or Command Prompt in the project folder and run:
```bash
pip install -r requirements.txt
```
*(Requires Python 3.8+; Flask is the only dependency)*

### Step 2: Initialize Database (Optional, done automatically on first run)
To manually set up or seed the database with sample entries:
```bash
python database/init_db.py
```

### Step 3: Run the Application
You can run it in either of two ways:

- **Option A (1-Click on Windows)**: Double-click `run.bat`.
- **Option B (Command Line)**:
  ```bash
  python run.py
  ```
The app will automatically launch your default browser at:
👉 **`http://127.0.0.1:5000`**

---

## 🔑 Login Codes (PINs)

Each partner has a personal PIN code stored securely hashed (`werkzeug.security` with PBKDF2/SHA256):

| Partner | Default PIN Code | Purpose |
| :--- | :--- | :--- |
| **Partner A** | `111111` | Edit Partner A money, bills, tasks & mark penalties |
| **Partner B** | `222222` | Edit Partner B money, bills, tasks & mark penalties |

### How to Change Your PIN Code
1. Click **"🔑 Partner Login"** in the top navigation bar.
2. Select your partner profile and enter your current PIN.
3. Click **"⚙️ Settings"** in the top navigation bar.
4. Under **"Change Login PIN"**, input your current PIN and choose your new secret code.
5. Click **"Update My PIN Code"**.

---

## 💡 Partnership Agreement & Habit Tips

- **Daily Check-in Habit**: Open the app once every morning or evening. Mark off your tasks for the day and enter business expenses on the same day they happen.
- **Weekly Review**: Every Sunday evening, sit down together and open the **Combined** tab. Review total profit, upcoming bills for the week, and celebrate completed tasks!
- **Consequences**: Agree on motivating, fun, safe, non-harmful penalties (e.g. baking cookies, cleaning shared space, buying coffee).

---

## 🔮 Future Feature Roadmap

Here are recommended extensions for future versions:
1. **Automated Reminders**: Email or Discord/Telegram webhook reminders for overdue bills and pending daily tasks.
2. **Progressive Web App (PWA)**: Installable icon on iPhone/Android home screens for offline mobile tracking.
3. **Receipt & Invoice Uploads**: Attach PDF invoices and receipt images to money transactions.
4. **Live Currency Exchange Rates**: Automatic multi-currency conversion if doing international sales.
5. **Shared Business Bank API Sync**: Direct Plaid or Open Banking synchronization for automatic transaction matching.
