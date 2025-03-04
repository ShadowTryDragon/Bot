from discord.ext import commands
from discord.commands import slash_command, Option
import discord
import aiosqlite
import random


class LevelSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.create_db())

    async def create_db(self):
        """Erstellt die Datenbank und Tabelle, falls sie nicht existiert."""
        async with aiosqlite.connect("levels.db") as db:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1
                )"""
            )
            await db.commit()

    async def get_user(self, user_id: int):
        """Holt die XP und das Level eines Benutzers aus der Datenbank."""
        async with aiosqlite.connect("levels.db") as db:
            async with db.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,)) as cursor:
                return await cursor.fetchone()

    async def add_xp(self, user_id: int, xp_to_add: int, message: discord.Message = None):
        """Fügt XP hinzu und prüft auf Level-Up."""
        async with aiosqlite.connect("levels.db") as db:
            user = await self.get_user(user_id)
            xp, level = user if user else (0, 1)
            xp += xp_to_add
            new_level = level

            leveled_up = False
            while xp >= 100 * new_level:
                xp -= 100 * new_level
                new_level += 1
                leveled_up = True  # ✅ Level-Up erkannt!

            await db.execute("INSERT OR REPLACE INTO users (user_id, xp, level) VALUES (?, ?, ?)",
                             (user_id, xp, new_level))
            await db.commit()

        if leveled_up and message:  # ✅ Level-Up Nachricht nur senden, wenn `message` vorhanden ist
            embed = discord.Embed(
                title="🎉 Level Up!",
                description=f"Herzlichen Glückwunsch {message.author.mention}! 🎉\n"
                            f"Du hast Level **{new_level}** erreicht! 🚀",
                color=discord.Color.green()
            )
            await message.channel.send(embed=embed)  # ✅ Level-Up Nachricht senden

    @commands.Cog.listener()
    async def on_message(self, message):
        """Wird bei jeder gesendeten Nachricht ausgelöst (ohne Bots)."""
        if message.author.bot:
            return

        xp_to_add = random.randint(5, 15)  # Zufällige XP zwischen 5 und 15
        await self.add_xp(message.author.id, xp_to_add)

    @slash_command(name="level", description="Zeigt dein detailliertes Level-Profil an.")
    async def level(self, ctx, user: Option(discord.Member, "Wähle einen Benutzer", required=False) = None):
        """Zeigt das Level, XP und den Rang eines Benutzers an."""
        user = user or ctx.author
        user_data = await self.get_user(user.id)

        if user_data is None:
            await ctx.respond(f"{user.mention} hat noch keine XP gesammelt!", ephemeral=True)
            return

        xp, level = user_data
        next_level_xp = 100 * level  # XP-Anforderung für nächstes Level
        xp_needed = next_level_xp - xp  # Fehlende XP für Level-Up
        progress = int((xp / next_level_xp) * 10)  # Fortschrittsbalken (10 Blöcke)
        progress_bar = "█" * progress + "░" * (10 - progress)  # Optische Darstellung

        # Rangberechnung (Global)
        async with aiosqlite.connect("levels.db") as db:
            async with db.execute("SELECT COUNT(*) FROM users WHERE level > ? OR (level = ? AND xp > ?)",
                                  (level, level, xp)) as cursor:
                global_rank = (await cursor.fetchone())[0] + 1  # Aktuelle Position

        # Rangberechnung (Server)
        member_ids = [member.id for member in ctx.guild.members if not member.bot]
        async with aiosqlite.connect("levels.db") as db:
            async with db.execute(
                    f"SELECT COUNT(*) FROM users WHERE (level > ? OR (level = ? AND xp > ?)) AND user_id IN ({','.join(['?'] * len(member_ids))})",
                    (level, level, xp, *member_ids)) as cursor:
                server_rank = (await cursor.fetchone())[0] + 1

        # Embed-Erstellung
        embed = discord.Embed(title=f"🎖 Level-Profil von {user.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        embed.add_field(name="📊 Level", value=f"{level}", inline=True)
        embed.add_field(name="🔹 XP", value=f"{xp}/{next_level_xp} XP", inline=True)
        embed.add_field(name="📈 Fortschritt", value=f"`{progress_bar}`", inline=False)
        embed.add_field(name="⬆️ XP bis zum nächsten Level", value=f"{xp_needed} XP", inline=True)
        embed.add_field(name="🌍 Globaler Rang", value=f"#{global_rank}", inline=True)
        embed.add_field(name="🏆 Server Rang", value=f"#{server_rank}", inline=True)

        await ctx.respond(embed=embed)

    @slash_command(name="leaderboard", description="Zeigt die besten Spieler global oder nur für diesen Server.")
    async def leaderboard(self, ctx, server_only: Option(bool, "Nur Mitglieder dieses Servers anzeigen?", required=False,default=False)):
        """Zeigt die Top 10 Benutzer mit dem höchsten Level an. Optional nur für den aktuellen Server."""
        async with aiosqlite.connect("levels.db") as db:
            if server_only:
                # Holen aller Benutzer aus dem Server
                member_ids = [member.id for member in ctx.guild.members if not member.bot]
                query = f"SELECT user_id, level, xp FROM users WHERE user_id IN ({','.join(['?'] * len(member_ids))}) ORDER BY level DESC, xp DESC LIMIT 10"
                params = member_ids
            else:
                # Globales Leaderboard
                query = "SELECT user_id, level, xp FROM users ORDER BY level DESC, xp DESC LIMIT 10"
                params = []

            async with db.execute(query, params) as cursor:
                top_users = await cursor.fetchall()

        if not top_users:
            await ctx.respond("Es gibt noch keine Einträge im Leaderboard!", ephemeral=True)
            return

        leaderboard_text = "**🏆 Leaderboard - Top 10 Spieler 🏆**\n\n"
        for rank, (user_id, level, xp) in enumerate(top_users, start=1):
            user = self.bot.get_user(user_id) or f"Unbekannter Benutzer ({user_id})"
            leaderboard_text += f"**{rank}.** {user} - Level {level} ({xp} XP)\n"

        title = "🏆 Server Leaderboard" if server_only else "🌍 Globales Leaderboard"
        embed = discord.Embed(title=title, description=leaderboard_text, color=discord.Color.gold())

        await ctx.respond(embed=embed)

    @slash_command(name="modifylevel", description="Füge einem Benutzer XP hinzu oder entferne sie (Admin only).")
    @commands.has_permissions(administrator=True)
    async def modifylevel(self, ctx, user: discord.Member, xp_amount: int):
        """Ermöglicht Administratoren, XP hinzuzufügen oder zu entfernen."""
        async with aiosqlite.connect("levels.db") as db:
            user_data = await self.get_user(user.id)

            if user_data is None:
                await ctx.respond(f"❌ {user.mention} ist noch nicht im Level-System registriert.", ephemeral=True)
                return

            current_xp, level = user_data
            new_xp = max(0, current_xp + xp_amount)  # Verhindert negative XP

            # Level-Update prüfen
            new_level = level
            leveled_up = False

            if xp_amount > 0:  # XP hinzufügen
                while new_xp >= 100 * new_level:
                    new_xp -= 100 * new_level
                    new_level += 1
                    leveled_up = True
            else:  # XP entfernen (kein Downgrade unter Level 1)
                while new_xp < 0 and new_level > 1:
                    new_level -= 1
                    new_xp += 100 * new_level

            # Datenbank aktualisieren
            await db.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (new_xp, new_level, user.id))
            await db.commit()

        # Antwort senden
        xp_action = "erhalten" if xp_amount > 0 else "verloren"
        embed = discord.Embed(
            title="🔧 XP-Modifikation",
            description=f"{user.mention} hat **{abs(xp_amount)} XP** {xp_action}.",
            color=discord.Color.green() if xp_amount > 0 else discord.Color.red()
        )
        embed.add_field(name="📊 Neues Level", value=f"**{new_level}**", inline=True)
        embed.add_field(name="🔹 Neue XP", value=f"**{new_xp}** XP", inline=True)

        await ctx.respond(embed=embed)

        # Falls ein Level-Up passiert, Level-Up-Nachricht senden
        if leveled_up:
            level_embed = discord.Embed(
                title="🎉 Level Up!",
                description=f"Herzlichen Glückwunsch {user.mention}! 🎉\nDu hast Level **{new_level}** erreicht! 🚀",
                color=discord.Color.gold()
            )
            await ctx.channel.send(embed=level_embed)

    @slash_command(name="reset-level",description="Setzt das Level eines Benutzers oder aller Spieler zurück (Admin only).")
    @commands.has_permissions(administrator=True)
    async def reset_level(self, ctx,user: Option(discord.Member, "Wähle einen Benutzer (oder leer lassen für globalen Reset)",required=False),global_reset: Option(bool, "Alle Benutzer zurücksetzen? (Achtung: nicht rückgängig!)",required=False, default=False)):
        """Setzt das Level eines Benutzers oder aller Spieler zurück, mit Backup & Bestätigung für globalen Reset."""
        async with aiosqlite.connect("levels.db") as db:
            # Backup-Tabelle erstellen, falls nicht vorhanden
            await db.execute("""
                CREATE TABLE IF NOT EXISTS backup_users (
                    user_id INTEGER PRIMARY KEY,
                    xp INTEGER,
                    level INTEGER
                )
            """)

            if global_reset:
                # Schritt 1: Backup speichern
                await db.execute("DELETE FROM backup_users")  # Altes Backup löschen
                await db.execute("INSERT INTO backup_users SELECT * FROM users")  # Backup erstellen
                await db.commit()
                # Schritt 2: Bestätigung einholen
                confirm_embed = discord.Embed(
                    title="⚠ Bestätigung erforderlich!",
                    description="❗ Bist du sicher, dass du **alle Level-Daten** zurücksetzen möchtest?\n"
                                "Diese Aktion kann nicht rückgängig gemacht werden!\n\n"
                                "✅ **Zum Bestätigen:** Klicke auf ✅\n"
                                "❌ **Zum Abbrechen:** Klicke auf ❌",
                    color=discord.Color.red()
                )
                confirmation_message = await ctx.respond(embed=confirm_embed)
                await confirmation_message.add_reaction("✅")
                await confirmation_message.add_reaction("❌")
                def check(reaction, user):
                    return user == ctx.author and str(reaction.emoji) in ["✅", "❌"]

                try:
                    reaction, _ = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
                    if str(reaction.emoji) == "✅":
                        await db.execute("DELETE FROM users")  # Alle Daten löschen
                        await db.commit()
                        await ctx.send("🚨 **Alle Spieler wurden zurückgesetzt!** Backup wurde gespeichert.",
                                       delete_after=5)
                    else:
                        await ctx.send("❌ Reset abgebrochen.", delete_after=5)
                except TimeoutError:
                    await ctx.send("⏳ Zeit abgelaufen, Reset abgebrochen.", delete_after=5)

            elif user:
                # Backup für einen bestimmten Benutzer erstellen
                await db.execute("INSERT OR REPLACE INTO backup_users SELECT * FROM users WHERE user_id = ?",
                                 (user.id,))
                await db.execute("DELETE FROM users WHERE user_id = ?", (user.id,))
                await db.commit()
                await ctx.respond(f"✅ {user.mention} wurde zurückgesetzt! Backup wurde gespeichert.", ephemeral=True)

            else:
                await ctx.respond("❌ Bitte gib entweder einen Benutzer an oder setze `global_reset` auf `True`.",
                                  ephemeral=True)


    @slash_command(name="restore-level",description="Stellt das Level eines Benutzers aus dem Backup wieder her (Admin only).")
    @commands.has_permissions(administrator=True)
    async def restore_level(self, ctx, user: Option(discord.Member, "Wähle einen Benutzer für die Wiederherstellung")):
        """Stellt die XP und das Level eines Benutzers aus dem Backup wieder her (nur Admins)."""
        async with aiosqlite.connect("levels.db") as db:
            async with db.execute("SELECT xp, level FROM backup_users WHERE user_id = ?", (user.id,)) as cursor:
                backup_data = await cursor.fetchone()
                if backup_data is None:
                    await ctx.respond(f"❌ Kein Backup für {user.mention} gefunden!", ephemeral=True)
                    return
                xp, level = backup_data
                # Wiederherstellen der Daten
                await db.execute("INSERT OR REPLACE INTO users (user_id, xp, level) VALUES (?, ?, ?)",
                                 (user.id, xp, level))
                await db.commit()
                await ctx.respond(f"✅ {user.mention} wurde auf Level {level} mit {xp} XP wiederhergestellt!",
                                  ephemeral=True)


def setup(bot):
    bot.add_cog(LevelSystem(bot))