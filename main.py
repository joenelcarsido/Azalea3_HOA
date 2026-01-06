from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

# Serve static files (login.html, dashboard.html, css, js, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---- Login API ----
class LoginData(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def login(data: LoginData):
    # TEMP credentials (replace with database later)
    if data.username == "admin" and data.password == "admin":
        return {"message": "Login successful"}

    raise HTTPException(status_code=401, detail="Invalid username or password")

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Azalea HOA API is running"}
