import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from datetime import datetime, timezone

DATABASE_URL = os.environ.get('DATABASE_URL') or 'postgresql://postgres:nCUgIiBvJacjJAlgirvhptvZjyxjMRtN@nozomi.proxy.rlwy.net:23013/railway'

@contextmanager
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def init_db():
    with get_db() as db:
        cur = db.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            first_name TEXT,
            base_currency TEXT DEFAULT 'EUR',
            created_at TEXT
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS transactions (
            tx_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id),
            amount REAL,
            currency TEXT,
            amount_base REAL,
            fx_rate REAL DEFAULT 1.0,
            direction TEXT,
            category TEXT,
            note TEXT,
            ts TEXT
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS assets (
            asset_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id),
            name TEXT,
            amount REAL,
            currency TEXT,
            amount_base REAL,
            is_liquid INTEGER DEFAULT 0,
            created_at TEXT
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS debts (
            debt_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id),
            name TEXT,
            amount REAL,
            currency TEXT,
            amount_base REAL,
            interest_rate REAL DEFAULT 0,
            created_at TEXT
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS goals (
            goal_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id),
            title TEXT,
            target_amount REAL,
            current_amount REAL DEFAULT 0,
            target_months INTEGER,
            created_at TEXT
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            snap_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id),
            net_worth REAL,
            total_assets REAL,
            total_debts REAL,
            ts TEXT
        )""")
        db.commit()

def row_to_dict(row, cursor):
    if row is None:
        return None
    cols = [desc[0] for desc in cursor.description]
    return dict(zip(cols, row))

def rows_to_dicts(rows, cursor):
    cols = [desc[0] for desc in cursor.description]
    return [dict(zip(cols, row)) for row in rows]

def get_user_by_email(email):
    with get_db() as db:
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        return row_to_dict(cur.fetchone(), cur)

def get_user_by_id(user_id):
    with get_db() as db:
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
        return row_to_dict(cur.fetchone(), cur)

def create_user(email, password_hash, first_name, base_currency='EUR'):
    with get_db() as db:
        cur = db.cursor()
        cur.execute(
            "INSERT INTO users (email, password_hash, first_name, base_currency, created_at) VALUES (%s,%s,%s,%s,%s) RETURNING *",
            (email, password_hash, first_name, base_currency, now_iso())
        )
        return row_to_dict(cur.fetchone(), cur)

def add_transaction(user_id, amount, currency, amount_base, fx_rate, direction, category, note):
    with get_db() as db:
        cur = db.cursor()
        cur.execute(
            "INSERT INTO transactions (user_id,amount,currency,amount_base,fx_rate,direction,category,note,ts) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (user_id, amount, currency, amount_base, fx_rate, direction, category, note, now_iso())
        )
        return row_to_dict(cur.fetchone(), cur)

def get_transactions(user_id, limit=50):
    with get_db() as db:
        cur = db.cursor()
        cur.execute("SELECT * FROM transactions WHERE user_id=%s ORDER BY ts DESC LIMIT %s", (user_id, limit))
        return rows_to_dicts(cur.fetchall(), cur)

def delete_transaction(tx_id, user_id):
    with get_db() as db:
        cur = db.cursor()
        cur.execute("DELETE FROM transactions WHERE tx_id=%s AND user_id=%s", (tx_id, user_id))

def get_month_cashflow(user_id):
    with get_db() as db:
        cur = db.cursor()
        month = datetime.now().strftime('%Y-%m')
        cur.execute("SELECT direction, SUM(amount_base) as total FROM transactions WHERE user_id=%s AND ts LIKE %s GROUP BY direction", (user_id, month+'%'))
        rows = rows_to_dicts(cur.fetchall(), cur)
        income = next((r['total'] for r in rows if r['direction'] == 'income'), 0) or 0
        expenses = next((r['total'] for r in rows if r['direction'] == 'expense'), 0) or 0
        return {'income': income, 'expenses': expenses, 'surplus': income - expenses, 'savings_rate': (income - expenses) / income * 100 if income > 0 else 0}

def add_asset(user_id, name, amount, currency, amount_base, is_liquid):
    with get_db() as db:
        cur = db.cursor()
        cur.execute(
            "INSERT INTO assets (user_id,name,amount,currency,amount_base,is_liquid,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (user_id, name, amount, currency, amount_base, 1 if is_liquid else 0, now_iso())
        )
        return row_to_dict(cur.fetchone(), cur)

def get_assets(user_id):
    with get_db() as db:
        cur = db.cursor()
        cur.execute("SELECT * FROM assets WHERE user_id=%s", (user_id,))
        return rows_to_dicts(cur.fetchall(), cur)

def get_debts(user_id):
    with get_db() as db:
        cur = db.cursor()
        cur.execute("SELECT * FROM debts WHERE user_id=%s", (user_id,))
        return rows_to_dicts(cur.fetchall(), cur)

def add_goal(user_id, title, target_amount, target_months):
    with get_db() as db:
        cur = db.cursor()
        cur.execute(
            "INSERT INTO goals (user_id,title,target_amount,target_months,created_at) VALUES (%s,%s,%s,%s,%s) RETURNING *",
            (user_id, title, target_amount, target_months, now_iso())
        )
        return row_to_dict(cur.fetchone(), cur)

def get_goals(user_id):
    with get_db() as db:
        cur = db.cursor()
        cur.execute("SELECT * FROM goals WHERE user_id=%s ORDER BY created_at DESC", (user_id,))
        return rows_to_dicts(cur.fetchall(), cur)

def save_snapshot(user_id, net_worth, total_assets, total_debts):
    with get_db() as db:
        cur = db.cursor()
        cur.execute(
            "INSERT INTO snapshots (user_id,net_worth,total_assets,total_debts,ts) VALUES (%s,%s,%s,%s,%s)",
            (user_id, net_worth, total_assets, total_debts, now_iso())
        )

def get_snapshots(user_id, limit=30):
    with get_db() as db:
        cur = db.cursor()
        cur.execute("SELECT * FROM snapshots WHERE user_id=%s ORDER BY ts DESC LIMIT %s", (user_id, limit))
        return rows_to_dicts(cur.fetchall(), cur)
