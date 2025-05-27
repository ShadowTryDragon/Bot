import discord
from discord.ext import commands
from discord.commands import slash_command


class HelpDropdown(discord.ui.Select):
    """Dropdown-Menü für die Auswahl einer Befehlskategorie."""

    def __init__(self, bot, command_dict):
        self.bot = bot
        self.command_dict = command_dict

        options = [
            discord.SelectOption(label=category, description=f"Zeigt Befehle für {category}.")
            for category in sorted(command_dict.keys())
        ]

        super().__init__(
            placeholder="Wähle eine Kategorie...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """Reagiert auf die Auswahl einer Kategorie im Dropdown-Menü."""
        category = self.values[0]
        commands_list = self.command_dict[category]

        embed = discord.Embed(
            title=f"📂 {category} - Befehle",
            description="Hier sind alle Befehle für diese Kategorie:",
            color=discord.Color.green()
        )

        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        # 🔧 Lange Liste aufteilen in mehrere Felder
        chunk = ""
        for command in commands_list:
            if len(chunk) + len(command) + 1 > 1024:
                embed.add_field(name="Befehle:", value=chunk, inline=False)
                chunk = ""
            chunk += command + "\n"
        if chunk:
            embed.add_field(name="Befehle:", value=chunk, inline=False)

        embed.set_footer(text="Nutze /help [Befehl], um mehr Informationen zu einem Befehl zu erhalten.")

        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):
    """View für das Help-Dropdown-Menü."""

    def __init__(self, bot, command_dict):
        super().__init__(timeout=None)
        self.add_item(HelpDropdown(bot, command_dict))


class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="help", description="Zeigt eine Liste aller verfügbaren Befehle.")
    async def help(self, ctx):
        """Erstellt eine Embed-Liste aller verfügbaren Befehle nach Kategorie sortiert (mit Dropdown)."""

        command_dict = {}  # Kategorie: [Befehle]

        for command in self.bot.application_commands:
            if isinstance(command, discord.SlashCommand):
                category = command.cog.qualified_name if command.cog else "Allgemein"
                if category not in command_dict:
                    command_dict[category] = []
                command_dict[category].append(f"**/{command.name}** - {command.description}")

        embed = discord.Embed(
            title="📜 Bot-Hilfe",
            description="Wähle eine Kategorie aus dem Dropdown-Menü, um Befehle anzuzeigen.",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        await ctx.respond(embed=embed, view=HelpView(self.bot, command_dict))


def setup(bot):
    bot.add_cog(HelpCommand(bot))
