from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>HOA App is running ✅</h1><p>This is the login page placeholder.</p>"

if __name__ == "__main__":
    app.run()
