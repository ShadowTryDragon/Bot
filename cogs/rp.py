import discord
from discord.ext import commands, tasks
from discord.commands import slash_command, Option
import aiosqlite
import re
from datetime import datetime

GUILD_ID = 824029270384312341


class Geburtstage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.geburtstag_auto_update.start()

    async def init_db(self):
        async with aiosqlite.connect("charaktere.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS geburtstage (
                    name TEXT PRIMARY KEY,
                    tag INTEGER,
                    monat INTEGER,
                    alterc INTEGER DEFAULT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER
                )
            """)
            await db.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.init_db()
        print("✅ Geburtstags-System bereit")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        if message.guild.id != GUILD_ID:
            return

        async with aiosqlite.connect("charaktere.db") as db:
            async with db.execute("SELECT channel_id FROM settings WHERE guild_id = ?", (message.guild.id,)) as cursor:
                row = await cursor.fetchone()
                if not row or row[0] != message.channel.id:
                    return  # Nur im festgelegten Channel

        match = re.match(r"^(.+):\s*(\d{1,2})\.(\d{1,2})$", message.content.strip())
        if not match:
            return

        name, tag, monat = match.groups()
        tag = int(tag)
        monat = int(monat)

        async with aiosqlite.connect("charaktere.db") as db:
            await db.execute("INSERT OR IGNORE INTO geburtstage (name, tag, monat) VALUES (?, ?, ?)",
                             (name.strip(), tag, monat))
            await db.commit()

        await message.delete()
        print(f"🎉 Geburtstag gespeichert: {name} am {tag}.{monat}")

    @slash_command(name="setgebchannel", description="Setzt den Kanal für Geburtstags-Einträge")
    @discord.default_permissions(administrator=True)
    async def set_channel(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        if ctx.guild.id != GUILD_ID:
            return await ctx.respond("Dieser Command ist auf diesem Server nicht erlaubt.", ephemeral=True)

        async with aiosqlite.connect("charaktere.db") as db:
            await db.execute("INSERT OR REPLACE INTO settings (guild_id, channel_id) VALUES (?, ?)",
                             (ctx.guild.id, channel.id))
            await db.commit()
        await ctx.respond(f"✅ Geburtstags-Channel wurde auf {channel.mention} gesetzt.", ephemeral=True)

    from discord.commands import Option

    @commands.slash_command(name="delete_gb", description="Löscht einen Charakter aus der Geburtstagsliste.")
    async def geburtstag_loeschen(
            self,
            ctx,
            name: Option(str, "Name des Charakters, der gelöscht werden soll")
    ):
        # Nur auf dem Zielserver
        if ctx.guild.id != 824029270384312341:
            return await ctx.respond("Dieser Befehl ist hier nicht verfügbar.", ephemeral=True)

        async with aiosqlite.connect("charaktere.db") as db:
            cursor = await db.execute("SELECT * FROM geburtstage WHERE name = ?", (name,))
            eintrag = await cursor.fetchone()

            if not eintrag:
                return await ctx.respond(f"❌ Kein Eintrag mit dem Namen **{name}** gefunden.", ephemeral=True)

            await db.execute("DELETE FROM geburtstage WHERE name = ?", (name,))
            await db.commit()

        await ctx.respond(f"✅ Charakter **{name}** wurde aus der Liste gelöscht.", ephemeral=True)

    @commands.slash_command(name="geburtstage", description="Zeigt alle registrierten Geburtstage an.")
    async def geburtstage(self, ctx):
        await ctx.defer()

        # Nur auf dem Zielserver ausführen
        if ctx.guild.id != 824029270384312341:
            return await ctx.respond("Dieser Befehl ist nur auf dem offiziellen Server verfügbar.", ephemeral=True)

        async with aiosqlite.connect("charaktere.db") as db:
            cursor = await db.execute("SELECT name, tag, monat FROM geburtstage ORDER BY monat, tag")
            eintraege = await cursor.fetchall()

        if not eintraege:
            return await ctx.respond("Keine Geburtstage gefunden.", ephemeral=True)

        embed = discord.Embed(
            title="🎂 Geburtstage der Charaktere",
            color=discord.Color.purple()
        )

        monate = {
            1: "Januar", 2: "Februar", 3: "März", 4: "April",
            5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
            9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
        }

        gruppiert = {}
        for name, tag, monat in eintraege:
            gruppiert.setdefault(monat, []).append(f"`{tag:02d}.{monat:02d}` - **{name}**")

        for monat in sorted(gruppiert.keys()):
            eintraege_text = "\n".join(gruppiert[monat])
            embed.add_field(
                name=f"📅 {monate.get(monat, str(monat))}",
                value=eintraege_text,
                inline=False
            )

        # Nachricht editieren oder neu senden
        async with aiosqlite.connect("charaktere.db") as db:
            await db.execute("CREATE TABLE IF NOT EXISTS settings (channel_id INTEGER, message_id INTEGER)")
            await db.commit()

            row = await db.execute("SELECT channel_id, message_id FROM settings")
            settings = await row.fetchone()

            if settings:
                channel = ctx.guild.get_channel(settings[0])
                try:
                    old_msg = await channel.fetch_message(settings[1])
                    await old_msg.edit(embed=embed)
                    return await ctx.respond("✅ Geburtstagsliste aktualisiert!", ephemeral=True)
                except discord.NotFound:
                    pass  # Falls Nachricht gelöscht wurde

            # Neue Nachricht posten
            msg = await ctx.channel.send(embed=embed)
            await db.execute("DELETE FROM settings")
            await db.execute("INSERT INTO settings (channel_id, message_id) VALUES (?, ?)", (ctx.channel.id, msg.id))
            await db.commit()

        await ctx.respond("✅ Geburtstagsliste gepostet!", ephemeral=True)

    @tasks.loop(minutes=2)
    async def geburtstag_auto_update(self):
        async with aiosqlite.connect("charaktere.db") as db:
            await db.execute("""CREATE TABLE IF NOT EXISTS geburtstage (name TEXT, tag INTEGER, monat INTEGER)""")
            await db.execute("""CREATE TABLE IF NOT EXISTS settings (channel_id INTEGER, message_id INTEGER)""")
            await db.commit()

            cursor = await db.execute("SELECT name, tag, monat FROM geburtstage ORDER BY monat, tag")
            eintraege = await cursor.fetchall()

            cursor = await db.execute("SELECT channel_id, message_id FROM settings")
            settings = await cursor.fetchone()

        if not settings or not all(settings):
            return

        channel_id, message_id = settings
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            return

        if not eintraege:
            return

        embed = discord.Embed(
            title="🎂 Geburtstage der Charaktere",
            color=discord.Color.purple()
        )
        monate = {
            1: "Januar", 2: "Februar", 3: "März", 4: "April",
            5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
            9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
        }
        gruppiert = {}
        for name, tag, monat in eintraege:
            gruppiert.setdefault(monat, []).append(f"`{tag:02d}.{monat:02d}` - **{name}**")
        for monat in sorted(gruppiert.keys()):
            embed.add_field(
                name=f"📅 {monate.get(monat)}",
                value="\n".join(gruppiert[monat]),
                inline=False
            )

        await message.edit(embed=embed)

    @geburtstag_auto_update.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Geburtstage(bot))
