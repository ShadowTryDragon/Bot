import discord
import aiosqlite
from discord.ext import commands, tasks
import asyncio

class PrivateVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_empty_channels.start()  # Task für leere Channels starten

    async def create_tables(self):
        """Erstellt die notwendigen Tabellen in der Datenbank."""
        async with aiosqlite.connect("channels.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS servers (
                    guild_id INTEGER PRIMARY KEY,
                    guild_name TEXT,
                    voice_setup INTEGER,
                    text_setup INTEGER,
                    message_id INTEGER,
                    ticket_embed_title TEXT DEFAULT '🎫 Ticketsystem',
                    ticket_embed_description TEXT DEFAULT 'Klicke auf den Button, um ein Ticket zu erstellen.',
                    ticket_embed_color TEXT DEFAULT '#3498db'  -- Standard Blau
                    
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS voice_channels (
                    channel_id INTEGER PRIMARY KEY,
                    channel_name TEXT,
                    user_id INTEGER,
                    user_name TEXT,
                    guild_id INTEGER,
                    FOREIGN KEY (guild_id) REFERENCES servers (guild_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS text_channels (
                    channel_id INTEGER PRIMARY KEY,
                    channel_name TEXT,
                    user_id INTEGER,
                    user_name TEXT,
                    guild_id INTEGER,
                    ticket_id INTEGER,
                    message_id INTEGER,
                    FOREIGN KEY (guild_id) REFERENCES servers (guild_id)
                )
            """)
            await db.execute("""
                            CREATE TABLE IF NOT EXISTS tickets (
                                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                channel_id INTEGER,
                                user_id INTEGER,
                                user_name TEXT,
                                guild_id INTEGER,
                                message_id INTEGER,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                status TEXT DEFAULT 'open',                     
                                FOREIGN KEY (guild_id) REFERENCES servers (guild_id)
                            )
                        """)
            await db.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        """Fügt alle Server zur Datenbank hinzu & entfernt nicht mehr existierende Voice-Channels."""
        await self.create_tables()

        async with aiosqlite.connect("channels.db") as db:
            for guild in self.bot.guilds:
                await db.execute(
                    "INSERT OR IGNORE INTO servers (guild_id, guild_name, voice_setup, text_setup) VALUES (?, ?, NULL, NULL)",
                    (guild.id, guild.name)
                )
            await db.commit()

        print("✅ Alle Server wurden zur Datenbank hinzugefügt.")

        # **🔹 Entferne nicht existierende Voice-Channels**
        async with aiosqlite.connect("channels.db") as db:
            rows = await db.execute("SELECT channel_id FROM voice_channels")
            voice_channels = await rows.fetchall()

        deleted_channels = 0  # Debugging-Zähler

        for channel_id, in voice_channels:
            channel = self.bot.get_channel(channel_id)

            if channel is None:  # Kanal existiert nicht mehr
                async with aiosqlite.connect("channels.db") as db:
                    await db.execute("DELETE FROM voice_channels WHERE channel_id = ?", (channel_id,))
                    await db.commit()
                print(f"🗑 Gelöschter Eintrag: Channel-ID {channel_id} existiert nicht mehr.")
                deleted_channels += 1

        print(f"🔍 Voice-Channel-Bereinigung abgeschlossen. {deleted_channels} nicht existierende Kanäle entfernt.")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Fügt einen neuen Server zur Datenbank hinzu."""
        async with aiosqlite.connect("channels.db") as db:
            await db.execute(
                "INSERT OR IGNORE INTO servers (guild_id, guild_name, voice_setup, text_setup) VALUES (?, ?, NULL, NULL)",
                (guild.id, guild.name)
            )
            await db.commit()
        print(f"✅ Server {guild.name} wurde zur Datenbank hinzugefügt.")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Entfernt einen Server aus der Datenbank, wenn der Bot ihn verlässt."""
        async with aiosqlite.connect("channels.db") as db:
            await db.execute("DELETE FROM servers WHERE guild_id = ?", (guild.id,))
            await db.execute("DELETE FROM voice_channels WHERE guild_id = ?", (guild.id,))
            await db.execute("DELETE FROM text_channels WHERE guild_id = ?", (guild.id,))  # NEU: Textkanäle löschen
            await db.commit()
        print(f"❌ Server {guild.name} wurde aus der Datenbank entfernt.")

    @commands.slash_command(name="voice-setup", description="Erstellt den Voice-Setup-Channel")
    @commands.has_permissions(administrator=True)
    async def voice_setup(self, ctx):
        """Erstellt die Kategorie & den Setup-Channel für private Sprachkanäle."""
        guild = ctx.guild

        # Prüfen, ob bereits ein Setup-Channel existiert
        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT voice_setup FROM servers WHERE guild_id = ?", (guild.id,))
            result = await row.fetchone()

        if result and result[0]:
            return await ctx.respond("⚠ Es gibt bereits einen Setup-Channel!", ephemeral=True)

        # Kategorie erstellen
        category = await guild.create_category("🎤 Private Channels")
        setup_channel = await guild.create_voice_channel("➕ Join to Create", category=category)

        # Speichern in DB (Spalte heißt jetzt voice_setup)
        async with aiosqlite.connect("channels.db") as db:
            await db.execute("UPDATE servers SET voice_setup = ? WHERE guild_id = ?", (setup_channel.id, guild.id))
            await db.commit()

        await ctx.respond(
            f"✅ Setup abgeschlossen! Betritt {setup_channel.mention}, um einen eigenen Kanal zu erstellen.",
            ephemeral=True)

    @commands.slash_command(name="rename-voice", description="Ändert den Namen deines privaten Kanals.")
    async def rename_voice(self, ctx, neuer_name: str):
        """Lässt den Besitzer seinen Kanal umbenennen."""
        member = ctx.author
        voice_channel = member.voice.channel if member.voice else None

        if not voice_channel:
            return await ctx.respond("⚠ Du bist in keinem Voice-Channel!", ephemeral=True)

        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT user_id FROM voice_channels WHERE channel_id = ?", (voice_channel.id,))
            result = await row.fetchone()

        if not result or result[0] != member.id:
            return await ctx.respond("❌ Du bist nicht der Besitzer dieses Kanals!", ephemeral=True)

        await voice_channel.edit(name=neuer_name)  # Kanal umbenennen

        async with aiosqlite.connect("channels.db") as db:
            await db.execute("UPDATE voice_channels SET channel_name = ? WHERE channel_id = ?",
                             (neuer_name, voice_channel.id))
            await db.commit()

        await ctx.respond(f"✅ Dein Kanal wurde umbenannt zu **{neuer_name}**!")

    @commands.slash_command(name="kick-voice", description="Wirft einen Nutzer aus deinem privaten Kanal.")
    async def kick_voice(self, ctx, member: discord.Member):
        """Kickt einen User aus einem privaten Kanal."""
        voice_channel = ctx.author.voice.channel if ctx.author.voice else None

        if not voice_channel:
            return await ctx.respond("⚠ Du bist in keinem Voice-Channel!", ephemeral=True)

        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT user_id FROM voice_channels WHERE channel_id = ?", (voice_channel.id,))
            result = await row.fetchone()

        if not result or result[0] != ctx.author.id:
            return await ctx.respond("❌ Du bist nicht der Besitzer dieses Kanals!", ephemeral=True)

        if member not in voice_channel.members:
            return await ctx.respond("⚠ Dieser Nutzer ist nicht in deinem Kanal!", ephemeral=True)

        await member.move_to(None)  # User aus dem Kanal werfen
        await ctx.respond(f"👢 {member.mention} wurde aus deinem Kanal gekickt!")

    @commands.slash_command(name="lock-voice",
                            description="Sperrt deinen privaten Kanal (nur eingeladene User können rein).")
    async def lock_voice(self, ctx):
        """Macht den Kanal nur für den Besitzer & aktuelle Mitglieder zugänglich."""
        voice_channel = ctx.author.voice.channel if ctx.author.voice else None

        if not voice_channel:
            return await ctx.respond("⚠ Du bist in keinem Voice-Channel!", ephemeral=True)

        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT user_id FROM voice_channels WHERE channel_id = ?", (voice_channel.id,))
            result = await row.fetchone()

        if not result or result[0] != ctx.author.id:
            return await ctx.respond("❌ Du bist nicht der Besitzer dieses Kanals!", ephemeral=True)

        await voice_channel.set_permissions(ctx.guild.default_role, connect=False)  # Serverweite Verbindung sperren
        await ctx.respond("🔒 Dein Kanal ist jetzt gesperrt! Nur eingeladene Nutzer können beitreten.")

    @commands.slash_command(name="unlock-voice", description="Macht deinen privaten Kanal wieder für alle zugänglich.")
    async def unlock_voice(self, ctx):
        """Macht den Kanal wieder für alle zugänglich."""
        voice_channel = ctx.author.voice.channel if ctx.author.voice else None

        if not voice_channel:
            return await ctx.respond("⚠ Du bist in keinem Voice-Channel!", ephemeral=True)

        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT user_id FROM voice_channels WHERE channel_id = ?", (voice_channel.id,))
            result = await row.fetchone()

        if not result or result[0] != ctx.author.id:
            return await ctx.respond("❌ Du bist nicht der Besitzer dieses Kanals!", ephemeral=True)

        await voice_channel.set_permissions(ctx.guild.default_role, connect=True)  # Serverweite Verbindung erlauben
        await ctx.respond("🔓 Dein Kanal ist jetzt wieder öffentlich!")

    @commands.slash_command(name="limit-voice", description="Setzt die maximale Anzahl an Nutzern in deinem Kanal.")
    async def limit_voice(self, ctx, limit: int):
        """Setzt ein Benutzerlimit für den eigenen Voice-Channel."""
        voice_channel = ctx.author.voice.channel if ctx.author.voice else None

        if not voice_channel:
            return await ctx.respond("⚠ Du bist in keinem Voice-Channel!", ephemeral=True)

        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT user_id FROM voice_channels WHERE channel_id = ?", (voice_channel.id,))
            result = await row.fetchone()

        if not result or result[0] != ctx.author.id:
            return await ctx.respond("❌ Du bist nicht der Besitzer dieses Kanals!", ephemeral=True)

        if limit < 1 or limit > 99:
            return await ctx.respond("⚠ Das Limit muss zwischen 1 und 99 liegen!", ephemeral=True)

        await voice_channel.edit(user_limit=limit)
        await ctx.respond(f"✅ Dein Kanal hat nun ein Limit von {limit} Nutzer(n).")

    @commands.slash_command(name="remove-voice",
                            description="Entfernt den Setup-Channel und die Kategorie (Admin Only)")
    @commands.has_permissions(administrator=True)
    async def remove_voice(self, ctx):
        """Löscht den Voice-Setup-Channel, die Kategorie (falls leer) und entfernt die ID aus der Datenbank."""
        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT voice_setup FROM servers WHERE guild_id = ?", (ctx.guild.id,))
            result = await row.fetchone()

        if not result or not result[0]:
            return await ctx.respond("⚠ Kein Setup-Channel gefunden!", ephemeral=True)

        setup_channel = ctx.guild.get_channel(result[0])  # Voice-Setup-Channel abrufen
        category = setup_channel.category if setup_channel else None  # Zugehörige Kategorie abrufen

        if setup_channel:
            await setup_channel.delete()  # Voice-Setup-Channel löschen

        # Prüfen, ob die Kategorie noch andere Kanäle hat
        if category and len(category.channels) == 0:
            await category.delete()  # Nur löschen, wenn sie leer ist

        async with aiosqlite.connect("channels.db") as db:
            await db.execute("UPDATE servers SET voice_setup = NULL WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        await ctx.respond("✅ Der Setup-Channel und die Kategorie wurden erfolgreich entfernt!", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Erstellt einen privaten Kanal, wenn der User den Setup-Channel betritt, aber begrenzt auf 1 pro User."""

        if after.channel and before.channel != after.channel:
            async with aiosqlite.connect("channels.db") as db:
                # **Prüfen, ob der User bereits einen Kanal besitzt**
                row = await db.execute("SELECT channel_id FROM voice_channels WHERE user_id = ?", (member.id,))
                existing_channel = await row.fetchone()

                if existing_channel:
                    await member.send(
                        "⚠ Du hast bereits einen privaten Voice-Channel! Bitte verlasse ihn zuerst, bevor du einen neuen erstellst."
                    )
                    await member.move_to(None)  # User aus dem Voice-Channel kicken
                    return

                # **Setup-Channel aus der Datenbank holen**
                row = await db.execute("SELECT voice_setup FROM servers WHERE guild_id = ?", (member.guild.id,))
                result = await row.fetchone()

            if result:
                setup_channel_id = result[0]

                # **Nur wenn der Nutzer den Setup-Channel betritt**
                if after.channel.id == setup_channel_id:
                    new_channel = await after.channel.category.create_voice_channel(f"{member.name}'s Channel")
                    await member.move_to(new_channel)

                    # **Neuen Channel in der DB speichern**
                    async with aiosqlite.connect("channels.db") as db:
                        await db.execute(
                            "INSERT INTO voice_channels (channel_id, channel_name, user_id, user_name, guild_id) VALUES (?, ?, ?, ?, ?)",
                            (new_channel.id, new_channel.name, member.id, member.name, member.guild.id)
                        )
                        await db.commit()

                    print(f"🎤 {member.name} hat einen privaten Kanal erstellt: {new_channel.name}")
                else:
                    print(
                        f"🚫 {member.name} ist einem anderen Voice-Channel beigetreten, kein neuer Channel wird erstellt.")

        # **Leere Channels nach 5 Minuten automatisch löschen**
        if before.channel and before.channel.category and before.channel.category.name == "🎤 Private Channels":
            async with aiosqlite.connect("channels.db") as db:
                row = await db.execute("SELECT channel_id FROM voice_channels WHERE channel_id = ?",
                                       (before.channel.id,))
                result = await row.fetchone()

            if result and len(before.channel.members) == 0:  # Kanal ist leer
                await asyncio.sleep(300)  # 5 Minuten warten
                if len(before.channel.members) == 0:  # Noch immer leer?
                    await before.channel.delete()
                    async with aiosqlite.connect("channels.db") as db:
                        await db.execute("DELETE FROM voice_channels WHERE channel_id = ?", (before.channel.id,))
                        await db.commit()
                    print(f"🗑 Gelöschter Kanal: {before.channel.name}")

    @tasks.loop(minutes=1)
    async def check_empty_channels(self):
        """Regelmäßig leere Sprachkanäle aus der Datenbank entfernen."""
        async with aiosqlite.connect("channels.db") as db:
            rows = await db.execute("SELECT channel_id FROM voice_channels")  # Nur Sprachkanäle
            channels = await rows.fetchall()

        for channel_id, in channels:
            channel = self.bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.VoiceChannel) and len(channel.members) == 0:
                await asyncio.sleep(300)  # 5 Minuten warten
                if len(channel.members) == 0:  # Noch immer leer?
                    try:
                        await channel.delete()
                        async with aiosqlite.connect("channels.db") as db:
                            await db.execute("DELETE FROM voice_channels WHERE channel_id = ?", (channel_id,))
                            await db.commit()
                        print(f"🗑 Gelöschter Sprachkanal: {channel.name}")
                    except discord.NotFound:
                        print(f"⚠ Fehler: Sprachkanal {channel_id} existiert nicht mehr (bereits gelöscht).")
                    except discord.Forbidden:
                        print(f"❌ Fehler: Keine Berechtigung zum Löschen von Sprachkanal {channel_id}.")
                    except Exception as e:
                        print(f"⚠ Unerwarteter Fehler beim Löschen von Sprachkanal {channel_id}: {e}")


def setup(bot):
    bot.add_cog(PrivateVoice(bot))