import discord
from discord.ext import commands
from discord.commands import slash_command, Option
from datetime import timedelta


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(description="Kicke einen User")
    @discord.default_permissions(kick_members=True)
    async def kick(
            self,
            ctx,
            member: Option(discord.Member,
                           "Wähle einen Member"
                           )):
        try:
            await member.kick()
        except discord.Forbidden as e:
            print(e)
            await ctx.respond("Ich kann diesen Befehl nicht Ausführen")
            return
        await ctx.respond(f"{member.mention} wurde gekickt.")

    @slash_command(description="Banne einen User")
    @discord.default_permissions(ban_members=True)
    async def ban(
            self,
            ctx,
            member: Option(discord.Member,
                           "Wähle einen Member"
                           )):
        try:
            await member.ban()
        except discord.Forbidden as e:
            print(e)
            await ctx.respond("Ich kann diesen Befehl nicht Ausführen")
            return
        await ctx.respond(f"{member.mention} wurde gebannt.")


    @slash_command(name="timeout", description="Setzt einen Benutzer in Timeout")
    async def timeout(
            self,
            ctx,
            member: Option(discord.Member, "Wähle den Benutzer aus"),
            duration: Option(int, "Timeout-Dauer in Sekunden"),
            reason: Option(str, "Grund für den Timeout", default="Kein Grund angegeben")
    ):
        if not ctx.author.guild_permissions.moderate_members:
            return await ctx.respond("Du hast keine Berechtigung, um Timeouts zu setzen.", ephemeral=True)

        if member == ctx.author:
            return await ctx.respond("Du kannst dich nicht selbst timeouten!", ephemeral=True)

        if member.top_role >= ctx.author.top_role:
            return await ctx.respond("Du kannst keinen Benutzer mit höherer oder gleicher Rolle timeouten!",
                                     ephemeral=True)

        try:
            await member.timeout(discord.utils.utcnow() + timedelta(seconds=duration), reason=reason)
            await ctx.respond(f"{member.mention} wurde für {duration} Sekunden getimeoutet. Grund: {reason}")

            embed = discord.Embed(title="Timeout", color=discord.Color.red())
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            embed.add_field(name="Benutzer", value=member.mention, inline=True)
            embed.add_field(name="Dauer", value=f"{duration} Sekunden", inline=True)
            embed.add_field(name="Grund", value=reason, inline=False)
            embed.set_footer(text=f"Timeout durch {ctx.author}", icon_url=ctx.author.avatar.url)

            channel = await self.bot.fetch_channel(1120502293838696610)  # Log-Kanal ID anpassen
            await channel.send(embed=embed)

        except discord.Forbidden:
            await ctx.respond("Ich habe nicht die erforderlichen Berechtigungen, um diesen Benutzer zu timeouten.",
                              ephemeral=True)
        except discord.HTTPException:
            await ctx.respond("Fehler beim Versuch, den Benutzer zu timeouten.", ephemeral=True)




def setup(bot):
    bot.add_cog(Admin(bot))
