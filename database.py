import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from config import settings

@contextmanager
def get_db():
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def init_db():
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            first_name TEXT,
            base_currency TEXT DEFAULT 'EUR',
            plan TEXT DEFAULT 'free',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            amount_original REAL NOT NULL,
            currency_original TEXT NOT NULL,
            amount_base REAL NOT NULL,
            base_currency TEXT NOT NULL,
            direction TEXT NOT NULL,
            source TEXT, category TEXT, note TEXT, fx_rate REAL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            amount_base REAL NOT NULL,
            kind TEXT DEFAULT 'manual',
            is_liquid INTEGER DEFAULT 0,
            is_crypto INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, name))""")
        db.execute("""CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            amount_base REAL NOT NULL,
            interest_rate REAL DEFAULT 0,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, name))""")
        db.execute("""CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            target_amount REAL NOT NULL,
            target_months INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            completed INTEGER DEFAULT 0)""")
        db.execute("""CREATE TABLE IF NOT EXISTS wealth_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            net_worth_base REAL NOT NULL,
            base_currency TEXT NOT NULL)""")

def get_user_by_email(email):
    with get_db() as db:
        return db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

def get_user_by_id(user_id):
    with get_db() as db:
        return db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()

def create_user(email, hashed_password, first_name, base_currency="EUR"):
    ts = now_iso()
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO users(email,hashed_password,first_name,base_currency,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (email, hashed_password, first_name, base_currency, ts, ts))
        return cur.lastrowid

def add_transaction(user_id, amount_original, currency_original, amount_base,
                    base_currency, direction, source=None, category=None, note=None, fx_rate=None):
    with get_db() as db:
        cur = db.execute("""INSERT INTO transactions
            (user_id,ts,amount_original,currency_original,amount_base,base_currency,
             direction,source,category,note,fx_rate) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, now_iso(), amount_original, currency_original, amount_base,
             base_currency, direction, source, category, note, fx_rate))
        return cur.lastrowid

def delete_last_transaction(user_id):
    with get_db() as db:
        row = db.execute("SELECT id FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        if not row: return False
        db.execute("DELETE FROM transactions WHERE id=?", (row["id"],))
        return True

def list_transactions(user_id, limit=20):
    with get_db() as db:
        return db.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()

def transactions_this_month(user_id):
    ym = datetime.now(timezone.utc).strftime("%Y-%m")
    with get_db() as db:
        return db.execute("SELECT * FROM transactions WHERE user_id=? AND substr(ts,1,7)=?", (user_id, ym)).fetchall()

def month_cashflow(user_id):
    rows = transactions_this_month(user_id)
    income   = sum(r["amount_base"] for r in rows if r["direction"] == "income")
    expenses = sum(r["amount_base"] for r in rows if r["direction"] == "expense")
    surplus  = income - expenses
    savings_rate = (surplus / income * 100) if income > 0 else 0
    return {"income": income, "expenses": expenses, "surplus": surplus, "savings_rate": round(savings_rate, 1)}

def upsert_asset(user_id, name, amount_base, kind="manual", is_liquid=0, is_crypto=0):
    with get_db() as db:
        db.execute("""INSERT INTO assets(user_id,name,amount_base,kind,is_liquid,is_crypto,updated_at)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id,name) DO UPDATE SET
            amount_base=excluded.amount_base, is_liquid=excluded.is_liquid,
            is_crypto=excluded.is_crypto, updated_at=excluded.updated_at""",
            (user_id, name, amount_base, kind, int(is_liquid), int(is_crypto), now_iso()))

def upsert_debt(user_id, name, amount_base, interest_rate=0):
    with get_db() as db:
        db.execute("""INSERT INTO debts(user_id,name,amount_base,interest_rate,updated_at)
            VALUES(?,?,?,?,?) ON CONFLICT(user_id,name) DO UPDATE SET
            amount_base=excluded.amount_base, interest_rate=excluded.interest_rate,
            updated_at=excluded.updated_at""",
            (user_id, name, amount_base, interest_rate, now_iso()))

def all_assets(user_id):
    with get_db() as db:
        return db.execute("SELECT * FROM assets WHERE user_id=? ORDER BY amount_base DESC", (user_id,)).fetchall()

def all_debts(user_id):
    with get_db() as db:
        return db.execute("SELECT * FROM debts WHERE user_id=? ORDER BY interest_rate DESC", (user_id,)).fetchall()

def net_worth(user_id):
    assets = all_assets(user_id)
    debts  = all_debts(user_id)
    total_assets = sum(a["amount_base"] for a in assets)
    total_debts  = sum(d["amount_base"] for d in debts)
    return {"net_worth": total_assets - total_debts, "total_assets": total_assets,
            "total_debts": total_debts, "assets": [dict(a) for a in assets], "debts": [dict(d) for d in debts]}

def emergency_months(user_id):
    assets = all_assets(user_id)
    liquid = sum(a["amount_base"] for a in assets if a["is_liquid"])
    if not liquid: return None
    cf = month_cashflow(user_id)
    if not cf["expenses"]: return None
    return round(liquid / cf["expenses"], 1)

def wealth_score(user_id):
    cf = month_cashflow(user_id)
    nw = net_worth(user_id)
    em = emergency_months(user_id)
    score = 0
    if cf["savings_rate"] >= 50: score += 30
    elif cf["savings_rate"] >= 20: score += 20
    elif cf["savings_rate"] > 0: score += 10
    if em and em >= 6: score += 25
    elif em and em >= 3: score += 15
    if nw["net_worth"] > 0: score += 20
    if nw["total_debts"] == 0: score += 15
    assets = nw["assets"]
    if nw["total_assets"] > 0:
        crypto = sum(a["amount_base"] for a in assets if a["is_crypto"])
        if crypto / nw["total_assets"] * 100 < 20: score += 10
    return max(0, min(100, score))

def add_snapshot(user_id, base_currency):
    nw = net_worth(user_id)
    with get_db() as db:
        db.execute("INSERT INTO wealth_snapshots(user_id,ts,net_worth_base,base_currency) VALUES(?,?,?,?)",
            (user_id, now_iso(), nw["net_worth"], base_currency))
    return nw["net_worth"]

def create_goal(user_id, title, target_amount, target_months):
    with get_db() as db:
        cur = db.execute("INSERT INTO goals(user_id,title,target_amount,target_months,created_at) VALUES(?,?,?,?,?)",
            (user_id, title, target_amount, target_months, now_iso()))
        return cur.lastrowid

def list_goals(user_id):
    with get_db() as db:
        return db.execute("SELECT * FROM goals WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()

def get_snapshots(user_id, limit=50):
    with get_db() as db:
        return db.execute("SELECT * FROM wealth_snapshots WHERE user_id=? ORDER BY ts ASC LIMIT ?", (user_id, limit)).fetchall()
