import discord
from discord.ext import commands, tasks
from discord.commands import slash_command, Option
import aiosqlite

GUILD_ID = 824029270384312341
MEME_CHANNEL_ID = 1018300492448792646
TSUKOYUMI_CHANNEL_ID = 1245360929361625110

# Rollen-IDs
BUMP_TIERS = {
    40: 1375630857896853565,
    20: 1375630871184543754,
    10: 1252197789312618526
}

MEME_TIERS = {
    20: 1375630866612748371,
    10: 1375630874208637068,
    5: 1252197999699034172
}

TSUKOYUMI_TIERS = {
    20: 1375630877228535909,
    10: 1252199118772768799
}



class AchievementSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db.start()

    @tasks.loop(count=1)
    async def init_db(self):
        await self.bot.wait_until_ready()
        async with aiosqlite.connect("achievement.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS server (
                    guild_id INTEGER,
                    user_id INTEGER PRIMARY KEY,
                    username TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS achievements (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    bumps INTEGER DEFAULT 0,
                    memes INTEGER DEFAULT 0
                )
            """)
            await db.commit()

            guild = self.bot.get_guild(GUILD_ID)
            for member in guild.members:
                if not member.bot:
                    await self.add_user(member)

    async def add_user(self, member):
        async with aiosqlite.connect("achievement.db") as db:
            await db.execute("INSERT OR IGNORE INTO server (guild_id, user_id, username) VALUES (?, ?, ?)",
                             (GUILD_ID, member.id, member.name))
            await db.execute("INSERT OR IGNORE INTO achievements (user_id, username) VALUES (?, ?)",
                             (member.id, member.name))
            await db.commit()

    async def remove_user(self, user_id):
        async with aiosqlite.connect("achievement.db") as db:
            await db.execute("DELETE FROM server WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM achievements WHERE user_id = ?", (user_id,))
            await db.commit()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id == GUILD_ID and not member.bot:
            await self.add_user(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild.id == GUILD_ID:
            await self.remove_user(member.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.guild.id != 824029270384312341:
            return

        # Fibo Bot Bump-Bestätigung
        if message.author.id == 735147814878969968:
            if message.content.startswith("Thx for bumping our Server!") and message.mentions:
                bumper = message.mentions[0]
                await self.increment_achievement(bumper, "bumps", BUMP_TIERS)
            return

        # ✅ Nur Aktionen auf Zielserver
        if message.guild and message.guild.id == GUILD_ID:
            if message.channel.id == MEME_CHANNEL_ID:
                if message.attachments:
                    await self.increment_achievement(message.author, "memes", MEME_TIERS)
                    await message.add_reaction("😂")
                    await message.add_reaction("❤️")
                else:
                    await message.delete()
                    try:
                        await message.author.send("❌ Im Meme-Channel sind nur Memes erlaubt!")
                    except discord.Forbidden:
                        pass

            elif message.channel.id == TSUKOYUMI_CHANNEL_ID:
                await self.increment_achievement(message.author, "tsukoyumi", TSUKOYUMI_TIERS)
                emoji = discord.utils.get(message.guild.emojis, id=1084102345991917609)
                if emoji:
                    try:
                        await message.add_reaction(emoji)
                        print("✅ Reaktion hinzugefügt.")
                    except discord.HTTPException as e:
                        print(f"❌ Fehler beim Hinzufügen der Reaktion: {e}")
                else:
                    print("⚠️ Emoji mit dieser ID nicht gefunden.")

    async def increment_achievement(self, member, column, tier_dict, amount=1):
        async with aiosqlite.connect("achievement.db") as db:
            await db.execute(f"UPDATE achievements SET {column} = {column} + ? WHERE user_id = ?", (amount, member.id))
            await db.commit()

            cursor = await db.execute(f"SELECT {column} FROM achievements WHERE user_id = ?", (member.id,))
            row = await cursor.fetchone()
            value = row[0] if row else 0

        # Rollenverwaltung
        for required, role_id in tier_dict.items():
            role = member.guild.get_role(role_id)
            if value >= required and role and role not in member.roles:
                await member.add_roles(role)
                try:
                    await member.send(f"🏆 Du hast die Rolle **{role.name}** erhalten!")
                except discord.Forbidden:
                    pass

    @slash_command(name="stats", description="Zeigt deine Bump- und Meme-Erfolge")
    async def stats(self, ctx):
        if ctx.guild.id != GUILD_ID:
            return await ctx.respond("Dieser Befehl ist nur auf dem Zielserver verfügbar.", ephemeral=True)

        async with aiosqlite.connect("achievement.db") as db:
            row = await db.execute("SELECT bumps, memes, tsukoyumi FROM achievements WHERE user_id = ?",
                                   (ctx.author.id,))
            result = await row.fetchone()

        if not result:
            return await ctx.respond("Du hast noch keine Erfolge erzielt.", ephemeral=True)

        bumps, memes, tsukoyumi = result
        embed = discord.Embed(title="🏆 Deine Erfolge", color=discord.Color.gold())
        embed.add_field(name="Bumps", value=f"{bumps} / 40", inline=True)
        embed.add_field(name="Memes", value=f"{memes} / 20", inline=True)
        embed.add_field(name="Tsukuyomi", value=f"{tsukoyumi} / 20", inline=True)

        await ctx.respond(embed=embed)

    @slash_command(name="add_achieve", description="Vergebe manuell Bumps oder Memes")
    @commands.has_permissions(administrator=True)
    async def add_achievement(self,ctx,user: Option(discord.Member, "Wähle den Nutzer"),art: Option(str, "Art", choices=["bumps", "memes", "tsukoyumi"]),menge: Option(int, "Anzahl der hinzuzufügenden Punkte")):
        if ctx.guild.id != GUILD_ID:
            return await ctx.respond("Dieser Befehl ist nur auf dem Hauptserver verfügbar.", ephemeral=True)
        await ctx.defer(ephemeral=True)

        tier_dict = {
            "bumps": BUMP_TIERS,
            "memes": MEME_TIERS,
            "tsukoyumi": TSUKOYUMI_TIERS
        }.get(art)

        await self.increment_achievement(user, art, tier_dict, menge)
        await ctx.respond(f"✅ {menge} {art} für {user.mention} hinzugefügt.", ephemeral=True)



def setup(bot):
    bot.add_cog(AchievementSystem(bot))