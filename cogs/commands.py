
from discord.ext import commands
from cooldown_handler import check_cooldown
from discord.commands import slash_command, Option
import discord


class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command()
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    @discord.default_permissions(administrator=True)
    async def activity(
            self, ctx,
            typ: Option(str, choices=["game", "stream"]),
            name: Option(str)
    ):
        if typ == "game":
            act = discord.Game(name=name)
        else:
            act = discord.Streaming(
                name=name,
                url="https://youtu.be/y6120QOlsfU?si=_Q-nVoz4oIbxPapN"
            )

        await self.bot.change_presence(activity=act, status=discord.Status.online)
        await ctx.respond("Status wurde geändert!")


def setup(bot):
    bot.add_cog(Commands(bot))
