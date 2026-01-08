from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import sqlite3
import os
import uuid
from datetime import datetime

app = FastAPI()

DB = "hoa.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# -------------------------
# DATABASE
# -------------------------
def get_db():
    return sqlite3.connect(DB, check_same_thread=False)


# -------------------------
# USER – UPLOAD PAYMENT
# -------------------------
@app.post("/api/upload-receipt")
async def upload_receipt(
    username: str,
    month: str,
    year: str,
    file: UploadFile = File(...),
    amount: float = Query(...)
):
    conn = get_db()
    cur = conn.cursor()

    filename = f"{uuid.uuid4()}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
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

    return {"message": "Payment uploaded successfully"}


# -------------------------
# USER – PAYMENT HISTORY
# -------------------------
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

    data = cur.fetchall()
    conn.close()
    return data


# -------------------------
# ADMIN – VIEW PAYMENTS
# -------------------------
@app.get("/api/admin/payments")
def admin_payments(
    username: str = Query(...),
    month: str | None = None,
    year: str | None = None
):
    conn = get_db()
    cur = conn.cursor()

    # validate admin
    cur.execute("SELECT role FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    if not row or row[0] != "admin":
        conn.close()
        raise HTTPException(status_code=403, detail="Forbidden")

    query = """
        SELECT
            id,
            username,
            filename,
            status,
            uploaded_at,
            month,
            year,
            amount
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


# -------------------------
# ADMIN – APPROVE PAYMENT
# -------------------------
@app.post("/api/admin/payments/{pid}/approve")
def approve_payment(pid: int):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE payments SET status='APPROVED' WHERE id=?",
        (pid,)
    )

    conn.commit()
    conn.close()
    return {"message": "Payment approved"}


# -------------------------
# ADMIN – REJECT PAYMENT
# -------------------------
@app.post("/api/admin/payments/{pid}/reject")
def reject_payment(pid: int, reason: dict):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE payments SET status='REJECTED' WHERE id=?",
        (pid,)
    )

    conn.commit()
    conn.close()
    return {"message": "Payment rejected", "reason": reason.get("reason")}


# -------------------------
# ADMIN – MONTHLY REPORT
# -------------------------
@app.get("/api/admin/reports/monthly")
def monthly_report(month: str, year: str):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM payments
        WHERE status='APPROVED'
        AND month=? AND year=?
    """, (month, year))

    total = cur.fetchone()[0]
    conn.close()

    return {"total": total}
