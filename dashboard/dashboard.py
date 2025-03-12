import os
import requests
from flask import Flask, render_template, redirect, url_for, session
from flask_discord import DiscordOAuth2Session
from dotenv import load_dotenv

# 🔄 Unsichere Transport-Variante für OAuth2 erlauben (nur lokal!)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")
app.config["DISCORD_BOT_TOKEN"] = os.getenv("TOKEN")

discord_oauth = DiscordOAuth2Session(app)

@app.route("/")
def home():
    """🏠 Startseite mit Bot-Statistiken"""
    try:
        bot_status = requests.get("http://127.0.0.1:5001/status").json()  # API-Call zum Bot
    except requests.exceptions.ConnectionError:
        bot_status = {"bot_name": "Unbekannt", "status": "Offline", "server_count": 0, "user_count": 0}

    return render_template("index.html", bot_status=bot_status)

@app.route("/login")
def login():
    """🔐 Startet die Discord-Authentifizierung"""
    return discord_oauth.create_session()

@app.route("/logout")
def logout():
    """🚪 Beendet die Discord-Session"""
    discord_oauth.revoke()
    session.clear()
    return redirect(url_for("home"))

@app.route("/callback")
def callback():
    """🔄 Verarbeitet den Discord OAuth2-Callback nach der Anmeldung."""
    discord_oauth.callback()  # Discord-Authentifizierung abschließen
    return redirect(url_for("dashboard"))  # Weiterleitung ins Dashboard




@app.route("/dashboard")
def dashboard():
    """📊 Dashboard-Seite"""
    if not discord_oauth.authorized:
        return redirect(url_for("login"))

    user = discord_oauth.fetch_user()
    guilds = discord_oauth.fetch_guilds()

    # 📌 API-Call zum Bot-Status (Fehlende Zeile!)
    try:
        bot_status = requests.get("http://127.0.0.1:5001/status").json()
    except requests.exceptions.ConnectionError:
        bot_status = {"bot_name": "Unbekannt", "status": "Offline", "server_count": 0, "user_count": 0}

    # **📌 Nur Server anzeigen, auf denen der User Admin ist (Bitwise-Berechtigungen prüfen)**
    admin_guilds = [guild for guild in guilds if guild.permissions.administrator]


    return render_template("dashboard.html", user=user, guilds=admin_guilds, bot_status=bot_status)  # ✅ `bot_status` übergeben!

if __name__ == "__main__":
    app.run(debug=True, port=5000)

