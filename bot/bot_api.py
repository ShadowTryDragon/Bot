from flask import Flask, jsonify
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ✅ Discord Bot initialisieren
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@app.route("/status")
def bot_status():
    """📡 API-Route für den Bot-Status"""
    return jsonify({
        "bot_name": bot.user.name if bot.user else "Offline",
        "status": "Online" if bot.is_ready() else "Offline",
        "server_count": len(bot.guilds) if bot.user else 0,
        "user_count": sum(g.member_count for g in bot.guilds) if bot.user else 0
    })

if __name__ == "__main__":
    bot.loop.create_task(app.run(host="127.0.0.1", port=5001))  # API-Server starten
    bot.run(os.getenv("/Users/borisdekic/PycharmProjects/Bot/.env"))
    TOKEN = os.getenv("TOKEN")
