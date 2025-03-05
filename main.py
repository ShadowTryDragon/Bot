import os
import discord





intents = discord.Intents.default()
intents.members = True
intents.guilds = True  # Benötigt für Server-Informationen
intents.messages = True  # Notwendig für Nachrichten-Tracking
intents.message_content = True  # Falls der Bot Nachrichten analysieren soll (z. B. für Blacklist-Wörter)
intents.reactions = True  # Ermöglicht das Tracking von Reaktionen


status = discord.Status.dnd
activity = discord.Activity(type=discord.ActivityType.playing, name="In Entwicklung")

bot = discord.Bot(
    intents=intents,
    status=status,
    activity=activity
)
bot.synced = False  # Initialisiere die Variable global

@bot.event
async def on_ready():
    await bot.sync_commands()  # Synchronisiert alle Slash-Commands
    print(f"✅ {bot.user} ist online! Alle Slash-Commands wurden synchronisiert.")




if __name__ == "__main__":
    for filename in os.listdir("cogs"):
        if filename.endswith(".py"):
            bot.load_extension(f"cogs.{filename[:-3]}")


import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--token", required=True, help="Discord Bot Token")
args = parser.parse_args()

TOKEN = args.token
bot.run(TOKEN)
