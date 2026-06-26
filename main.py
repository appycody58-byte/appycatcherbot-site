#!/usr/bin/env python3
"""
Tesla / xBank Demo - Professional Educational Banking System
Optimized for Render.com
⚠️ FOR EDUCATIONAL PURPOSES ONLY
"""

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
from datetime import datetime
from pathlib import Path

app = FastAPI(
    title="xBank Demo API",
    description="Educational banking system with transactions and account management",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config
DB_PATH = os.getenv("XBANK_DB_PATH", "xbank.db")
PORT = int(os.getenv("PORT", 8000))

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database with schema"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            balance REAL DEFAULT 0.0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            tx_type TEXT NOT NULL CHECK(tx_type IN ('deposit', 'withdraw', 'transfer_out', 'transfer_in')),
            amount REAL NOT NULL CHECK(amount > 0),
            balance_after REAL NOT NULL,
            description TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            counterparty TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE CASCADE
        );
    """)
    
    # Seed demo data
    cursor.execute("SELECT COUNT(*) as cnt FROM users")
    if cursor.fetchone()["cnt"] == 0:
        demo_users = [
            ("elon", "demo123", 52400000.75, "Elon - CEO Demo Account"),
            ("tesla", "demo123", 18750000.00, "Tesla - Corporate Account"),
            ("demo_user", "demo123", 250000.00, "Demo User - Personal Account")
        ]
        
        for username, password, balance, desc in demo_users:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            user_id = cursor.lastrowid
            cursor.execute("INSERT INTO accounts (user_id, balance) VALUES (?, ?)", (user_id, balance))
            account_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO transactions (account_id, tx_type, amount, balance_after, description, counterparty)
                VALUES (?, 'deposit', ?, ?, ?, 'System / Treasury')
            """, (account_id, balance, balance, desc))
        
        conn.commit()
        print("✅ Demo users seeded: elon, tesla, demo_user (password: demo123)")
    
    conn.close()

# Initialize on startup
init_database()

# ==================== AUTHENTICATION ====================

@app.post("/api/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """User login endpoint"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE username = ? AND password = ?", (username, password))
        row = cursor.fetchone()
        
        if row:
            return {"success": True, "username": username, "message": "Login successful"}
        raise HTTPException(401, detail="Invalid credentials")
    finally:
        conn.close()

@app.post("/api/register")
async def register(username: str = Form(...), password: str = Form(...)):
    """User registration endpoint"""
    if len(username) < 3 or len(password) < 4:
        raise HTTPException(400, detail="Username min 3 chars, password min 4 chars")
    
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        user_id = cursor.lastrowid
        cursor.execute("INSERT INTO accounts (user_id, balance) VALUES (?, 0.0)", (user_id,))
        conn.commit()
        return {"success": True, "message": "Account created successfully"}
    except sqlite3.IntegrityError:
        raise HTTPException(409, detail="Username already taken")
    finally:
        conn.close()

# ==================== ACCOUNT ENDPOINTS ====================

@app.get("/api/balance/{username}")
async def get_balance(username: str):
    """Get account balance"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.balance FROM accounts a 
            JOIN users u ON a.user_id = u.id 
            WHERE u.username = ?
        """, (username,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(404, detail="User not found")
        
        return {"username": username, "balance": round(row["balance"], 2)}
    finally:
        conn.close()

@app.get("/api/transactions/{username}")
async def get_transactions(username: str, limit: int = 100):
    """Get transaction history"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tx_type, amount, balance_after, description, timestamp, counterparty
            FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            JOIN users u ON a.user_id = u.id
            WHERE u.username = ?
            ORDER BY timestamp DESC, t.id DESC
            LIMIT ?
        """, (username, limit))
        
        transactions = [dict(row) for row in cursor.fetchall()]
        return {"username": username, "transactions": transactions, "count": len(transactions)}
    finally:
        conn.close()

@app.get("/api/users")
async def list_users():
    """List all users with balances (demo endpoint)"""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.username, a.balance FROM users u 
            JOIN accounts a ON u.id = a.user_id 
            ORDER BY u.created_at DESC
        """)
        users = [{"username": row["username"], "balance": round(row["balance"], 2)} for row in cursor.fetchall()]
        return {"users": users}
    finally:
        conn.close()

# ==================== TRANSACTION ENDPOINTS ====================

@app.post("/api/deposit")
async def deposit(username: str = Form(...), amount: float = Form(...), description: str = Form("Deposit")):
    """Deposit funds to account"""
    if amount <= 0:
        raise HTTPException(400, detail="Amount must be greater than 0")
    
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.balance FROM accounts a 
            JOIN users u ON a.user_id = u.id 
            WHERE u.username = ?
        """, (username,))
        account = cursor.fetchone()
        
        if not account:
            raise HTTPException(404, detail="Account not found")
        
        new_balance = round(account["balance"] + amount, 2)
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, account["id"]))
        cursor.execute("""
            INSERT INTO transactions (account_id, tx_type, amount, balance_after, description, counterparty)
            VALUES (?, 'deposit', ?, ?, ?, 'External / Bank Transfer')
        """, (account["id"], amount, new_balance, description))
        conn.commit()
        
        return {"success": True, "message": f"Deposited ${amount:,.2f}", "new_balance": new_balance}
    finally:
        conn.close()

