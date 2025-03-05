import aiosqlite
import discord
from discord.commands import slash_command, Option
from discord.ext import commands


class CommandLock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.create_db())
        self.bot.before_invoke(self.before_invoke_check)  # ✅ Überprüft jeden Command vor der Ausführung!

    BLOCKED_COMMANDS = ["lockcommand", "unlockcommand", "lockallcommands", "resetlocks", "warn", "set_autrole",
                        "add_blacklist", "remove_blacklist", "allow_domain", "remove_domain", "ban", "set_cooldown",
                        "remove_cooldown", "set_welcome_embed", "set_leave_embed", "set_log_channel",
                        "set_global_cooldown", "clear_all_cooldowns", "clear_warns", "modifylevel", "reset-level",
                        "restore-level", "set_automod", "set_autorole", "set_warn_decay", "kick", "ban", "timeout"]

    async def create_db(self):
        """Erstellt die Datenbank für gesperrte Commands, falls sie nicht existiert."""
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS locked_commands (
                    guild_id INTEGER,
                    channel_id INTEGER,
                    command_name TEXT,
                    PRIMARY KEY (guild_id, channel_id, command_name)
                )
            """)
            await db.commit()

    async def before_invoke_check(self, ctx):
        """Blockiert gesperrte Commands vor der Ausführung."""
        if await self.is_command_locked(ctx.guild.id, ctx.channel.id, ctx.command.name):
            await ctx.respond(f"❌ Der Command `{ctx.command.name}` ist in diesem Channel gesperrt.", ephemeral=True)
            raise commands.CheckFailure  # Verhindert die Ausführung des Commands

    async def is_command_locked(self, guild_id: int, channel_id: int, command_name: str) -> bool:
        """Prüft, ob ein Command in einem Channel gesperrt ist."""
        async with aiosqlite.connect("server_settings.db") as db:
            async with db.execute("""
                SELECT 1 FROM locked_commands WHERE guild_id = ? AND channel_id = ? AND command_name = ?
            """, (guild_id, channel_id, command_name)) as cursor:
                return await cursor.fetchone() is not None

    async def check_command_block(self, ctx):
        """Checkt vor der Ausführung, ob der Command gesperrt ist."""
        if await self.is_command_locked(ctx.guild.id, ctx.channel.id, ctx.command.name):
            await ctx.respond(f"❌ Der Command `{ctx.command.name}` ist in diesem Channel gesperrt.", ephemeral=True)
            return False
        return True

    @slash_command(name="lockallcommands",
                   description="Sperrt alle Commands in einem Channel außer geschützte Commands.")
    @commands.has_permissions(administrator=True)
    async def lock_all_commands(
            self,
            ctx,
            channel: Option(discord.TextChannel, "In welchem Channel sollen alle Commands gesperrt werden?")
    ):
        """Sperrt alle Commands außer die blockierten in einem Channel."""
        all_commands = [cmd.name for cmd in self.bot.application_commands if cmd.name not in self.BLOCKED_COMMANDS]

        async with aiosqlite.connect("server_settings.db") as db:
            for command in all_commands:
                await db.execute("""
                        INSERT OR IGNORE INTO locked_commands (guild_id, channel_id, command_name)
                        VALUES (?, ?, ?)
                    """, (ctx.guild.id, channel.id, command))
            await db.commit()

        await ctx.respond(f"✅ Alle Commands außer System-Befehle wurden in {channel.mention} gesperrt.", ephemeral=True)

    @slash_command(name="resetlocks", description="Entsperrt alle gesperrten Commands auf dem Server (Admin only).")
    @commands.has_permissions(administrator=True)
    async def reset_locks(self, ctx):
        """Entsperrt alle gesperrten Commands auf dem Server."""
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("DELETE FROM locked_commands WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
            await ctx.respond(f"Der Channel wurde wieder freigegeben")

    @slash_command(name="lockcommand", description="Sperrt einen Befehl in einem bestimmten Channel (Admin only).")
    @commands.has_permissions(administrator=True)
    async def lock_command(
        self,
        ctx,
        command_name: Option(str, "Welchen Befehl willst du sperren?"),
        channel: Option(discord.TextChannel, "In welchem Channel soll er gesperrt werden?")
    ):
        """Sperrt einen Command in einem bestimmten Channel."""
        if command_name.lower() in self.BLOCKED_COMMANDS:
            await ctx.respond("❌ Dieser Command kann nicht gesperrt werden.", ephemeral=True)
            return

        if command_name.lower() not in [cmd.name for cmd in self.bot.application_commands]:
            await ctx.respond("❌ Dieser Command existiert nicht!", ephemeral=True)
            return

        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("""
                INSERT OR IGNORE INTO locked_commands (guild_id, channel_id, command_name)
                VALUES (?, ?, ?)
            """, (ctx.guild.id, channel.id, command_name))
            await db.commit()

        await ctx.respond(f"✅ Der Command `{command_name}` wurde in {channel.mention} gesperrt.", ephemeral=True)

    @slash_command(name="unlockcommand", description="Entsperrt einen Befehl in einem bestimmten Channel (Admin only).")
    @commands.has_permissions(administrator=True)
    async def unlock_command(
        self,
        ctx,
        command_name: Option(str, "Welchen Befehl willst du entsperren?"),
        channel: Option(discord.TextChannel, "In welchem Channel soll er entsperrt werden?")
    ):
        """Entsperrt einen Command in einem bestimmten Channel."""
        async with aiosqlite.connect("server_settings.db") as db:
            await db.execute("""
                DELETE FROM locked_commands WHERE guild_id = ? AND channel_id = ? AND command_name = ?
            """, (ctx.guild.id, channel.id, command_name))
            await db.commit()

        await ctx.respond(f"✅ Der Command `{command_name}` ist in {channel.mention} wieder erlaubt.", ephemeral=True)



    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Verhindert, dass `CheckFailure`-Fehler in der Konsole erscheinen."""
        if isinstance(error, commands.CheckFailure):
            return  # ✅ Fehler wird ignoriert & nicht geloggt!
        else:
            raise error  # Andere Fehler normal anzeigen

def setup(bot):
    bot.add_cog(CommandLock(bot))
