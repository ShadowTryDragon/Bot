import discord
from discord.ext import commands


class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_application_command_error(self, ctx, error):
        """Fängt Fehler bei Slash-Commands ab und sendet eine Antwort."""

        if isinstance(error, commands.CommandOnCooldown):
            remaining_time = round(error.retry_after, 2)  # Zeit auf 2 Dezimalstellen runden
            minutes, seconds = divmod(int(remaining_time), 60)  # In Minuten & Sekunden umwandeln

            embed = discord.Embed(
                title="⏳ Cooldown aktiv!",
                description=f"Bitte warte `{minutes}m {seconds}s`, bevor du `{ctx.command.name}` erneut nutzt.",
                color=discord.Color.orange()
            )

            await ctx.respond(embed=embed, ephemeral=True)  # Nachricht nur für den User sichtbar
            return  # ✅ Fehler als "behandelt" markieren (kein Log in der Konsole)

        # Falls es ein anderer Fehler ist, logge ihn in der Konsole
        print(f"⚠ Ein Fehler ist aufgetreten: {error}")


def setup(bot):
    bot.add_cog(ErrorHandler(bot))
