import aiosqlite
import discord
from discord.ext import commands
from discord.commands import slash_command, Option
import asyncio
import re
import sqlite3


DATABASE = "server_settings.db"  # Name der SQLite-Datenbank


class ServerSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.create_db())  # Erstellt die DB beim Start

    async def create_db(self):
        """Erstellt die Datenbank und Tabellen, falls sie nicht existieren."""
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    guild_id INTEGER PRIMARY KEY,
                    guild_name TEXT,
                    welcome_message TEXT,
                    log_channel_id INTEGER,
                    capslock_filter BOOLEAN DEFAULT FALSE,
                    link_filter BOOLEAN DEFAULT FALSE,
                    mention_filter BOOLEAN DEFAULT FALSE
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS blacklisted_words (
                    guild_id INTEGER,
                    word TEXT,
                    PRIMARY KEY (guild_id, word)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cooldowns (
                    guild_id INTEGER,
                    command TEXT,
                    seconds INTEGER,
                    PRIMARY KEY (guild_id, command)
                )
            """)
            await db.commit()
            print("✅ Datenbank wurde erfolgreich erstellt!")

    async def store_servers(self):
        """Speichert alle Server in der `settings`-Tabelle."""
        await self.bot.wait_until_ready()  # Wartet, bis der Bot vollständig gestartet ist
        async with aiosqlite.connect("server_settings.db") as db:
            for guild in self.bot.guilds:
                await db.execute("""
                    INSERT INTO settings (guild_id, guild_name)
                    VALUES (?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET guild_name = excluded.guild_name
                """, (guild.id, guild.name))

            await db.commit()
        print(f"✅ {len(self.bot.guilds)} Server wurden in `settings` gespeichert!")

    async def get_setting(self, guild_id, setting):
        """Holt eine bestimmte Einstellung aus der Datenbank."""
        async with aiosqlite.connect("server_settings.db") as db:
            async with db.execute(f"SELECT {setting} FROM settings WHERE guild_id = ?", (guild_id,)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else None

    async def update_setting(self, guild_id, setting, value):
        """Aktualisiert oder setzt eine Einstellung für einen Server."""
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute(f"""
                INSERT INTO settings (guild_id, {setting}) 
                VALUES (?, ?) ON CONFLICT(guild_id) 
                DO UPDATE SET {setting} = excluded.{setting}
            """, (guild_id, value))
            await db.commit()

    ### --- SERVER-SETTINGS BEFEHLE --- ###

    @slash_command(name="set_welcome", description="Setzt die Begrüßungsnachricht für den Server (Admin only).")
    @commands.has_permissions(administrator=True)
    async def set_welcome(self, ctx, message: Option(str, "Willkommensnachricht eingeben")):
        await self.update_setting(ctx.guild.id, "welcome_message", message)
        await ctx.respond(f"✅ Begrüßungsnachricht wurde auf:\n\n```{message}``` gesetzt!")

    @slash_command(name="set_log_channel", description="Setzt den Log-Kanal für Moderationsereignisse (Admin only).")
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx, channel: Option(discord.TextChannel, "Wähle den Log-Kanal")):
        await self.update_setting(ctx.guild.id, "log_channel_id", channel.id)
        await ctx.respond(f"✅ Log-Kanal wurde auf {channel.mention} gesetzt!")

    ### --- BLACKLIST WÖRTER --- ###

    @slash_command(name="add_blacklist", description="Fügt ein Wort zur Blacklist hinzu (Admin only).")
    @commands.has_permissions(administrator=True)
    async def add_blacklist(self, ctx, word: Option(str, "Gib das Wort ein")):
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("INSERT INTO blacklisted_words (guild_id, word) VALUES (?, ?)", (ctx.guild.id, word.lower()))
            await db.commit()
        await ctx.respond(f"✅ Das Wort `{word}` wurde zur Blacklist hinzugefügt!")

    @slash_command(name="remove_blacklist", description="Entfernt ein Wort von der Blacklist (Admin only).")
    @commands.has_permissions(administrator=True)
    async def remove_blacklist(self, ctx, word: Option(str, "Gib das Wort ein")):
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("DELETE FROM blacklisted_words WHERE guild_id = ? AND word = ?", (ctx.guild.id, word.lower()))
            await db.commit()
        await ctx.respond(f"✅ Das Wort `{word}` wurde von der Blacklist entfernt!")

    ### --- AUTO-MODERATION --- ###

    @slash_command(name="set_automod", description="Aktiviert oder deaktiviert automatische Moderation (Admin only).")
    @commands.has_permissions(administrator=True)
    async def set_automod(self, ctx, capslock: Option(bool, "Capslock-Spam blockieren?", default=False),
                          links: Option(bool, "Links blockieren?", default=False),
                          mentions: Option(bool, "Massen-Pings blockieren?", default=False)):
        await self.update_setting(ctx.guild.id, "capslock_filter", capslock)
        await self.update_setting(ctx.guild.id, "link_filter", links)
        await self.update_setting(ctx.guild.id, "mention_filter", mentions)
        await ctx.respond("✅ Auto-Moderationseinstellungen wurden aktualisiert!")

    ### --- COOLDOWNS --- ###

    @slash_command(name="set_cooldown", description="Setzt ein Cooldown für einen Befehl (Admin only).")
    @commands.has_permissions(administrator=True)
    async def set_cooldown(self, ctx, command: Option(str, "Befehl eingeben"), seconds: Option(int, "Cooldown in Sekunden")):
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("""
                INSERT INTO cooldowns (guild_id, command, seconds) 
                VALUES (?, ?, ?) ON CONFLICT(guild_id, command) 
                DO UPDATE SET seconds = excluded.seconds
            """, (ctx.guild.id, command, seconds))
            await db.commit()
        await ctx.respond(f"✅ Cooldown für `{command}` wurde auf `{seconds}` Sekunden gesetzt!")

    ### --- EVENT LISTENERS --- ###

    @commands.Cog.listener()
    async def on_ready(self):
        """Erstellt die Datenbank und speichert die Server-Einstellungen."""
        print("🔄 Bot ist bereit! Initialisiere Datenbank...")
        await self.store_servers()  # ✅ Speichert Server in `settings`

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Speichert einen neuen Server in der Datenbank, wenn der Bot beitritt."""
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("""
                INSERT INTO settings (guild_id, guild_name)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET guild_name = excluded.guild_name
            """, (guild.id, guild.name))
        conn.commit()
        conn.close()
        print(f"✅ Der Server {guild.name} wurde in der Datenbank gespeichert.")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Löscht den Server aus der Datenbank, wenn der Bot den Server verlässt."""
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM settings WHERE guild_id = ?", (guild.id,))
        conn.commit()
        conn.close()
        print(f"❌ Der Server {guild.name} wurde aus der Datenbank entfernt.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        await self.bot.process_commands(message)  # ✅ WICHTIG: Damit Befehle weiter funktionieren

        # Capslock-Filter abrufen
        capslock_enabled = await self.is_capslock_enabled(message.guild.id)

        # Capslock prüfen und Nachricht löschen
        if capslock_enabled and is_capslock_message(message.content):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, bitte nicht schreien! 🔇", delete_after=5)
            return  # WICHTIG: Verhindert doppelte Verarbeitung

        # Prüft Blacklist-Wörter
        async with aiosqlite.connect("server_settings.db") as db:
            async with db.execute("SELECT word FROM blacklisted_words WHERE guild_id = ?",
                                  (message.guild.id,)) as cursor:
                blacklist = [row[0] for row in await cursor.fetchall()]

        filtered_message = "".join(c if c.isalnum() or c.isspace() else " " for c in message.content).lower()

        if any(word in filtered_message.split() for word in blacklist):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, dieses Wort ist auf der Blacklist!", delete_after=5)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Sendet eine Begrüßungsnachricht, wenn ein neuer User joint."""
        welcome_message = await self.get_setting(member.guild.id, "welcome_message")
        if welcome_message:
            await member.guild.system_channel.send(welcome_message.replace("{user}", member.mention))

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Loggt gelöschte Nachrichten."""
        log_channel_id = await self.get_setting(message.guild.id, "log_channel_id")
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(title="🗑 Nachricht gelöscht", description=message.content, color=discord.Color.red())
                embed.set_footer(text=f"Von {message.author}")
                await log_channel.send(embed=embed)

def setup(bot):
    bot.add_cog(ServerSettings(bot))
