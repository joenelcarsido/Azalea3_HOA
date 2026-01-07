from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime
import sqlite3
import os
import uuid

from database import init_db

# ================= CONFIG =================
DB = "hoa.db"
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

os.makedirs(UPLOAD_DIR, exist_ok=True)

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

# ================= DB HELPERS =================
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

# ================= ADMIN BOOTSTRAP =================
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

# ================= APP =================
app = FastAPI()

init_db()
ensure_admin()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ================= PAGE ROUTES =================
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

@app.get("/admin")
def admin_page():
    return FileResponse("static/admin.html")

# ================= MODELS =================
class LoginData(BaseModel):
    username: str
    password: str

class RegisterData(BaseModel):
    username: str
    password: str

class ChangePasswordData(BaseModel):
    old_password: str
    new_password: str

# ================= AUTH =================
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

# ================= CHANGE PASSWORD =================
@app.post("/api/change-password")
def change_password(username: str, data: ChangePasswordData):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT password FROM users WHERE username=?", (username,))
    row = cur.fetchone()

    if not row or not verify_password(data.old_password, row[0]):
        conn.close()
        raise HTTPException(status_code=400, detail="Old password incorrect")

    cur.execute(
        "UPDATE users SET password=? WHERE username=?",
        (hash_password(data.new_password), username)
    )

    conn.commit()
    conn.close()

    return {"message": "Password updated successfully"}

# ================= RECEIPT UPLOAD =================
@app.post("/api/upload-receipt")
async def upload_receipt(username: str, file: UploadFile = File(...)):

    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".pdf")):
        raise HTTPException(status_code=400, detail="Invalid file type")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    filename = f"{uuid.uuid4()}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO payments (username, filename, status, uploaded_at)
        VALUES (?, ?, 'PENDING', ?)
        """,
        (username, filename, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    return {"message": "Receipt uploaded. Awaiting admin approval."}

# ================= USER STATUS =================
@app.get("/api/payment-status/{username}")
def payment_status(username: str):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT status, uploaded_at
        FROM payments
        WHERE username=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (username,)
    )

    row = cur.fetchone()
    conn.close()

    if not row:
        return {"status": "NO PAYMENT"}

    return {"status": row[0], "uploaded_at": row[1]}

# ================= ADMIN APIs =================
@app.get("/api/admin/users")
def admin_users(username: str):
    if not is_admin(username):
        raise HTTPException(status_code=403)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username, role FROM users ORDER BY username")
    users = cur.fetchall()
    conn.close()

    return users

@app.get("/api/admin/payments")
def admin_payments(username: str):
    if not is_admin(username):
        raise HTTPException(status_code=403)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM payments ORDER BY id DESC")
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
