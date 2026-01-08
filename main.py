# =======================
# main.py
# =======================

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime
import sqlite3
import os
import uuid

# ---------------- CONFIG ----------------
DB = "hoa.db"
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 5 * 1024 * 1024

os.makedirs(UPLOAD_DIR, exist_ok=True)

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# ---------------- DB ----------------
def get_db():
    return sqlite3.connect(DB, check_same_thread=False)

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)

def is_admin(username: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    return row and row[0] == "admin"

# ---------------- INIT ----------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL
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
        year TEXT
    )
    """)

    conn.commit()
    conn.close()

def ensure_admin():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            ("admin", hash_password("admin123"), "admin")
        )
        conn.commit()
    conn.close()

# ---------------- APP ----------------
app = FastAPI()

init_db()
ensure_admin()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ---------------- PAGES ----------------
@app.get("/")
def root():
    return FileResponse("static/login.html")

@app.get("/login")
def login_page():
    return FileResponse("static/login.html")

@app.get("/register")
def register_page():
    return FileResponse("static/register.html")

# ---------------- MODELS ----------------
class LoginData(BaseModel):
    username: str
    password: str

class RegisterData(BaseModel):
    username: str
    password: str

# ---------------- AUTH ----------------
@app.post("/api/register")
def register(data: RegisterData):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            (data.username, hash_password(data.password), "homeowner")
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Username exists")
    finally:
        conn.close()
    return {"message": "Registered"}

@app.post("/api/login")
def login(data: LoginData):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT password, role FROM users WHERE username=?",
        (data.username,)
    )
    row = cur.fetchone()
    conn.close()

    if not row or not verify_password(data.password, row[0]):
        raise HTTPException(401, "Invalid credentials")

    return {"username": data.username, "role": row[1]}

# ---------------- UPLOAD RECEIPT (FIXED) ----------------
@app.post("/api/upload-receipt")
async def upload_receipt(
    username: str = Query(...),
    month: str = Query(...),
    year: str = Query(...),
    file: UploadFile = File(...)
):
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".pdf")):
        raise HTTPException(400, "Invalid file type")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large")

    filename = f"{uuid.uuid4()}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT 1 FROM payments WHERE username=? AND month=? AND year=?",
        (username, month, year)
    )
    if cur.fetchone():
        conn.close()
        raise HTTPException(400, "Payment already exists")

    cur.execute(
        """
        INSERT INTO payments
        (username, filename, status, uploaded_at, month, year)
        VALUES (?, ?, 'PENDING', ?, ?, ?)
        """,
        (username, filename, datetime.utcnow().isoformat(), month, year)
    )

    conn.commit()
    conn.close()

    return {"message": "Receipt uploaded successfully"}

# ---------------- USER PAYMENTS ----------------
@app.get("/api/user/payments/{username}")
def user_payments(username: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, filename, status, uploaded_at, month, year
        FROM payments
        WHERE username=?
        ORDER BY uploaded_at DESC
        """,
        (username,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows
# ---------------- ADMIN USERS ----------------
@app.get("/api/admin/users")
def admin_users(username: str = Query(...)):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT role FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    if not row or row[0] != "admin":
        conn.close()
        raise HTTPException(status_code=403, detail="Forbidden")

    cur.execute("SELECT username, role FROM users ORDER BY username")
    users = cur.fetchall()
    conn.close()
    return users


# ---------------- ADMIN PAYMENTS ----------------
# =======================
# ADMIN – VIEW PAYMENTS
# =======================

@app.get("/api/admin/payments")
def admin_payments(
    username: str = Query(...),
    month: str | None = None,
    year: str | None = None
):
    conn = get_db()
    cur = conn.cursor()

    # verify admin
    cur.execute("SELECT role FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    if not row or row[0] != "admin":
        conn.close()
        raise HTTPException(status_code=403, detail="Forbidden")

    query = """
        SELECT id, username, filename, status, uploaded_at, month, year, amount
        FROM payments
        WHERE 1=1
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
    payments = cur.fetchall()
    conn.close()

    return payments



# ---------------- APPROVE PAYMENT ----------------
@app.post("/api/admin/approve/{payment_id}")
def approve_payment(payment_id: int, username: str = Query(...)):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT role FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    if not row or row[0] != "admin":
        conn.close()
        raise HTTPException(status_code=403, detail="Forbidden")

    cur.execute(
        "UPDATE payments SET status='APPROVED' WHERE id=?",
        (payment_id,)
    )
    conn.commit()
    conn.close()

    return {"message": "Payment approved"}
