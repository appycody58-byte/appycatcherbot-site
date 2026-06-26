#!/usr/bin/env python3
"""
xBank Demo - Educational Core Banking System (USD)
A simplified, self-contained demo showing realistic transaction flows.
⚠️ FOR EDUCATIONAL PURPOSES ONLY. Not real banking code.
"""

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from datetime import datetime
import os
from typing import Optional

DB_PATH = os.getenv("XBANK_DB_PATH", "xbank.db")
app = FastAPI(
    title="xBank Demo",
    description="Educational core banking demo - transactions, balances, transfers.",
    version="1.0.0-demo"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        balance REAL DEFAULT 0.0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        tx_type TEXT NOT NULL CHECK(tx_type IN ('deposit', 'withdraw', 'transfer_out', 'transfer_in')),
        amount REAL NOT NULL CHECK(amount > 0),
        balance_after REAL NOT NULL,
        description TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        counterparty TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE CASCADE
    )""")

    conn.commit()

    cursor.execute("SELECT COUNT(*) as count FROM users")
    if cursor.fetchone()["count"] == 0:
        demo_data = [
            ("elon", "demo123", 52400000.75, "Initial capital allocation from Tesla/xAI treasury"),
            ("tesla", "demo123", 18750000.00, "Model Y & Cybertruck sales reserve"),
            ("demo_user", "demo123", 250000.00, "Personal demo account")
        ]
        for username, password, initial_balance, note in demo_data:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            user_id = cursor.lastrowid
            cursor.execute("INSERT INTO accounts (user_id, balance) VALUES (?, ?)", (user_id, initial_balance))
            acc_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO transactions 
                (account_id, tx_type, amount, balance_after, description, counterparty)
                VALUES (?, 'deposit', ?, ?, ?, 'System / Treasury Seed')
            """, (acc_id, initial_balance, initial_balance, note))
        conn.commit()
        print("✅ Seeded demo users: elon, tesla, demo_user (password: demo123)")

    conn.close()

init_database()

# ==================== API ENDPOINTS ====================

@app.post("/api/register")
async def api_register(username: str = Form(...), password: str = Form(...)):
    if len(username) < 3 or len(password) < 4:
        raise HTTPException(400, detail="Username (min 3) and password (min 4) required")
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        user_id = cursor.lastrowid
        cursor.execute("INSERT INTO accounts (user_id, balance) VALUES (?, 0.0)", (user_id,))
        conn.commit()
        return {"success": True, "message": "Account created successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(409, detail="Username already taken.")
    finally:
        conn.close()

@app.post("/api/login")
async def api_login(username: str = Form(...), password: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row and row["password"] == password:
        return {"success": True, "username": username}
    raise HTTPException(401, detail="Invalid credentials")

@app.get("/api/balance/{username}")
async def api_balance(username: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT a.balance FROM accounts a JOIN users u ON a.user_id = u.id WHERE u.username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, detail="User not found")
    return {"username": username, "balance": round(row["balance"], 2)}

@app.get("/api/transactions/{username}")
async def api_transactions(username: str, limit: int = 100):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.id, t.tx_type, t.amount, t.balance_after, t.description, t.timestamp, t.counterparty
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        JOIN users u ON a.user_id = u.id
        WHERE u.username = ?
        ORDER BY t.timestamp DESC, t.id DESC LIMIT ?
    """, (username, limit))
    txs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"transactions": txs, "count": len(txs)}

@app.post("/api/deposit")
async def api_deposit(username: str = Form(...), amount: float = Form(...), description: str = Form("Deposit")):
    if amount <= 0:
        raise HTTPException(400, detail="Amount must be > 0")
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT a.id, a.balance FROM accounts a JOIN users u ON a.user_id = u.id WHERE u.username = ?", (username,))
        acc = cursor.fetchone()
        if not acc: raise HTTPException(404, detail="Account not found")
        new_balance = round(acc["balance"] + amount, 2)
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, acc["id"]))
        cursor.execute("""
            INSERT INTO transactions (account_id, tx_type, amount, balance_after, description, counterparty)
            VALUES (?, 'deposit', ?, ?, ?, 'External / Bank Transfer')
        """, (acc["id"], amount, new_balance, description))
        conn.commit()
        return {"success": True, "message": f"Deposited ${amount:,.2f}", "new_balance": new_balance}
    finally:
        conn.close()

@app.post("/api/withdraw")
async def api_withdraw(username: str = Form(...), amount: float = Form(...), description: str = Form("Withdrawal")):
    if amount <= 0: raise HTTPException(400, detail="Amount must be > 0")
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT a.id, a.balance FROM accounts a JOIN users u ON a.user_id = u.id WHERE u.username = ?", (username,))
        acc = cursor.fetchone()
        if not acc: raise HTTPException(404, detail="Account not found")
        if acc["balance"] < amount: raise HTTPException(400, detail=f"Insufficient funds: ${acc['balance']:,.2f}")
        new_balance = round(acc["balance"] - amount, 2)
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, acc["id"]))
        cursor.execute("""
            INSERT INTO transactions (account_id, tx_type, amount, balance_after, description, counterparty)
            VALUES (?, 'withdraw', ?, ?, ?, 'Self / ATM')
        """, (acc["id"], amount, new_balance, description))
        conn.commit()
        return {"success": True, "message": f"Withdrew ${amount:,.2f}", "new_balance": new_balance}
    finally:
        conn.close()

@app.post("/api/transfer")
async def api_transfer(from_username: str = Form(...), to_username: str = Form(...), amount: float = Form(...), description: str = Form("Transfer")):
    """Core atomic transfer logic."""
    if amount <= 0: raise HTTPException(400, detail="Amount must be > 0")
    if from_username.lower() == to_username.lower(): raise HTTPException(400, detail="Cannot transfer to self")
    conn = get_db()
    try:
        cursor = conn.cursor()
        # Sender
        cursor.execute("SELECT a.id, a.balance FROM accounts a JOIN users u ON a.user_id = u.id WHERE u.username = ?", (from_username,))
        from_acc = cursor.fetchone()
        if not from_acc: raise HTTPException(404, detail="Sender not found")
        if from_acc["balance"] < amount: raise HTTPException(400, detail=f"Insufficient funds: ${from_acc['balance']:,.2f}")
        
        # Receiver
        cursor.execute("SELECT a.id FROM accounts a JOIN users u ON a.user_id = u.id WHERE u.username = ?", (to_username,))
        to_acc = cursor.fetchone()
        if not to_acc: raise HTTPException(404, detail="Recipient not found")

        new_from = round(from_acc["balance"] - amount, 2)
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_from, from_acc["id"]))

        cursor.execute("SELECT balance FROM accounts WHERE id = ?", (to_acc["id"],))
        to_current = cursor.fetchone()["balance"]
        new_to = round(to_current + amount, 2)
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_to, to_acc["id"]))

        # Double-entry records
        cursor.execute("""
            INSERT INTO transactions (account_id, tx_type, amount, balance_after, description, counterparty)
            VALUES (?, 'transfer_out', ?, ?, ?, ?)
        """, (from_acc["id"], amount, new_from, description, to_username))
        cursor.execute("""
            INSERT INTO transactions (account_id, tx_type, amount, balance_after, description, counterparty)
            VALUES (?, 'transfer_in', ?, ?, ?, ?)
        """, (to_acc["id"], amount, new_to, description, from_username))

        conn.commit()
        return {"success": True, "message": f"Transferred ${amount:,.2f} to {to_username}"}
    finally:
        conn.close()

@app.get("/api/users")
async def api_list_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT u.username, a.balance FROM users u JOIN accounts a ON u.id = a.user_id ORDER BY u.created_at DESC")
    users = [{"username": row["username"], "balance": round(row["balance"], 2)} for row in cursor.fetchall()]
    conn.close()
    return {"users": users}

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return HTMLResponse(content="""<!DOCTYPE html>
<html>
<head><title>xBank Demo</title></head>
<body><h1>xBank Demo API Running</h1>
<p>Visit API docs: <a href='/docs'>/docs</a></p>
</body></html>""")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)