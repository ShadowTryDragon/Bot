import discord
from discord.ext import commands, tasks
from discord.commands import slash_command, Option
import aiosqlite
import aiohttp
import feedparser
from bs4 import BeautifulSoup

FEED_URLS = {
    "Unknown Times": "https://naruto-unknown-times.fandom.com/de/wiki/Spezial:Neue_Seiten?feed=rss",
    "Echo of War": "https://naruto-rp.fandom.com/de/wiki/Spezial:Neue_Seiten?feed=rss"
}



class WikiUpdates(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_posted = None
        self.check_feed.start()

    @slash_command(name="disablewiki", description="Deaktiviert die Wiki-Benachrichtigungen für diesen Server.")
    @discord.default_permissions(administrator=True)
    async def disablewiki(self, ctx: discord.ApplicationContext):
        async with aiosqlite.connect("channels.db") as db:
            await db.execute("DELETE FROM text_channels WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        await ctx.respond("Wiki-Benachrichtigungen wurden deaktiviert.", ephemeral=True)

    @slash_command(name="wikistatus", description="Zeigt den aktuellen Status der Wiki-Integration.")
    async def wikistatus(self, ctx: discord.ApplicationContext):
        async with aiosqlite.connect("channels.db") as db:
            # Channel abfragen
            async with db.execute("SELECT channel_id FROM text_channels WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
                channel = self.bot.get_channel(row[0]) if row else None

            # Letzter Eintrag
            async with db.execute("SELECT value FROM metadata WHERE key = 'last_posted'") as cursor:
                row = await cursor.fetchone()
                last_posted = row[0] if row else "Keine Daten"

        embed = discord.Embed(
            title="📊 Wiki-Bot Status",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Channel", value=channel.mention if channel else "Kein Channel gesetzt", inline=False)
        embed.add_field(name="Letzter Beitrag", value=last_posted, inline=False)

        await ctx.respond(embed=embed, ephemeral=True)

    @slash_command(name="setwikichannel", description="Lege den Channel und das Wiki fest, das überwacht wird.")
    @discord.default_permissions(administrator=True)
    async def setwikichannel(
            self,
            ctx: discord.ApplicationContext,
            channel: discord.TextChannel,
            wiki: Option(str, "Welches Wiki?", choices=["Unknown Times", "Echo of War"])
    ):
        async with aiosqlite.connect("channels.db") as db:
            await db.execute(
                "INSERT OR REPLACE INTO text_channels (guild_id, channel_id, wiki_type) VALUES (?, ?, ?)",
                (ctx.guild.id, channel.id, wiki)
            )
            await db.commit()

        await ctx.respond(f"✅ Wiki-Update-Channel wurde auf {channel.mention} mit Wiki `{wiki}` gesetzt.",
                          ephemeral=True)

    @tasks.loop(minutes=1)
    async def check_feed(self):
        print("Feed wird überprüft...")

        async with aiosqlite.connect("channels.db") as db:
            async with db.execute("SELECT guild_id, channel_id, wiki_type FROM text_channels") as cursor:
                async for guild_id, channel_id, wiki_type in cursor:
                    feed_url = FEED_URLS.get(wiki_type, FEED_URLS["Unknown Times"])
                    feed = feedparser.parse(feed_url)

                    if not feed.entries:
                        print(f"[{wiki_type}] Keine Einträge.")
                        continue

                    latest = feed.entries[0]

                    async with db.execute("SELECT value FROM metadata WHERE key = ?",
                                          (f"last_posted_{guild_id}",)) as row_cursor:
                        row = await row_cursor.fetchone()
                        last_posted = row[0] if row else None

                    if last_posted == latest.id:
                        print(f"[{guild_id}] Eintrag schon gepostet.")
                        continue

                    await db.execute(
                        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                        (f"last_posted_{guild_id}", latest.id)
                    )
                    await db.commit()

                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        print(f"Guild {guild_id} nicht gefunden.")
                        continue

                    channel = guild.get_channel(channel_id)
                    if not channel:
                        print(f"Channel {channel_id} nicht gefunden.")
                        continue

                    try:
                        await channel.send(f"# 「📌」・NEUHEIT - [[{latest.title}]]({latest.link})")
                        print(f"✅ Gesendet an {channel.name} ({guild.name})")
                    except Exception as e:
                        print(f"Fehler beim Senden: {e}")

    @check_feed.before_loop
    async def before_check_feed(self):
        await self.bot.wait_until_ready()
        # Datenbank-Setup für 'metadata'-Tabelle (falls nicht vorhanden)
        async with aiosqlite.connect("channels.db") as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)"
            )
            await db.commit()

    @slash_command(name="wiki", description="Suche eine Seite im Wiki.")
    async def wiki(
            self,
            ctx: discord.ApplicationContext,
            *,
            titel: Option(str, "Seitentitel"),
            wiki: Option(str, "Welches Wiki?", choices=["Unknown Times", "Narutopedia", "Echo of War"])

    ):
        await ctx.defer()

        slug = titel.strip().replace(" ", "_")
        if wiki == "Unknown Times":
            base_url = "https://naruto-unknown-times.fandom.com/de/wiki/"
            file_path_base = "https://naruto-unknown-times.fandom.com/de/wiki/Special:FilePath/"
            logo = "https://naruto-unknown-times.fandom.com/de/wiki/Special:FilePath/NarutoUT_Logo.png"
        elif wiki == "Echo of War":
            base_url = "https://naruto-rp.fandom.com/de/wiki/"
            file_path_base = "https://naruto-rp.fandom.com/de/wiki/Special:FilePath/"
            logo = "https://naruto-rp.fandom.com/de/wiki/Special:FilePath/Echo_Logo.png"  # ggf. durch richtiges Logo ersetzen

        elif wiki == "Naruto":
            base_url = "https://naruto.fandom.com/wiki/"
            file_path_base = "https://naruto.fandom.com/wiki/Special:FilePath/"
            logo = "https://static.wikia.nocookie.net/naruto/images/6/60/Narutopedia_Wikia_Icon.png"

        wiki_url = f"{base_url}{slug}"
        image_url = None

        async with aiohttp.ClientSession() as session:
            async with session.get(wiki_url) as response:
                if response.status != 200:
                    embed = discord.Embed(
                        title="❌ Seite nicht gefunden",
                        description=f"Die Seite [{titel}]({wiki_url}) scheint im {wiki} Wiki nicht zu existieren.",
                        color=discord.Color.red()
                    )
                    return await ctx.respond(embed=embed)

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Unknown Times – portable infobox
                if wiki == "Unknown Times":
                    infobox = soup.find('aside', class_='portable-infobox')
                    if infobox:
                        img_tag = infobox.find('img')
                        if img_tag and img_tag.has_attr('src'):
                            image_url = img_tag['src']
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                                
                                
                elif wiki == "Echo of War":
                    infobox = soup.find('aside', class_='portable-infobox')
                    if infobox:
                        img_tag = infobox.find('img')
                        if img_tag and img_tag.has_attr('src'):
                            image_url = img_tag['src']
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                                
                          
                                
                         

                # Narutopedia – suche image name Feld
                elif wiki == "Narutopedia":
                    table = soup.find("table", class_="infobox")
                    if table:
                        rows = table.find_all("tr")
                        for row in rows:
                            if row.th and "image name" in row.th.text.lower():
                                if row.td:
                                    raw = row.td.text.strip().split(";")[0]
                                    filename = raw.replace(" ", "_")
                                    image_url = file_path_base + filename
                                    break

        # Embed erzeugen
        embed = discord.Embed(
            title=f"🔍 Wiki-Ergebnis: {titel}",
            url=wiki_url,
            description=f"Hier findest du die Seite im {wiki} Wiki.",
            color=discord.Color.orange()
        )
        if image_url:
            embed.set_image(url=image_url)

        embed.set_footer(text=f"Powered by {wiki}", icon_url=logo)
        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(WikiUpdates(bot))