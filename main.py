import os
import discord





intents = discord.Intents.default()
intents.members = True


status = discord.Status.dnd
activity = discord.Activity(type=discord.ActivityType.playing, name="In Entwicklung")

bot = discord.Bot(
    intents=intents,
    debug_guilds=[523109595292368907],
    status=status,
    activity=activity
)

@bot.event
async def on_ready():
    print(f"{bot.user} ist Online")

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
