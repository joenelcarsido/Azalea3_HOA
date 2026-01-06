from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI()

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---- Login Page ----
@app.get("/")
def login_page():
    return FileResponse("static/login.html")


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
