import discord
from discord.ext import commands
from discord.commands import slash_command

class Greet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        @slash_command()
        async def greet(
                self,
                ctx,
        ):
         await ctx.respond(f"Hallo, {ctx.author.mention}")

        @commands.Cog.listener()
        async def on_member_join(self, member):
            embed = discord.Embed(
                title="Willkommen",
                description=f"Hey, {member.mention}",
                color=discord.Color.green()

            )

            channel = await self.bot.fetch_chennels(1124488156658548846)
            await channel.send(embed=embed)

def setup(bot):
    bot.add_cog(Greet(bot))

