import discord
from discord.commands import slash_command
from discord.ext import commands


class Greet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="greet", description="Begrüßt den User")
    async def greet(self, ctx):
        await ctx.respond(f"Hallo, {ctx.author.mention}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = discord.Embed(
            title="Willkommen",
            description=f"Hey, {member.mention}! Schön, dass du da bist! 🎉",
            color=discord.Color.green()
        )

        # 🛠️ Fehler behoben: `fetch_channel` statt `fetch_chennels`
        channel = await self.bot.fetch_channel(1124488156658548846)

        # Prüfen, ob der Channel existiert
        if channel:
            await channel.send(embed=embed)
        else:
            print("❌ Fehler: Channel nicht gefunden!")


def setup(bot):
    bot.add_cog(Greet(bot))
