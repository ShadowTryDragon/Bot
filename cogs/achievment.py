import aiosqlite
import discord
from discord.ext import commands


class AchievementTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.create_db())  # Erstellt die Datenbank beim Start
        self.bot.loop.create_task(self.store_servers_and_users())  # Speichert Server & Nutzer

    async def create_db(self):
        """Erstellt die Datenbank und Tabellen, falls sie nicht existieren."""
        async with aiosqlite.connect("achievements.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS servers (
                    guild_id INTEGER PRIMARY KEY,
                    name TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER,
                    guild_id INTEGER,
                    name TEXT,
                    messages INTEGER DEFAULT 0,
                    reactions INTEGER DEFAULT 0,
                    commands_used INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            await db.commit()

    async def store_servers_and_users(self):
        """Speichert alle Server & Nutzer beim Start des Bots."""
        await self.bot.wait_until_ready()
        async with aiosqlite.connect("achievements.db") as db:
            # Server speichern
            for guild in self.bot.guilds:
                await db.execute("INSERT INTO servers (guild_id, name) VALUES (?, ?) ON CONFLICT(guild_id) DO NOTHING",
                                 (guild.id, guild.name))

                # Nutzer speichern
                for member in guild.members:
                    if not member.bot:
                        await db.execute("""
                            INSERT INTO users (user_id, guild_id, name) 
                            VALUES (?, ?, ?) 
                            ON CONFLICT(user_id, guild_id) DO UPDATE SET name = excluded.name
                        """, (member.id, guild.id, member.name))

            await db.commit()
        print(f"✅ {len(self.bot.guilds)} Server & ihre Nutzer wurden gespeichert!")

    async def add_user(self, guild, member):
        """Fügt einen neuen User in die Datenbank ein."""
        if not member.bot:
            async with aiosqlite.connect("achievements.db") as db:
                await db.execute("""
                    INSERT INTO users (user_id, guild_id, name) 
                    VALUES (?, ?, ?) 
                    ON CONFLICT(user_id, guild_id) DO NOTHING
                """, (member.id, guild.id, member.name))
                await db.commit()
            print(f"✅ Nutzer {member.name} wurde hinzugefügt.")



    async def remove_user(self, guild, member):
        """Löscht einen User aus der Datenbank, wenn er den Server verlässt."""
        async with aiosqlite.connect("achievements.db") as db:
            await db.execute("DELETE FROM users WHERE user_id = ? AND guild_id = ?", (member.id, guild.id))
            await db.commit()
        print(f"❌ Nutzer {member.name} wurde entfernt.")

    async def add_message(self, message):
        """Zählt Nachrichten & checkt für Erfolge."""
        async with aiosqlite.connect("achievements.db") as db:
            # Nachrichtenzähler erhöhen
            await db.execute("UPDATE users SET messages = messages + 1 WHERE user_id = ? AND guild_id = ?",
                             (message.author.id, message.guild.id))
            await db.commit()

            # Erfolg prüfen
            async with db.execute("SELECT messages FROM users WHERE user_id = ? AND guild_id = ?",
                                  (message.author.id, message.guild.id)) as cursor:
                result = await cursor.fetchone()
                if result:
                    messages = result[0]
                    if messages in [10, 100, 1000]:
                        await message.channel.send(f"🏆 {message.author.mention} hat {messages} Nachrichten gesendet!")

    async def add_reaction(self, reaction, user):
        """Zählt Reaktionen & checkt für Erfolge."""
        if user.bot:
            return

        @commands.Cog.listener()
        async def on_raw_reaction_add(self, payload):
            """Erkennt Reaktionen, auch wenn die Nachricht nicht im Cache ist."""
            user = self.bot.get_user(payload.user_id)
            if user.bot:
                return

            print(f"✅ Reaktion erkannt: {payload.emoji.name} von {user.name}")

            # Falls du die Gilde (Server) brauchst
            guild = self.bot.get_guild(payload.guild_id)
            if guild:
                print(f"🎉 Reaktion passiert in: {guild.name}")

                # Falls du die Nachricht laden willst
                channel = self.bot.get_channel(payload.channel_id)
                if channel:
                    try:
                        message = await channel.fetch_message(payload.message_id)
                        print(f"📩 Nachricht: {message.content}")
                    except discord.NotFound:
                        print("❌ Nachricht nicht gefunden (vielleicht gelöscht?)")

            await self.add_reaction(reaction, user)

        async with aiosqlite.connect("achievements.db") as db:
            # Reaktionszähler erhöhen
            await db.execute("UPDATE users SET reactions = reactions + 1 WHERE user_id = ? AND guild_id = ?",
                             (user.id, reaction.message.guild.id))
            await db.commit()

            # Erfolg prüfen
            async with db.execute("SELECT reactions FROM users WHERE user_id = ? AND guild_id = ?",
                                  (user.id, reaction.message.guild.id)) as cursor:
                result = await cursor.fetchone()
                if result:
                    reactions = result[0]
                    if reactions in [10, 100]:
                        await reaction.message.channel.send(f"🏆 {user.mention} hat {reactions} Reaktionen verwendet!")

    async def add_command_usage(self, ctx):
        """Zählt Befehlsnutzung & checkt für Erfolge."""
        async with aiosqlite.connect("achievements.db") as db:
            # Befehlzähler erhöhen
            await db.execute("UPDATE users SET commands_used = commands_used + 1 WHERE user_id = ? AND guild_id = ?",
                             (ctx.author.id, ctx.guild.id))
            await db.commit()

            # Erfolg prüfen
            async with db.execute("SELECT commands_used FROM users WHERE user_id = ? AND guild_id = ?",
                                  (ctx.author.id, ctx.guild.id)) as cursor:
                result = await cursor.fetchone()
                if result:
                    commands_used = result[0]
                    if commands_used in [10, 100, 1000]:
                        await ctx.send(f"🏆 {ctx.author.mention} hat {commands_used} Befehle genutzt!")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Wird bei jeder gesendeten Nachricht ausgelöst (ohne Bots)."""
        if message.author.bot:
            return
        await self.add_message(message)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Wird bei jeder Reaktion ausgelöst."""
        await self.add_reaction(reaction, user)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Fügt einen neuen User hinzu, wenn er dem Server beitritt."""
        await self.add_user(member.guild, member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Löscht einen User, wenn er den Server verlässt."""
        await self.remove_user(member.guild, member)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Fügt einen neuen Server hinzu, wenn der Bot einem Server beitritt."""
        async with aiosqlite.connect("achievements.db") as db:
            await db.execute("INSERT INTO servers (guild_id, name) VALUES (?, ?) ON CONFLICT(guild_id) DO NOTHING",
                             (guild.id, guild.name))
            for member in guild.members:
                if not member.bot:
                    await db.execute(
                        "INSERT INTO users (user_id, guild_id, name) VALUES (?, ?, ?) ON CONFLICT(user_id, guild_id) DO NOTHING",
                        (member.id, guild.id, member.name))
            await db.commit()
        print(f"✅ Neuer Server hinzugefügt: {guild.name}")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Löscht einen Server aus der Datenbank, wenn der Bot entfernt wird."""
        async with aiosqlite.connect("achievements.db") as db:
            await db.execute("DELETE FROM servers WHERE guild_id = ?", (guild.id,))
            await db.execute("DELETE FROM users WHERE guild_id = ?", (guild.id,))
            await db.commit()
        print(f"❌ Server entfernt: {guild.name}")

    @commands.Cog.listener()
    async def on_application_command_completion(self, ctx):
        """Zählt ausgeführte Slash-Befehle."""
        await self.add_command_usage(ctx)


def setup(bot):
    bot.add_cog(AchievementTracker(bot))
