
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime
import sqlite3
import os
import uuid

# ---------------- APP SETUP ----------------
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB = "hoa.db"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------- HELPERS ----------------
def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)

def get_db():
    return sqlite3.connect(DB)

# ---------------- ROOT ----------------
@app.get("/")
def login_page():
    return FileResponse("static/login.html")

# ---------------- MODELS ----------------
class LoginData(BaseModel):
    username: str
    password: str

class RegisterData(BaseModel):
    username: str
    password: str

class ChangePasswordData(BaseModel):
    username: str
    old_password: str
    new_password: str

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

@app.post("/api/change-password")
def change_password(data: ChangePasswordData):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT password FROM users WHERE username=?", (data.username,))
    user = cur.fetchone()

    if not user or not verify_password(data.old_password, user[0]):
        raise HTTPException(status_code=401, detail="Old password incorrect")

    cur.execute(
        "UPDATE users SET password=? WHERE username=?",
        (hash_password(data.new_password), data.username)
    )
    conn.commit()
    conn.close()

    return {"message": "Password changed successfully"}

# ---------------- RECEIPT UPLOAD ----------------
@app.post("/api/upload-receipt")
async def upload_receipt(username: str, file: UploadFile = File(...)):

    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".pdf")):
        raise HTTPException(status_code=400, detail="Invalid file type")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    filename = f"{uuid.uuid4()}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO payments (username, filename, status, uploaded_at)
        VALUES (?, ?, 'PENDING', ?)
    """, (username, filename, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return {"message": "Receipt uploaded. Awaiting admin approval."}

# ---------------- ADMIN ----------------
@app.get("/api/admin/payments")
def admin_payments():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM payments")
    rows = cur.fetchall()
    conn.close()
    return rows

@app.post("/api/admin/approve/{payment_id}")
def approve_payment(payment_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE payments SET status='APPROVED' WHERE id=?", (payment_id,))
    conn.commit()
    conn.close()
    return {"message": "Payment approved"}

# ---------------- USER STATUS ----------------
@app.get("/api/payment-status/{username}")
def payment_status(username: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT status, uploaded_at
        FROM payments
        WHERE username=?
        ORDER BY id DESC
        LIMIT 1
    """, (username,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {"status": "NO PAYMENT"}
    return {"status": row[0], "uploaded_at": row[1]}
