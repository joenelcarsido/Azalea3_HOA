from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from datetime import datetime
import sqlite3, os, uuid

app = FastAPI()

# ---------------- CONFIG ----------------
DB = "hoa.db"
UPLOAD_DIR = "uploads"
STATIC_DIR = "static"

os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ---------------- ROOT (FIX 404) ----------------
@app.get("/")
def root():
    return RedirectResponse(url="/static/login.html")


# ---------------- DB ----------------
def get_db():
    def init_db():
    conn = get_db()
    cur = conn.cursor()

    # users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # payments table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        filename TEXT,
        status TEXT,
        uploaded_at TEXT,
        month TEXT,
        year TEXT,
        amount REAL
    )
    """)

    # default admin
    cur.execute("SELECT * FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", "admin123", "admin")
        )

    conn.commit()
    conn.close()


init_db()

    return sqlite3.connect(DB, check_same_thread=False)


# ---------------- USER UPLOAD ----------------
@app.post("/api/upload-receipt")
async def upload_receipt(
    username: str,
    month: str,
    year: str,
    amount: float = Query(...),
    file: UploadFile = File(...)
):
    conn = get_db()
    cur = conn.cursor()

    filename = f"{uuid.uuid4()}_{file.filename}"
    with open(f"{UPLOAD_DIR}/{filename}", "wb") as f:
        f.write(await file.read())

    cur.execute("""
        INSERT INTO payments
        (username, filename, status, uploaded_at, month, year, amount)
        VALUES (?, ?, 'PENDING', ?, ?, ?, ?)
    """, (
        username,
        filename,
        datetime.utcnow().isoformat(),
        month,
        year,
        amount
    ))

    conn.commit()
    conn.close()
    return {"message": "Receipt uploaded"}


# ---------------- USER HISTORY ----------------
@app.get("/api/user/payments/{username}")
def user_payments(username: str):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, filename, status, uploaded_at, month, year, amount
        FROM payments
        WHERE username=?
        ORDER BY uploaded_at DESC
    """, (username,))

    rows = cur.fetchall()
    conn.close()
    return rows


# ---------------- ADMIN PAYMENTS (FIXED) ----------------
@app.get("/api/admin/payments")
def admin_payments(
    username: str,
    month: str | None = None,
    year: str | None = None
):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT role FROM users WHERE username=?", (username,))
    role = cur.fetchone()
    if not role or role[0] != "admin":
        conn.close()
        raise HTTPException(status_code=403, detail="Forbidden")

    query = """
        SELECT id, username, filename, status, uploaded_at, month, year, amount
        FROM payments WHERE 1=1
    """
    params = []

    if month:
        query += " AND month=?"
        params.append(month)
    if year:
        query += " AND year=?"
        params.append(year)

    query += " ORDER BY uploaded_at DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------------- APPROVE ----------------
@app.post("/api/admin/payments/{pid}/approve")
def approve(pid: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE payments SET status='APPROVED' WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return {"message": "Approved"}


# ---------------- REJECT ----------------
@app.post("/api/admin/payments/{pid}/reject")
def reject(pid: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE payments SET status='REJECTED' WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return {"message": "Rejected"}
