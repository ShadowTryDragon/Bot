
import os
import discord
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.members = True

status = discord.Status.dnd
activity = discord.Activity(type=discord.ActivityType.playing, name="Supporter")

bot = discord.Bot(
    intents=intents,
    debug_guilds=[523109595292368907],
    status = status,
    activity = activity
)

@bot.event
async def on_ready():
    print(f"{bot.user} ist Online")



if __name__ == "__main__":
    for filename in os.listdir("cogs"):
        if filename.endswith(".py"):
            bot.load_extension(f"cogs.{filename[:-3]}")





load_dotenv()
bot.run("MTM0NDM0MTU0NDIzMjAzMDI0OQ.GlIerP.RWgX6yiSkdfVVihJUtMGhh9349yXpTUh8l9ydY")