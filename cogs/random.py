import discord
import random
from discord.commands import slash_command, Option
from discord.ext import commands

class RandomChoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="random", description="Wählt zufällig eine Option aus deinen Eingaben")
    async def random_choice(
        self,
        ctx,
        option1: Option(str, "Erste Option"),
        option2: Option(str, "Zweite Option", default=None),
        option3: Option(str, "Dritte Option", default=None),
        option4: Option(str, "Vierte Option", default=None),
        option5: Option(str, "Fünfte Option", default=None)
    ):
        # Alle nicht-leeren Optionen in eine Liste packen
        options = [option for option in [option1, option2, option3, option4, option5] if option]

        # Zufällige Auswahl
        choice = random.choice(options)

        # Antwort an den User senden
        await ctx.respond(f"🎲 Ich habe mich für **{choice}** entschieden!")

def setup(bot):
    bot.add_cog(RandomChoice(bot))