@app.post("/api/withdraw")
async def withdraw(username: str = Form(...), amount: float = Form(...), description: str = Form("Withdrawal")):
    """Withdraw funds from account"""
    if amount <= 0:
        raise HTTPException(400, detail="Amount must be greater than 0")
    
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.balance FROM accounts a 
            JOIN users u ON a.user_id = u.id 
            WHERE u.username = ?
        """, (username,))
        account = cursor.fetchone()
        
        if not account:
            raise HTTPException(404, detail="Account not found")
        
        if account["balance"] < amount:
            raise HTTPException(400, detail=f"Insufficient funds: ${account['balance']:,.2f}")
        
        new_balance = round(account["balance"] - amount, 2)
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, account["id"]))
        cursor.execute("""
            INSERT INTO transactions (account_id, tx_type, amount, balance_after, description, counterparty)
            VALUES (?, 'withdraw', ?, ?, ?, 'Self / ATM')
        """, (account["id"], amount, new_balance, description))
        conn.commit()
        
        return {"success": True, "message": f"Withdrew ${amount:,.2f}", "new_balance": new_balance}
    finally:
        conn.close()

@app.post("/api/transfer")
async def transfer(
    from_username: str = Form(...),
    to_username: str = Form(...),
    amount: float = Form(...),
    description: str = Form("Transfer")
):
    """Transfer funds between accounts"""
    if amount <= 0:
        raise HTTPException(400, detail="Amount must be greater than 0")
    
    if from_username.lower() == to_username.lower():
        raise HTTPException(400, detail="Cannot transfer to self")
    
    conn = get_db()
    try:
        cursor = conn.cursor()
        
        # Get sender account
        cursor.execute("""
            SELECT a.id, a.balance FROM accounts a 
            JOIN users u ON a.user_id = u.id 
            WHERE u.username = ?
        """, (from_username,))
        from_account = cursor.fetchone()
        
        if not from_account:
            raise HTTPException(404, detail="Sender not found")
        
        if from_account["balance"] < amount:
            raise HTTPException(400, detail=f"Insufficient funds: ${from_account['balance']:,.2f}")
        
        # Get recipient account
        cursor.execute("""
            SELECT a.id, a.balance FROM accounts a 
            JOIN users u ON a.user_id = u.id 
            WHERE u.username = ?
        """, (to_username,))
        to_account = cursor.fetchone()
        
        if not to_account:
            raise HTTPException(404, detail="Recipient not found")
        
        # Perform transfer (atomic transaction)
        from_new_balance = round(from_account["balance"] - amount, 2)
        to_new_balance = round(to_account["balance"] + amount, 2)
        
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (from_new_balance, from_account["id"]))
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (to_new_balance, to_account["id"]))
        
        # Log transaction for both accounts (double-entry)
        cursor.execute("""
            INSERT INTO transactions (account_id, tx_type, amount, balance_after, description, counterparty)
            VALUES (?, 'transfer_out', ?, ?, ?, ?)
        """, (from_account["id"], amount, from_new_balance, description, to_username))
        
        cursor.execute("""
            INSERT INTO transactions (account_id, tx_type, amount, balance_after, description, counterparty)
            VALUES (?, 'transfer_in', ?, ?, ?, ?)
        """, (to_account["id"], amount, to_new_balance, description, from_username))
        
        conn.commit()
        
        return {
            "success": True,
            "message": f"Transferred ${amount:,.2f} to {to_username}",
            "from_balance": from_new_balance,
            "to_balance": to_new_balance
        }
    finally:
        conn.close()

# ==================== FRONTEND ====================

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve main HTML interface"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("""
        <html>
            <head><title>xBank Demo</title></head>
            <body style="font-family: Arial; padding: 20px;">
                <h1>🏦 xBank Demo API</h1>
                <p>API is running! Check <a href="/docs">/docs</a> for interactive documentation.</p>
                <hr>
                <h2>Quick Start:</h2>
                <ul>
                    <li><strong>API Docs:</strong> <a href="/docs">/docs</a></li>
                    <li><strong>Demo Users:</strong> elon, tesla, demo_user (password: demo123)</li>
                    <li><strong>List Users:</strong> <a href="/api/users">/api/users</a></li>
                </ul>
                <p><em>Upload index.html to repo root for full UI</em></p>
            </body>
        </html>
        """, status_code=200)

@app.get("/api/health")
async def health_check():
    """Health check endpoint for Render"""
    return {"status": "healthy", "service": "xBank Demo API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
