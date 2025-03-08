from flask import Flask, render_template, redirect, request, session, jsonify
import requests
import aiosqlite

app = Flask(__name__)
app.secret_key = "super_secret_key"
DB_PATH = "/Users/borisdekic/PycharmProjects/Bot/server_settings.db"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/dashboard")  # 🔹 Route für das Admin-Dashboard
async def dashboard():
    """Lädt die Admin-Dashboard-Seite mit den aktuellen Einstellungen."""
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT welcome_message, log_channel_id, capslock_filter FROM settings WHERE guild_id = 1")
        settings = await row.fetchone()
    return render_template("dashboard.html", settings=settings)

@app.route("/settings", methods=["GET"])
async def get_settings():
    """API-Route, die die aktuellen Einstellungen zurückgibt"""
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT welcome_message, log_channel_id, capslock_filter FROM settings WHERE guild_id = 1")
        settings = await row.fetchone()
    return jsonify(settings)

@app.route("/update_settings", methods=["POST"])
async def update_settings():
    """Admin kann Einstellungen über das Web ändern"""
    data = request.json
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE settings 
            SET welcome_message = ?, log_channel_id = ?, capslock_filter = ? 
            WHERE guild_id = 1
        """, (data["welcome_message"], data["log_channel_id"], data["capslock_filter"]))
        await db.commit()
    return jsonify({"message": "Einstellungen aktualisiert!"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
