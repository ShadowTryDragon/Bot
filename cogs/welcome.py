import discord
from discord.ext import commands
from discord.commands import slash_command, Option
import aiosqlite

class WelcomeSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def replace_placeholders(self, text, member):
        text = text.replace("{@user}", member.mention)
        text = text.replace("{@channel}", f"#{member.guild.system_channel.name}" if member.guild.system_channel else "#unbekannt")
        text = text.replace("{@server}", member.guild.name)
        count = sum(1 for m in member.guild.members if not m.bot)
        return text.replace("{count}", str(count))

    async def get_welcome_settings(self, guild_id):
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS welcome_settings (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    header TEXT NOT NULL,
                    content TEXT NOT NULL,
                    image TEXT,
                    footer TEXT,
                    color TEXT
                )
            """)
            await db.commit()
            cursor = await db.execute("SELECT * FROM welcome_settings WHERE guild_id = ?", (guild_id,))
            return await cursor.fetchone()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        settings = await self.get_welcome_settings(member.guild.id)
        if not settings:
            return

        channel = member.guild.get_channel(settings[1])
        if not channel:
            return

        header, content, image, footer, color = settings[2], settings[3], settings[4], settings[5], settings[6]
        header = await self.replace_placeholders(header, member)
        content = await self.replace_placeholders(content, member)

        color_value = discord.Color(int(color.replace("#", ""), 16)) if color else discord.Color.blue()
        embed = discord.Embed(title=header, description=content, color=color_value)

        if image:
            embed.set_image(url=image)
        if footer:
            embed.set_footer(text=footer)

        await channel.send(embed=embed)

    @slash_command(name="setwelcome", description="Setzt die Willkommensnachricht.")
    @commands.has_permissions(administrator=True)
    async def setwelcome(
        self,
        ctx,
        channel: Option(discord.TextChannel, "Channel für Willkommensnachricht"),
        header: Option(str, "Embed-Titel (Pflicht)"),
        content: Option(str, "Inhalt (Pflicht)"),
        image: Option(str, "Bild/GIF-URL", required=False),
        footer: Option(str, "Footer-Text", required=False),
        color: Option(str, "Hex-Farbe z.B. #00ABFF", required=False)
    ):
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("""
                INSERT OR REPLACE INTO welcome_settings (guild_id, channel_id, header, content, image, footer, color)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ctx.guild.id, channel.id, header, content, image, footer, color))
            await db.commit()

        await ctx.respond("✅ Willkommensnachricht wurde gespeichert!", ephemeral=True)

def setup(bot):
    bot.add_cog(WelcomeSystem(bot))