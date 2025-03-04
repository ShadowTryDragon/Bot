import aiosqlite
import time
from discord.ext import commands

async def check_cooldown(ctx):
    """Überprüft, ob der User für einen Befehl einen Cooldown hat"""
    async with aiosqlite.connect("server_settings.db") as db:
        async with db.execute("SELECT seconds FROM cooldowns WHERE guild_id = ? AND command = ?",
                              (ctx.guild.id, ctx.command.name)) as cursor:
            result = await cursor.fetchone()
            cooldown_time = result[0] if result else None

    if cooldown_time is None:
        return True  # Kein Cooldown gesetzt

    async with aiosqlite.connect("server_settings.db") as db:
        async with db.execute("SELECT last_used FROM cooldown_tracker WHERE user_id = ? AND command = ?",
                              (ctx.author.id, ctx.command.name)) as cursor:
            last_used = await cursor.fetchone()

    if last_used:
        last_used_time = last_used[0]
        time_since_last_use = time.time() - last_used_time  # Zeitdifferenz berechnen

        if time_since_last_use < cooldown_time:
            remaining_time = cooldown_time - time_since_last_use
            raise commands.CommandOnCooldown(
                commands.Cooldown(rate=1, per=cooldown_time),
                retry_after=remaining_time,
                type=commands.BucketType.user
            )

    # Speichere den aktuellen Zeitstempel für den Befehl
    async with aiosqlite.connect("server_settings.db") as db:
        await db.execute("""
            INSERT INTO cooldown_tracker (user_id, command, last_used) 
            VALUES (?, ?, ?) 
            ON CONFLICT(user_id, command) DO UPDATE SET last_used = ?
        """, (ctx.author.id, ctx.command.name, time.time(), time.time()))
        await db.commit()

    return True  # Kein aktiver Cooldown
