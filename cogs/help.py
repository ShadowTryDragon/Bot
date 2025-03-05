import discord
from discord.ext import commands
from discord.commands import slash_command


class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="help", description="Zeigt eine Liste aller verfügbaren Befehle.")
    async def help(self, ctx):
        """Erstellt eine Embed-Liste aller verfügbaren Befehle nach Kategorie sortiert."""

        embed = discord.Embed(title="📜 Bot-Hilfe", description="Hier sind alle verfügbaren Befehle:",
                              color=discord.Color.blue())
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        # 📌 Befehle nach Kategorie sortieren
        command_dict = {}  # Kategorie: [Befehle]

        for command in self.bot.application_commands:
            if isinstance(command, discord.SlashCommand):
                category = command.cog.qualified_name if command.cog else "Allgemein"
                if category not in command_dict:
                    command_dict[category] = []
                command_dict[category].append(f"**/{command.name}** - {command.description}")

        # 📌 Befehle zur Embed-Nachricht hinzufügen, in max. 1024 Zeichen-Blöcken
        for category, commands_list in sorted(command_dict.items()):
            command_text = "\n".join(commands_list)

            # Falls die Kategorie mehr als 1024 Zeichen hat, aufteilen
            while len(command_text) > 1024:
                split_index = command_text[:1024].rfind("\n")  # Letzter Zeilenumbruch vor 1024 Zeichen
                embed.add_field(name=f"📂 {category}", value=command_text[:split_index], inline=False)
                command_text = command_text[split_index:].strip()  # Restliche Befehle weitermachen

            # Letztes (oder einziges) Feld hinzufügen
            if command_text:
                embed.add_field(name=f"📂 {category}", value=command_text, inline=False)

        embed.set_footer(text="Nutze /help [Befehl], um mehr Informationen zu einem Befehl zu erhalten.")

        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(HelpCommand(bot))
