import discord
from discord.commands import slash_command
from discord.ext import commands

from cooldown_handler import check_cooldown


class Greet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="greet", description="Begrüßt den User")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def greet(self, ctx):
        await ctx.respond(f"Hallo, {ctx.author.mention}")




def setup(bot):
    bot.add_cog(Greet(bot))
