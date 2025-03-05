import asyncio

import re
from datetime import timedelta

import aiosqlite
import discord
from discord.ext import commands
from discord.commands import slash_command, Option

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
                    welcome_channel_id INTEGER,  -- Neu: Speichert den Willkommens-Channel
                    default_roles TEXT,  -- Neu: Speichert Rollen als kommagetrennte Liste
                    leave_message TEXT,  -- Neu: Speichert die Abschieds-Nachricht
                    leave_channel_id INTEGER,  -- Neu: Speichert den Abschieds-Channel
                    log_channel_id INTEGER,
                    warn_decay_hours INTEGER,
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

            await db.execute("""
                        CREATE TABLE IF NOT EXISTS allowed_domains (
                            guild_id INTEGER,
                            domain TEXT COLLATE NOCASE,
                            PRIMARY KEY (guild_id, domain)
                        )
                    """)
            await db.execute("""
                        CREATE TABLE IF NOT EXISTS cooldown_tracker (
                            user_id INTEGER,
                            command TEXT,
                            last_used REAL,
                            PRIMARY KEY (user_id, command)
                        )
                    """)
            await db.execute("""
                        CREATE TABLE IF NOT EXISTS warns (
                            guild_id INTEGER,
                            guild_name TEXT,
                            user_id INTEGER,
                            username TEXT,
                            warn_count INTEGER DEFAULT 0,
                            last_warned REAL DEFAULT 0,
                            PRIMARY KEY (guild_id, user_id)
                        )
                    """)
            await db.execute("""
                        CREATE TABLE IF NOT EXISTS settings (
                            guild_id INTEGER PRIMARY KEY,
                            guild_name TEXT,
                            warn_decay_hours INTEGER DEFAULT 24  -- Standard: Alle 24h wird eine Warnung gelöscht
                        )
                    """)

            await db.commit()
            print("✅ Datenbank wurde erfolgreich erstellt!")

    async def remove_expired_warns(self):
        """Löscht Verwarnungen, die älter sind als die eingestellte Zeit."""
        while True:
            await asyncio.sleep(3600)  # ⏳ Warten (1 Stunde)

            async with aiosqlite.connect("server_settings.db") as db:
                async with db.execute("SELECT guild_id, warn_decay_hours FROM settings") as cursor:
                    decay_times = await cursor.fetchall()

                for guild_id, hours in decay_times:
                    await db.execute("""
                        UPDATE warns 
                        SET warn_count = warn_count - 1 
                        WHERE guild_id = ? 
                        AND (strftime('%s', 'now') - strftime('%s', last_warned)) / 3600 >= ?
                    """, (guild_id, hours))

                    # Optional: Lösche Verwarnungen mit `warn_count <= 0`
                    await db.execute("""
                        DELETE FROM warns WHERE guild_id = ? AND warn_count <= 0
                    """, (guild_id,))

                await db.commit()

            print("✅ Abgelaufene Verwarnungen wurden reduziert!")

    async def log_action(self, guild, action, details):
        """Sendet Moderationslogs in den festgelegten Log-Channel"""
        log_channel_id = await self.get_setting(guild.id, "log_channel_id")  # Hol den Log-Channel aus der DB
        if not log_channel_id:
            return  # Kein Log-Channel gesetzt, also keine Aktion

        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            return  # Falls der Channel nicht gefunden wird (gelöscht oder Bot hat keine Rechte)

        embed = discord.Embed(title="🔍 Moderationslog", color=discord.Color.orange())
        embed.add_field(name="📢 Aktion", value=action, inline=False)
        embed.add_field(name="📋 Details", value=details, inline=False)
        embed.set_footer(text=f"Server: {guild.name}")

        await log_channel.send(embed=embed)

    async def is_capslock_enabled(self, guild_id):
        """Überprüft, ob der Capslock-Filter für diesen Server aktiviert ist."""
        async with aiosqlite.connect("server_settings.db") as db:
            async with db.execute("SELECT capslock_filter FROM settings WHERE guild_id = ?", (guild_id,)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else False

    async def store_servers(self):
        """Speichert alle Server und deren Mitglieder in der Datenbank."""
        await self.bot.wait_until_ready()  # Wartet, bis der Bot vollständig gestartet ist
        async with aiosqlite.connect("server_settings.db") as db:
            for guild in self.bot.guilds:
                await db.execute("""
                    INSERT INTO settings (guild_id, guild_name)
                    VALUES (?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET guild_name = excluded.guild_name
                """, (guild.id, guild.name))

                # 🔹 Jetzt über Mitglieder iterieren!
                for member in guild.members:
                    if not member.bot:  # Bots ignorieren
                        await db.execute("""
                            INSERT INTO warns (guild_id, guild_name, user_id, username) 
                            VALUES (?, ?, ?, ?) 
                            ON CONFLICT(guild_id, user_id) 
                            DO UPDATE SET username = excluded.username
                        """, (guild.id, guild.name, member.id, member.name))

            await db.commit()
        print("✅ Alle Server & Mitglieder wurden erfolgreich gespeichert!")

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

    @slash_command(name="set_autorole", description="Setzt die Standardrollen für neue Mitglieder (Admin only).")
    @commands.has_permissions(administrator=True)
    async def set_autorole(self, ctx,
                           role1: Option(discord.Role, "Wähle eine Rolle", required=True),
                           role2: Option(discord.Role, "Wähle eine weitere Rolle", required=False),
                           role3: Option(discord.Role, "Noch eine Rolle", required=False)):
        """Speichert die Standardrollen für neue Mitglieder."""
        roles = [role1]
        if role2: roles.append(role2)
        if role3: roles.append(role3)

        role_ids = ",".join(str(role.id) for role in roles)
        await self.update_setting(ctx.guild.id, "default_roles", role_ids)

        await ctx.respond(f"✅ Standardrollen gesetzt: {', '.join(r.mention for r in roles)}!")

    @slash_command(name="allow_domain", description="Erlaubt eine Domain für Links (Admin only).")
    @commands.has_permissions(administrator=True)
    async def allow_domain(self, ctx, domain: Option(str, "Gib die erlaubte Domain ein (z. B. example.com)")):
        """Fügt eine Domain zur Link-Whitelist hinzu"""
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute(
                "INSERT INTO allowed_domains (guild_id, domain) VALUES (?, ?) ON CONFLICT(guild_id, domain) DO NOTHING",
                (ctx.guild.id, domain.lower()))
            await db.commit()

        await ctx.respond(f"✅ Die Domain `{domain}` wurde zur Whitelist hinzugefügt!")

    @slash_command(name="set_welcome_embed", description="Setzt die personalisierte Begrüßung (Admin only).")
    @commands.has_permissions(administrator=True)
    async def set_welcome_embed(self, ctx, channel: Option(discord.TextChannel, "Begrüßungskanal auswählen"),
                                title: Option(str, "Titel der Begrüßungsnachricht"),
                                message: Option(str,
                                                "Willkommensnachricht eingeben. Nutze {user} für den neuen Nutzer"),
                                color: Option(str, "Embed-Farbe als HEX (z. B. #3498db)", default="#3498db")):
        """Speichert eine personalisierte Begrüßungsnachricht mit Nutzer-Platzhalter."""
        await self.update_setting(ctx.guild.id, "welcome_message", message)  # Speichert die Nachricht mit {user}
        await self.update_setting(ctx.guild.id, "welcome_channel_id", channel.id)

        await ctx.respond(f"✅ Begrüßungsnachricht gesetzt! Wird in {channel.mention} gesendet.")

        # Vorschau-Embed (Admin sieht, wie es aussehen würde)
        preview_embed = discord.Embed(title=title, description=message.replace("{user}", ctx.author.mention),
                                      color=discord.Color(int(color.lstrip("#"), 16)))
        preview_embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        preview_embed.set_footer(text=f"Willkommen auf {ctx.guild.name}!")
        await channel.send(embed=preview_embed)

    @slash_command(name="set_leave_embed", description="Setzt die personalisierte Abschiedsnachricht (Admin only).")
    @commands.has_permissions(administrator=True)
    async def set_leave_embed(self, ctx, channel: Option(discord.TextChannel, "Abschiedskanal auswählen"),
                              title: Option(str, "Titel der Abschiedsnachricht"),
                              message: Option(str, "Abschiedsnachricht eingeben. Nutze {user} für den Namen"),
                              color: Option(str, "Embed-Farbe als HEX (z. B. #e74c3c)", default="#e74c3c")):
        """Speichert eine personalisierte Abschiedsnachricht in einem bestimmten Kanal."""
        await self.update_setting(ctx.guild.id, "leave_message", message)
        await self.update_setting(ctx.guild.id, "leave_channel_id", channel.id)

        await ctx.respond(f"✅ Abschiedsnachricht wurde gesetzt! Nachrichten werden in {channel.mention} gesendet.")

        # Vorschau des Embeds senden
        preview_embed = discord.Embed(title=title, description=message.replace("{user}", ctx.author.mention),
                                      color=discord.Color(int(color.lstrip("#"), 16)))
        preview_embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        preview_embed.set_footer(text=f"Wir hoffen, du kommst wieder auf {ctx.guild.name}!")
        await channel.send(embed=preview_embed)

    @slash_command(name="remove_domain", description="Entfernt eine erlaubte Domain aus der Whitelist (Admin only).")
    @commands.has_permissions(administrator=True)
    async def remove_domain(self, ctx, domain: Option(str, "Gib die zu entfernende Domain ein (z. B. example.com)")):
        """Entfernt eine Domain von der Whitelist"""
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("DELETE FROM allowed_domains WHERE guild_id = ? AND domain = ?",
                             (ctx.guild.id, domain.lower()))
            await db.commit()

        await ctx.respond(f"❌ Die Domain `{domain}` wurde von der Whitelist entfernt!")



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

    @slash_command(name="set_warn_decay", description="Legt fest, nach wie vielen Stunden eine Warnung gelöscht wird.")
    @commands.has_permissions(administrator=True)
    async def set_warn_decay(self, ctx, hours: Option(int, "Anzahl der Stunden bis zur Löschung einer Warnung")):
        """Speichert, nach wie vielen Stunden eine Verwarnung gelöscht wird."""
        await self.update_setting(ctx.guild.id, "warn_decay_hours", hours)
        await ctx.respond(f"✅ Warnungen verfallen nun nach **{hours} Stunden**.")

    @slash_command(name="set_automod", description="Aktiviert oder deaktiviert automatische Moderation (Admin only).")
    @commands.has_permissions(administrator=True)
    async def set_automod(self, ctx, capslock: Option(bool, "Capslock-Spam blockieren?", default=False),
                          links: Option(bool, "Links blockieren?", default=False),
                          mentions: Option(bool, "Massen-Pings blockieren?", default=False)):
        await self.update_setting(ctx.guild.id, "capslock_filter", capslock)
        await self.update_setting(ctx.guild.id, "link_filter", links)
        await self.update_setting(ctx.guild.id, "mention_filter", mentions)
        await ctx.respond("✅ Auto-Moderationseinstellungen wurden aktualisiert!")

   ### --- Warns --- ###
    @slash_command(name="warn", description="Verwarnt einen Benutzer.")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: Option(discord.Member, "Wähle den Nutzer"),
                   reason: Option(str, "Grund für die Verwarnung")):
        """Verwarnt einen Nutzer und überprüft, ob Strafen angewendet werden müssen."""
        async with aiosqlite.connect("server_settings.db") as db:
            # Aktuelle Anzahl der Verwarnungen abrufen
            async with db.execute("SELECT warn_count FROM warns WHERE guild_id = ? AND user_id = ?",
                                  (ctx.guild.id, member.id)) as cursor:
                result = await cursor.fetchone()
                warn_count = result[0] + 1 if result else 1  # Falls Nutzer nicht existiert → 1. Warnung

            # Verwarnung in die DB eintragen
            await db.execute("""
                INSERT INTO warns (guild_id, guild_name, user_id, username, warn_count, last_warned) 
                VALUES (?, ?, ?, ?, ?, strftime('%s', 'now'))
                ON CONFLICT(guild_id, user_id) 
                DO UPDATE SET warn_count = excluded.warn_count, last_warned = excluded.last_warned
            """, (ctx.guild.id, ctx.guild.name, member.id, member.name, warn_count))

            await db.commit()

        # 📢 Embed für die Verwarnung
        embed = discord.Embed(title="⚠ Verwarnung", description=f"{member.mention} wurde verwarnt.",
                              color=discord.Color.orange())
        embed.add_field(name="Grund", value=reason, inline=False)
        embed.add_field(name="Anzahl Verwarnungen", value=warn_count, inline=True)
        embed.set_footer(text=f"Verwarnt von {ctx.author.name}")

        await ctx.respond(embed=embed)

        # **📌 Bestrafungen**
        if warn_count == 2:
            await member.timeout(discord.utils.utcnow() + timedelta(minutes=10), reason="2 Verwarnungen erhalten")
            await ctx.send(f"⏳ {member.mention} wurde **für 10 Minuten getimeoutet** wegen 2 Verwarnungen.")
        elif warn_count == 4:
            await member.kick(reason="4 Verwarnungen erhalten")
            await ctx.send(f"🚪 {member.mention} wurde **gekickt** wegen 4 Verwarnungen.")
        elif warn_count >= 5:
            await member.ban(reason="5 Verwarnungen erhalten")
            await ctx.send(f"⛔ {member.mention} wurde **gebannt** wegen 5 Verwarnungen.")

    @slash_command(name="clear_warns", description="Setzt die Verwarnungen eines Nutzers zurück (Admin only).")
    @commands.has_permissions(manage_messages=True)
    async def clear_warns(self, ctx, member: Option(discord.Member, "Wähle den Nutzer")):
        """Löscht alle Verwarnungen eines Nutzers."""
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("""
                UPDATE warns 
                SET warn_count = 0 
                WHERE guild_id = ? AND user_id = ?
            """, (ctx.guild.id, member.id))
            await db.commit()  # ✅ Änderungen speichern

        # 📢 Bestätigung senden
        embed = discord.Embed(title="✅ Verwarnungen gelöscht",
                              description=f"Alle Verwarnungen von {member.mention} wurden entfernt.",
                              color=discord.Color.green())
        embed.set_footer(text=f"Verwarnungen entfernt von {ctx.author.name}")

        await ctx.respond(embed=embed)

    ### --- COOLDOWNS --- ###

    @slash_command(name="set_global_cooldown", description="Setzt einen Cooldown für alle Befehle (Admin only).")
    @commands.has_permissions(administrator=True)
    async def set_global_cooldown(self, ctx, seconds: Option(int, "Cooldown in Sekunden für alle Befehle")):
        """Setzt einen Cooldown für alle Befehle des Servers"""
        async with aiosqlite.connect("server_settings.db") as db:
            # Alle existierenden Commands aus der Datenbank holen
            async with db.execute("SELECT DISTINCT command FROM cooldowns WHERE guild_id = ?",
                                  (ctx.guild.id,)) as cursor:
                commands_in_db = [row[0] for row in await cursor.fetchall()]

            # Falls die Tabelle noch leer ist, alle existierenden Commands setzen
            if not commands_in_db:
                commands_in_db = [cmd.qualified_name for cmd in self.bot.application_commands]

            # Cooldown für alle Befehle setzen
            for command in commands_in_db:
                await db.execute("""
                    INSERT INTO cooldowns (guild_id, command, seconds) 
                    VALUES (?, ?, ?) 
                    ON CONFLICT(guild_id, command) 
                    DO UPDATE SET seconds = excluded.seconds
                """, (ctx.guild.id, command, seconds))

            await db.commit()

        await ctx.respond(f"✅ Cooldown von **{seconds} Sekunden** für **alle Befehle** gesetzt!", ephemeral=True)

    @slash_command(name="clear_all_cooldowns", description="Entfernt alle Cooldowns für den Server (Admin only).")
    @commands.has_permissions(administrator=True)
    async def clear_all_cooldowns(self, ctx):
        """Löscht alle Cooldowns für den Server"""
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("DELETE FROM cooldowns WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        await ctx.respond("✅ Alle Cooldowns für diesen Server wurden entfernt!", ephemeral=True)

    @slash_command(name="remove_cooldown", description="Löscht den Cooldown eines Befehls (Admin only).")
    @commands.has_permissions(administrator=True)
    async def remove_cooldown(self, ctx, command: Option(str, "Name des Befehls")):
        """Entfernt einen gesetzten Cooldown aus der Datenbank"""
        async with aiosqlite.connect("server_settings.db") as db:
            async with db.execute("SELECT * FROM cooldowns WHERE guild_id = ? AND command = ?",
                                  (ctx.guild.id, command)) as cursor:
                result = await cursor.fetchone()

            if not result:
                await ctx.respond(f"❌ Es gibt keinen Cooldown für `{command}`.", ephemeral=True)
                return

            await db.execute("DELETE FROM cooldowns WHERE guild_id = ? AND command = ?", (ctx.guild.id, command))
            await db.commit()

        await ctx.respond(f"✅ Der Cooldown für `{command}` wurde erfolgreich entfernt!", ephemeral=True)

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

        if not message.content.strip():  # Falls die Nachricht nur ein Bild/Anhang ist
            return

        async with aiosqlite.connect("server_settings.db") as db:
            async with db.execute("SELECT word FROM blacklisted_words WHERE guild_id = ?",
                                  (message.guild.id,)) as cursor:
                blacklist = [row[0] for row in await cursor.fetchall()]

            async with db.execute("SELECT mention_filter FROM settings WHERE guild_id = ?",
                                  (message.guild.id,)) as cursor:
                mention_filter = (await cursor.fetchone() or [False])[0]

            async with db.execute("SELECT link_filter FROM settings WHERE guild_id = ?", (message.guild.id,)) as cursor:
                link_filter = (await cursor.fetchone() or [False])[0]

            async with db.execute("SELECT capslock_filter FROM settings WHERE guild_id = ?",
                                  (message.guild.id,)) as cursor:
                capslock_enabled = (await cursor.fetchone() or [False])[0]

            async with db.execute("SELECT domain FROM allowed_domains WHERE guild_id = ?",
                                  (message.guild.id,)) as cursor:
                allowed_domains = [row[0] for row in await cursor.fetchall()]

        # **🔹 Blacklist-Filter**
        filtered_message = "".join(c if c.isalnum() or c.isspace() else " " for c in message.content).lower()
        if any(word in filtered_message.split() for word in blacklist):
            await self.log_action(message.guild, "🔴 Blacklist-Wort erkannt", f"{message.author}: `{message.content}`")
            await message.delete()
            await message.channel.send(f"{message.author.mention}, dieses Wort ist auf der Blacklist!", delete_after=5)
            return  # Verhindert weitere Verarbeitung

        # **🔹 Mass Mention Filter (Mehr als 5 Pings)**
        if mention_filter and len(message.mentions) > 5:
            await self.log_action(message.guild, "🚨 Mass-Ping erkannt",
                                  f"{message.author} hat {len(message.mentions)} Leute erwähnt!")
            await message.delete()
            await message.channel.send(f"{message.author.mention}, bitte keine Mass-Pings! 🚨", delete_after=5)
            return

        # **🔹 Link-Filter mit Whitelist**
        if link_filter:
            url_pattern = re.compile(r"https?://(?:www\.)?([^/\s]+)")
            urls = url_pattern.findall(message.content)

            for domain in urls:
                if domain.lower() not in allowed_domains and not any(
                        sub in domain.lower() for sub in ["tenor.com", "giphy.com"]):
                    await self.log_action(message.guild, "🔗 Unerlaubter Link erkannt",
                                          f"{message.author}: `{message.content}` (Domain: {domain})")
                    await message.delete()
                    await message.channel.send(f"{message.author.mention}, Links von `{domain}` sind nicht erlaubt! 🚫",
                                               delete_after=5)
                    return

        # **🔹 Capslock-Filter**
        def is_capslock_message(text: str, threshold: float = 0.8) -> bool:
            """Prüft, ob eine Nachricht größtenteils aus Großbuchstaben besteht."""
            if len(text) < 5:
                return False

            upper_chars = sum(1 for c in text if c.isupper())
            total_chars = sum(1 for c in text if c.isalpha())

            if total_chars == 0:
                return False

            return (upper_chars / total_chars) >= threshold

        if capslock_enabled and is_capslock_message(message.content):
            await self.log_action(message.guild, "🔊 Capslock erkannt", f"{message.author}: `{message.content}`")
            await message.delete()
            await message.channel.send(f"{message.author.mention}, bitte nicht schreien! 🔇", delete_after=5)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Gibt neuen Mitgliedern Standardrollen und sendet eine Begrüßungsnachricht mit Nutzer-Erwähnung."""
        async with aiosqlite.connect("server_settings.db") as db:
            async with db.execute("SELECT welcome_message, welcome_channel_id FROM settings WHERE guild_id = ?",
                                  (member.guild.id,)) as cursor:
                result = await cursor.fetchone()
                if not result:
                    return  # Falls keine Einstellungen existieren, nichts tun

                welcome_message, welcome_channel_id = result

                # 🔹 Begrüßungsnachricht senden
                if welcome_message and welcome_channel_id:
                    channel = member.guild.get_channel(welcome_channel_id)
                    if channel:
                        embed = discord.Embed(title="👋 Willkommen!",
                                              description=welcome_message.replace("{user}", member.mention),
                                              color=discord.Color.green())
                        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
                        embed.set_footer(text=f"Willkommen auf {member.guild.name}!")
                        await channel.send(embed=embed)

        """Weist neuen Mitgliedern automatisch die Standardrollen zu."""
        async with aiosqlite.connect("server_settings.db") as db:
            async with db.execute("SELECT default_roles FROM settings WHERE guild_id = ?",
                                  (member.guild.id,)) as cursor:
                result = await cursor.fetchone()
                if not result or not result[0]:
                    return  # Keine Rollen gesetzt

                role_ids = [int(r) for r in result[0].split(",") if r.isdigit()]
                roles_to_add = [member.guild.get_role(rid) for rid in role_ids if member.guild.get_role(rid)]

                if roles_to_add:
                    await member.add_roles(*roles_to_add, reason="Automatische Rollenzuweisung")
                    print(f"✅ {member.name} hat {len(roles_to_add)} Standardrollen erhalten!")
        """Fügt neue Mitglieder automatisch zur Warn-Datenbank hinzu."""
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("""
                    INSERT INTO warns (guild_id, guild_name, user_id, username) 
                    VALUES (?, ?, ?, ?) 
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET username = excluded.username
                """, (member.guild.id, member.guild.name, member.id, member.name))
            await db.commit()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Sendet eine Abschiedsnachricht, wenn ein Mitglied den Server verlässt."""
        async with aiosqlite.connect("server_settings.db") as db:
            async with db.execute("SELECT leave_message, leave_channel_id FROM settings WHERE guild_id = ?",
                                  (member.guild.id,)) as cursor:
                result = await cursor.fetchone()
                if not result:
                    return  # Falls keine Einstellungen existieren, nichts tun

                leave_message, leave_channel_id = result

                # 🔹 Abschiedsnachricht senden
                if leave_message and leave_channel_id:
                    channel = member.guild.get_channel(leave_channel_id)
                    if channel:
                        embed = discord.Embed(title="😢 Auf Wiedersehen!",
                                              description=leave_message.replace("{user}", member.mention),
                                              color=discord.Color.red())
                        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
                        embed.set_footer(text=f"Wir hoffen, du kommst wieder auf {member.guild.name}!")
                        await channel.send(embed=embed)

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


@commands.Cog.listener()
async def on_member_join(self, member):
    """Gibt neuen Mitgliedern Standardrollen und sendet eine Begrüßungsnachricht."""
    async with aiosqlite.connect("server_settings.db") as db:
        async with db.execute(
                "SELECT default_roles, welcome_message, welcome_channel_id FROM settings WHERE guild_id = ?",
                (member.guild.id,)) as cursor:
            result = await cursor.fetchone()
            if not result:
                return  # Falls keine Einstellungen vorhanden sind, abbrechen

            default_roles, welcome_message, welcome_channel_id = result

            # 🔹 Automatische Rollenzuweisung
            if default_roles:
                role_ids = [int(r) for r in default_roles.split(",") if r.isdigit()]
                roles_to_add = [member.guild.get_role(rid) for rid in role_ids if member.guild.get_role(rid)]

                if roles_to_add:
                    await member.add_roles(*roles_to_add, reason="Automatische Rollenzuweisung")
                    print(f"✅ {member.name} hat {len(roles_to_add)} Standardrollen erhalten!")

            # 🔹 Begrüßungsnachricht senden
            if welcome_message and welcome_channel_id:
                channel = member.guild.get_channel(welcome_channel_id)
                if channel:
                    embed = discord.Embed(title="👋 Willkommen!",
                                          description=welcome_message.replace("{user}", member.mention),
                                          color=discord.Color.green())
                    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
                    embed.set_footer(text=f"Willkommen auf {member.guild.name}!")
                    await channel.send(embed=embed)


def setup(bot):
    bot.add_cog(ServerSettings(bot))
