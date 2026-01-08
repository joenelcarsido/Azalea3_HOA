from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import sqlite3, os

app = FastAPI()

DB = "hoa.db"
STATIC_DIR = "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------- ROOT ----------------
@app.get("/")
def root():
    return RedirectResponse("/static/login.html")


# ---------------- DB ----------------
def get_db():
    return sqlite3.connect(DB, check_same_thread=False)


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # USERS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # DEFAULT ADMIN
    cur.execute("SELECT * FROM users WHERE username='admin'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", "admin123", "admin")
        )

    conn.commit()
    conn.close()


init_db()


# ---------------- MODELS ----------------
class Auth(BaseModel):
    username: str
    password: str


# ---------------- REGISTER ----------------
@app.post("/api/register")
def register(data: Auth):
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (data.username, data.password, "user")
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already exists")
    finally:
        conn.close()

    return {"message": "Registered successfully"}


# ---------------- LOGIN ----------------
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
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return {
        "username": data.username,
        "role": row[0]
    }
