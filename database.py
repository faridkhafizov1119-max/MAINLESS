"""Локальная база данных FAMdefense (SQLite, работает без интернета)."""
from __future__ import annotations

import csv
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).resolve().parent / "famdefense.db"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def month_bounds(month: str) -> tuple[str, str]:
    """('2026-11') -> ('2026-11-01', '2026-11-31'); строки ISO сравниваются корректно."""
    return f"{month}-01", f"{month}-31"


# ─────────────────────────── Создание таблиц ───────────────────────────

def initialize_database() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
                full_name     TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at    TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL,
                transaction_type TEXT NOT NULL CHECK (transaction_type IN ('income', 'expense')),
                category         TEXT NOT NULL,
                amount           REAL NOT NULL CHECK (amount > 0),
                note             TEXT,
                transaction_date TEXT NOT NULL,
                created_at       TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_tx_user_date
                ON transactions (user_id, transaction_date);

            CREATE TABLE IF NOT EXISTS bills (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                kind        TEXT NOT NULL,
                period      TEXT NOT NULL,
                consumption REAL,
                amount      REAL NOT NULL,
                due_date    TEXT NOT NULL,
                paid_date   TEXT,
                note        TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_bills_user ON bills (user_id, period);

            CREATE TABLE IF NOT EXISTS budgets (
                user_id       INTEGER NOT NULL,
                category      TEXT NOT NULL,
                monthly_limit REAL NOT NULL,
                PRIMARY KEY (user_id, category)
            );

            CREATE TABLE IF NOT EXISTS goals (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                name          TEXT NOT NULL,
                target_amount REAL NOT NULL,
                saved_amount  REAL NOT NULL DEFAULT 0,
                deadline      TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER NOT NULL,
                key     TEXT NOT NULL,
                value   TEXT,
                PRIMARY KEY (user_id, key)
            );
            """
        )


# ─────────────────────────── Пользователи ───────────────────────────

def get_user_by_username(username: str) -> dict | None:
    with connect() as db:
        row = db.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()
    return dict(row) if row else None


def create_user(username: str, full_name: str, password_hash: str, salt: str) -> int:
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO users (username, full_name, password_hash, password_salt) "
            "VALUES (?, ?, ?, ?)",
            (username, full_name, password_hash, salt),
        )
        return int(cursor.lastrowid)


def update_full_name(user_id: int, full_name: str) -> None:
    with connect() as db:
        db.execute("UPDATE users SET full_name = ? WHERE id = ?", (full_name, user_id))


def update_password(user_id: int, password_hash: str, salt: str) -> None:
    with connect() as db:
        db.execute(
            "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
            (password_hash, salt, user_id),
        )


def clear_user_data(user_id: int) -> None:
    """Удаляет все финансовые данные пользователя, но оставляет сам аккаунт."""
    with connect() as db:
        for table in ("transactions", "bills", "budgets", "goals"):
            db.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))


def delete_user(user_id: int) -> None:
    clear_user_data(user_id)
    with connect() as db:
        db.execute("DELETE FROM settings WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ─────────────────────────── Операции ───────────────────────────

def add_transaction(user_id: int, transaction_type: str, category: str,
                    amount: float, note: str, transaction_date: str) -> int:
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO transactions "
            "(user_id, transaction_type, category, amount, note, transaction_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, transaction_type, category, amount, (note or "").strip(), transaction_date),
        )
        return int(cursor.lastrowid)


def update_transaction(user_id: int, transaction_id: int, category: str,
                       amount: float, note: str, transaction_date: str) -> bool:
    with connect() as db:
        cursor = db.execute(
            "UPDATE transactions SET category = ?, amount = ?, note = ?, transaction_date = ? "
            "WHERE id = ? AND user_id = ?",
            (category, amount, (note or "").strip(), transaction_date, transaction_id, user_id),
        )
        return cursor.rowcount > 0


def delete_transaction(user_id: int, transaction_id: int) -> bool:
    with connect() as db:
        cursor = db.execute(
            "DELETE FROM transactions WHERE id = ? AND user_id = ?", (transaction_id, user_id)
        )
        return cursor.rowcount > 0


def list_transactions(user_id: int, transaction_type: str | None = None,
                      limit: int | None = None, start: str | None = None,
                      end: str | None = None, month: str | None = None) -> list[dict]:
    """Операции пользователя, новые сверху. start/end/month — необязательные фильтры."""
    if month:
        start, end = month_bounds(month)
    sql = "SELECT * FROM transactions WHERE user_id = ?"
    params: list = [user_id]
    if transaction_type:
        sql += " AND transaction_type = ?"
        params.append(transaction_type)
    if start:
        sql += " AND transaction_date >= ?"
        params.append(start)
    if end:
        sql += " AND transaction_date <= ?"
        params.append(end)
    sql += " ORDER BY transaction_date DESC, id DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    with connect() as db:
        return [dict(row) for row in db.execute(sql, params).fetchall()]


def get_financial_summary(user_id: int, month: str) -> dict:
    start, end = month_bounds(month)
    with connect() as db:
        row = db.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN transaction_type = 'income'  THEN amount END), 0) AS total_income,
              COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount END), 0) AS total_expense,
              COALESCE(SUM(CASE WHEN transaction_type = 'income'
                    AND transaction_date BETWEEN ? AND ? THEN amount END), 0) AS month_income,
              COALESCE(SUM(CASE WHEN transaction_type = 'expense'
                    AND transaction_date BETWEEN ? AND ? THEN amount END), 0) AS month_expense
            FROM transactions WHERE user_id = ?
            """,
            (start, end, start, end, user_id),
        ).fetchone()
    result = dict(row)
    result["balance"] = result["total_income"] - result["total_expense"]
    return result


