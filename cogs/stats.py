import discord
from discord.ext import commands
from discord.commands import slash_command
import platform
import psutil
import time


class ServerStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="serverstats", description="Zeigt detaillierte Informationen über diesen Server.")
    async def serverstats(self, ctx):
        """Zeigt detaillierte Statistiken über den aktuellen Server in einem Embed."""

        guild = ctx.guild  # Der aktuelle Server

        # 🔹 Basis-Infos
        server_name = guild.name
        server_id = guild.id
        owner = guild.owner  # Server-Besitzer
        created_at = guild.created_at.strftime("%d.%m.%Y %H:%M:%S")

        # 🔹 Mitgliederstatistik
        total_members = guild.member_count
        human_members = sum(1 for member in guild.members if not member.bot)
        bot_members = total_members - human_members

        # 🔹 Kanal-Statistiken
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)

        # 🔹 Rollen & Boosts
        role_count = len(guild.roles)
        boost_level = guild.premium_tier  # Boost-Level (1-3)
        boost_count = guild.premium_subscription_count  # Anzahl der Boosts

        # 🔹 Server-Bilder
        server_icon = guild.icon.url if guild.icon else None
        banner = guild.banner.url if guild.banner else None

        # 📌 Embed erstellen
        embed = discord.Embed(title=f"📊 Server-Statistiken: {server_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=server_icon)  # Server-Icon als Thumbnail

        # 🔹 Server-Basisinformationen
        embed.add_field(name="🆔 Server ID", value=f"`{server_id}`", inline=True)
        embed.add_field(name="👑 Besitzer", value=f"{owner.mention}" if owner else "Unbekannt", inline=True)
        embed.add_field(name="📅 Erstellt am", value=f"`{created_at}`", inline=False)

        # 🔹 Mitglieder-Statistiken
        embed.add_field(name="👥 Mitglieder", value=f"**{total_members}** gesamt", inline=True)
        embed.add_field(name="🧑‍🤝‍🧑 Menschen", value=f"**{human_members}**", inline=True)
        embed.add_field(name="🤖 Bots", value=f"**{bot_members}**", inline=True)

        # 🔹 Kanal-Statistiken
        embed.add_field(name="💬 Textkanäle", value=f"**{text_channels}**", inline=True)
        embed.add_field(name="🔊 Sprachkanäle", value=f"**{voice_channels}**", inline=True)
        embed.add_field(name="📂 Kategorien", value=f"**{categories}**", inline=True)

        # 🔹 Rollen & Boosts
        embed.add_field(name="🎭 Rollen", value=f"**{role_count}**", inline=True)
        embed.add_field(name="💎 Boost-Level", value=f"**{boost_level}**", inline=True)
        embed.add_field(name="🚀 Server Boosts", value=f"**{boost_count}**", inline=True)

        # 🔹 Falls der Server ein Banner hat, füge es als Bild hinzu
        if banner:
            embed.set_image(url=banner)

        # ✅ Antwort senden
        await ctx.respond(embed=embed)


# 🔹 Speichert den Startzeitpunkt des Bots für die Uptime-Berechnung
start_time = time.time()


class BotStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="botstats", description="Zeigt Statistiken über den Bot.")
    async def botstats(self, ctx):
        """Zeigt detaillierte Statistiken über den Bot in einem Embed."""

        bot_user = self.bot.user  # Bot-User
        bot_id = bot_user.id
        bot_name = bot_user.name
        created_at = bot_user.created_at.strftime("%d.%m.%Y %H:%M:%S")

        # 🔹 Besitzer-Info (immer User mit ID 265547462062768129)
        bot_owner = await self.bot.fetch_user(265547462062768129)

        # 🔹 Server- & User-Statistiken
        total_servers = len(self.bot.guilds)
        total_users = sum(guild.member_count for guild in self.bot.guilds)

        # 🔹 Uptime berechnen
        uptime_seconds = int(time.time() - start_time)
        uptime_str = time.strftime("%H:%M:%S", time.gmtime(uptime_seconds))

        # 🔹 Ping (Latenz)
        latency = round(self.bot.latency * 1000, 2)

        # 🔹 Anzahl der Slash-Commands
        total_commands = len(self.bot.application_commands)

        # 📌 Embed erstellen
        embed = discord.Embed(title=f"🤖 Bot-Statistiken: {bot_name}", color=discord.Color.blurple())
        embed.set_thumbnail(url=bot_user.avatar.url if bot_user.avatar else None)

        # 🔹 Basis-Infos
        embed.add_field(name="🆔 Bot ID", value=f"`{bot_id}`", inline=True)
        embed.add_field(name="👑 Besitzer", value=f"{bot_owner.mention}", inline=True)
        embed.add_field(name="📅 Erstellt am", value=f"`{created_at}`", inline=False)

        # 🔹 Server- & Nutzer-Statistiken
        embed.add_field(name="🌍 Server", value=f"**{total_servers}**", inline=True)
        embed.add_field(name="👥 Nutzer", value=f"**{total_users}**", inline=True)

        # 🔹 Leistung & Uptime
        embed.add_field(name="⏳ Uptime", value=f"`{uptime_str}`", inline=True)
        embed.add_field(name="📡 Ping", value=f"`{latency}ms`", inline=True)
        embed.add_field(name="🔢 Befehle", value=f"`{total_commands}`", inline=True)

        # ✅ Antwort senden
        await ctx.respond(embed=embed)


# 🔹 Cog Setup-Funktion für Pycord
def setup(bot):
    bot.add_cog(ServerStats(bot))
    bot.add_cog(BotStats(bot))
