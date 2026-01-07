from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime
import sqlite3
import os
import uuid

from database import init_db

# ---------------- CONFIG ----------------
DB = "hoa.db"
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

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

# ---------------- ADMIN INIT ----------------
def ensure_admin():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
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

@app.get("/dashboard")
def dashboard_page():
    return FileResponse("static/dashboard.html")

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
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (data.username, hash_password(data.password), "homeowner")
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already exists")
    finally:
        conn.close()

    return {"message": "Registration successful"}

@app.post("/api/login")
def login(data: LoginData):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT password, role FROM users WHERE username=?",
        (data.username,)
    )
    user = cur.fetchone()
    conn.close()

    if not user or not verify_password(data.password, user[0]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"username": data.username, "role": user[1]}

# ---------------- USER PAYMENTS ----------------
@app.post("/api/upload-receipt")
async def upload_receipt(
    username: str = Form(...),
    month: str = Form(...),
    year: int = Form(...),
    file: UploadFile = File(...)
):
    # Validate file type
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".pdf")):
        raise HTTPException(status_code=400, detail="Invalid file type")

    contents = await file.read()

    # Validate file size
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    # Save file
    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(contents)

    conn = get_db()
    cur = conn.cursor()

    # Prevent duplicate payment
    cur.execute(
        "SELECT 1 FROM payments WHERE username=? AND month=? AND year=?",
        (username, month, year)
    )
    if cur.fetchone():
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Payment for this month already exists"
        )

    # Insert payment
    cur.execute(
        """
        INSERT INTO payments
        (username, filename, status, uploaded_at, month, year)
        VALUES (?, ?, 'PENDING', ?, ?, ?)
        """,
        (
            username,
            filename,
            datetime.now().isoformat(),
            month,
            year
        )
    )

    conn.commit()
    conn.close()

    return {"message": "Payment submitted for approval"}

@app.get("/api/user/payments/{username}")
def user_payments(username: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, filename, status, uploaded_at, month, year
        FROM payments
        WHERE username=?
        ORDER BY year DESC, uploaded_at DESC
        """,
        (username,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

# ---------------- ADMIN ----------------
@app.get("/api/admin/users")
def admin_users(username: str):
    if not is_admin(username):
        raise HTTPException(status_code=403)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username, role FROM users ORDER BY username")
    rows = cur.fetchall()
    conn.close()
    return rows

@app.get("/api/admin/payments")
def admin_payments(username: str):
    if not is_admin(username):
        raise HTTPException(status_code=403)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, username, filename, status, uploaded_at, month, year
        FROM payments
        ORDER BY uploaded_at DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows

@app.post("/api/admin/approve/{payment_id}")
def approve_payment(payment_id: int, username: str):
    if not is_admin(username):
        raise HTTPException(status_code=403)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE payments SET status='APPROVED' WHERE id=?",
        (payment_id,)
    )
    conn.commit()
    conn.close()
    return {"message": "Payment approved"}