def export_transactions_csv(path: str, rows: list[dict]) -> None:
    """Сохраняет список операций в CSV (кодировка и разделитель удобны для Excel)."""
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(["Дата", "Тип", "Категория", "Сумма", "Комментарий"])
        for r in rows:
            writer.writerow([
                r["transaction_date"],
                "Доход" if r["transaction_type"] == "income" else "Расход",
                r["category"], int(r["amount"]), r["note"] or "",
            ])


# ─────────────────────────── Коммунальные счета ───────────────────────────

def add_bill(user_id: int, kind: str, period: str, consumption: float | None,
             amount: float, due_date: str, note: str = "") -> int:
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO bills (user_id, kind, period, consumption, amount, due_date, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, kind, period, consumption, amount, due_date, note),
        )
        return int(cursor.lastrowid)


def list_bills(user_id: int, unpaid_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM bills WHERE user_id = ?"
    if unpaid_only:
        sql += " AND paid_date IS NULL"
        sql += " ORDER BY due_date ASC, id ASC"
    else:
        sql += " ORDER BY period DESC, id DESC"
    with connect() as db:
        return [dict(row) for row in db.execute(sql, (user_id,)).fetchall()]


def set_bill_paid(user_id: int, bill_id: int, paid_date: str | None) -> bool:
    with connect() as db:
        cursor = db.execute(
            "UPDATE bills SET paid_date = ? WHERE id = ? AND user_id = ?",
            (paid_date, bill_id, user_id),
        )
        return cursor.rowcount > 0


def delete_bill(user_id: int, bill_id: int) -> bool:
    with connect() as db:
        cursor = db.execute("DELETE FROM bills WHERE id = ? AND user_id = ?", (bill_id, user_id))
        return cursor.rowcount > 0


# ─────────────────────────── Бюджеты (лимиты по категориям) ───────────────────────────

def get_budgets(user_id: int) -> dict[str, float]:
    with connect() as db:
        rows = db.execute(
            "SELECT category, monthly_limit FROM budgets WHERE user_id = ?", (user_id,)
        ).fetchall()
    return {row["category"]: row["monthly_limit"] for row in rows}


def set_budget(user_id: int, category: str, monthly_limit: float) -> None:
    """Лимит 0 (или меньше) удаляет ограничение."""
    with connect() as db:
        if monthly_limit <= 0:
            db.execute("DELETE FROM budgets WHERE user_id = ? AND category = ?",
                       (user_id, category))
        else:
            db.execute(
                "INSERT INTO budgets (user_id, category, monthly_limit) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, category) DO UPDATE SET monthly_limit = excluded.monthly_limit",
                (user_id, category, monthly_limit),
            )


# ─────────────────────────── Цели накоплений ───────────────────────────

def list_goals(user_id: int) -> list[dict]:
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM goals WHERE user_id = ? ORDER BY id DESC", (user_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def add_goal(user_id: int, name: str, target_amount: float, saved_amount: float,
             deadline: str | None) -> int:
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO goals (user_id, name, target_amount, saved_amount, deadline) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, name, target_amount, saved_amount, deadline),
        )
        return int(cursor.lastrowid)


def add_to_goal(user_id: int, goal_id: int, amount: float) -> bool:
    with connect() as db:
        cursor = db.execute(
            "UPDATE goals SET saved_amount = saved_amount + ? WHERE id = ? AND user_id = ?",
            (amount, goal_id, user_id),
        )
        return cursor.rowcount > 0


def delete_goal(user_id: int, goal_id: int) -> bool:
    with connect() as db:
        cursor = db.execute("DELETE FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id))
        return cursor.rowcount > 0


# ─────────────────────────── Настройки и резервная копия ───────────────────────────

def get_setting(user_id: int, key: str, default: str | None = None) -> str | None:
    with connect() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE user_id = ? AND key = ?", (user_id, key)
        ).fetchone()
    return row["value"] if row else default


def set_setting(user_id: int, key: str, value: str) -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
            (user_id, key, value),
        )


def backup_database(destination: str) -> None:
    source = sqlite3.connect(DB_PATH)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
