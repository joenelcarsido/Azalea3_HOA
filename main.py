from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from datetime import datetime
import sqlite3, os, uuid

app = FastAPI()

DB = "hoa.db"
UPLOAD_DIR = "uploads"
STATIC_DIR = "static"

os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ---------- ROOT ----------
@app.get("/")
def root():
    return RedirectResponse("/static/login.html")


# ---------- DB ----------
def get_db():
    return sqlite3.connect(DB, check_same_thread=False)


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

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


# ---------- MODELS ----------
class Auth(BaseModel):
    username: str
    password: str


# ---------- REGISTER ----------
@app.post("/api/register")
def register(data: Auth):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, 'homeowner')",
            (data.username, data.password)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already exists")
    finally:
        conn.close()

    return {"message": "Registered successfully"}


# ---------- LOGIN ----------
@app.post("/api/login")
def login(data: Auth):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT role FROM users WHERE username=? AND password=?",
        (data.username, data.password)
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "username": data.username,
        "role": row[0]
    }


# ---------- USER PAYMENTS ----------
@app.get("/api/user/payments/{username}")
def user_payments(username: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, filename, status, uploaded_at, month, year, amount
        FROM payments WHERE username=?
        ORDER BY uploaded_at DESC
    """, (username,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------- UPLOAD RECEIPT ----------
@app.post("/api/upload-receipt")
async def upload_receipt(
    username: str,
    month: str,
    year: str,
    amount: float,
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


# ---------- ADMIN PAYMENTS ----------
@app.get("/api/admin/payments")
def admin_payments(username: str):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT role FROM users WHERE username=?", (username,))
    role = cur.fetchone()
    if not role or role[0] != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    cur.execute("""
        SELECT id, username, filename, status, uploaded_at, month, year, amount
        FROM payments ORDER BY uploaded_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows
