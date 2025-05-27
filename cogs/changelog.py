import aiosqlite
import discord
from discord.ext import commands


class ServerChangelog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_audit_log_entry(self, guild, action):
        """Holt den letzten Audit-Log-Eintrag für eine bestimmte Aktion."""
        async for entry in guild.audit_logs(limit=1, action=action):
            return entry  # Gibt den neuesten Eintrag zurück
        return None  # Falls nichts gefunden wurde

    async def log_action(self, guild, action, details, audit_action=None):
        async with aiosqlite.connect("server_settings.db") as db:
            async with db.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (guild.id,)) as cursor:
                log_channel_id = (await cursor.fetchone() or [None])[0]

        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                actor = "Unbekannt"

                if audit_action:
                    entry = await self.get_audit_log_entry(guild, audit_action)
                    if entry and entry.user:
                        actor = entry.user.mention  # Wer die Änderung durchgeführt hat

                embed = discord.Embed(
                    title=action,
                    description=f"{details}\n\n👤 **Geändert von:** {actor}",
                    color=discord.Color.red()
                )
                embed.set_footer(text="Automatische Moderation")
                await log_channel.send(embed=embed)

    ### --- 📌 CHANNEL-ÄNDERUNGEN --- ###
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self.log_action(channel.guild, "📢 Neuer Channel erstellt",
                              f"**{channel.name}** (ID: {channel.id})",
                              discord.AuditLogAction.channel_create)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self.log_action(channel.guild, "❌ Channel gelöscht",
                              f"**{channel.name}** (ID: {channel.id})",
                              discord.AuditLogAction.channel_delete)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        changes = []

        if before.name != after.name:
            changes.append(f"✏ **Name geändert:** `{before.name}` → `{after.name}`")

        if before.category != after.category:
            changes.append(f"📂 **Kategorie geändert:** `{before.category}` → `{after.category}`")

        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            if before.topic != after.topic:
                changes.append(f"📝 **Thema geändert:** `{before.topic}` → `{after.topic}`")

        if before.nsfw != after.nsfw:
            status = "aktiviert" if after.nsfw else "deaktiviert"
            changes.append(f"🔞 **NSFW geändert:** `{status}`")
            
            if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
                if before.slowmode_delay != after.slowmode_delay:
                    changes.append(f"🐌 **Slowmode geändert:** `{before.slowmode_delay} Sek.` → `{after.slowmode_delay} Sek.`")




        if changes:
            details = "\n".join(changes)
            await self.log_action(
                before.guild, "⚙ Kanal geändert", details, discord.AuditLogAction.channel_update
            )

    ### --- 🎭 ROLLEN-ÄNDERUNGEN --- ###
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self.log_action(role.guild, "🆕 Neue Rolle erstellt",
                              f"**{role.name}** (ID: {role.id})",
                              discord.AuditLogAction.role_create)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self.log_action(role.guild, "❌ Rolle gelöscht",
                              f"**{role.name}** (ID: {role.id})",
                              discord.AuditLogAction.role_delete)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if before.name != after.name:
            await self.log_action(before.guild, "✏ Rollen-Umbenennung",
                                  f"**{before.name}** ➜ **{after.name}**",
                                  discord.AuditLogAction.role_update)

        if before.permissions != after.permissions:
            await self.log_action(before.guild, "⚠ Rollen-Permissions geändert",
                                  f"**{after.name}** hat geänderte Berechtigungen!",
                                  discord.AuditLogAction.role_update)

    ### --- ⚙ SERVER-ÄNDERUNGEN --- ###
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        if before.name != after.name:
            await self.log_action(before, "🔄 Servername geändert",
                                  f"**{before.name}** ➜ **{after.name}**",
                                  discord.AuditLogAction.guild_update)

        if before.icon != after.icon:
            await self.log_action(before, "🖼 Server-Icon geändert",
                                  "Das Server-Icon wurde aktualisiert!",
                                  discord.AuditLogAction.guild_update)

        if before.owner != after.owner:
            await self.log_action(before, "👑 Serverbesitzer geändert",
                                  f"Neuer Besitzer: {after.owner.mention}",
                                  discord.AuditLogAction.guild_update)


   ### -- Änderungen Emotes und Sticker --- ###
@commands.Cog.listener()
async def on_guild_emojis_update(self, guild, before, after):
    before_emojis = {emoji.id: emoji for emoji in before}
    after_emojis = {emoji.id: emoji for emoji in after}

    changes = []

    # 1️⃣ Neue Emojis erkennen
    new_emojis = [emoji for emoji in after if emoji.id not in before_emojis]
    for emoji in new_emojis:
        changes.append(f"➕ Neues Emoji: {emoji} (`:{emoji.name}:`)")

    # 2️⃣ Gelöschte Emojis erkennen
    removed_emojis = [emoji for emoji in before if emoji.id not in after_emojis]
    for emoji in removed_emojis:
        changes.append(f"❌ Gelöschtes Emoji: `{emoji.name}`")

    # 3️⃣ Umbenannte Emojis erkennen
    for emoji_id, emoji in after_emojis.items():
        if emoji_id in before_emojis and emoji.name != before_emojis[emoji_id].name:
            changes.append(f"✏ Emoji umbenannt: `{before_emojis[emoji_id].name}` → `{emoji.name}`")

    if changes:
        details = "\n".join(changes)
        await self.log_action(guild, "😃 Emoji geändert", details, discord.AuditLogAction.emoji_update)


@commands.Cog.listener()
async def on_guild_stickers_update(self, guild, before, after):
    before_stickers = {sticker.id: sticker for sticker in before}
    after_stickers = {sticker.id: sticker for sticker in after}

    changes = []

    # 1️⃣ Neue Sticker erkennen
    new_stickers = [sticker for sticker in after if sticker.id not in before_stickers]
    for sticker in new_stickers:
        changes.append(f"➕ Neuer Sticker: `{sticker.name}`")

    # 2️⃣ Gelöschte Sticker erkennen
    removed_stickers = [sticker for sticker in before if sticker.id not in after_stickers]
    for sticker in removed_stickers:
        changes.append(f"❌ Gelöschter Sticker: `{sticker.name}`")

    # 3️⃣ Bearbeitete Sticker erkennen
    for sticker_id, sticker in after_stickers.items():
        if sticker_id in before_stickers:
            old_sticker = before_stickers[sticker_id]
            if sticker.name != old_sticker.name:
                changes.append(f"✏ Sticker umbenannt: `{old_sticker.name}` → `{sticker.name}`")

    if changes:
        details = "\n".join(changes)
        await self.log_action(guild, "🎭 Sticker geändert", details, discord.AuditLogAction.sticker_update)


def setup(bot):
    bot.add_cog(ServerChangelog(bot))





