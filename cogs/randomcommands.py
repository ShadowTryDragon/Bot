
import random
from io import BytesIO
from PIL import Image, ImageDraw
import discord
from discord.commands import slash_command, Option
from discord.ext import commands

from cooldown_handler import check_cooldown


class RandomChoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="random", description="Wählt zufällig eine Option aus deinen Eingaben")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def random_choice(self,ctx,option1: Option(str, "Erste Option"),option2: Option(str, "Zweite Option", default=None),option3: Option(str, "Dritte Option", default=None),option4: Option(str, "Vierte Option", default=None), option5: Option(str, "Fünfte Option", default=None)):
        # Alle nicht-leeren Optionen in eine Liste packen
        options = [option for option in [option1, option2, option3, option4, option5] if option]

        # Zufällige Auswahl
        choice = random.choice(options)

        # Antwort an den User senden
        await ctx.respond(f"🎲 Ich habe mich für **{choice}** entschieden!")

    @slash_command(name="ask", description="Stelle eine Frage und erhalte eine zufällige Antwort!")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def ask(self,ctx,frage: Option(str, "Stelle deine Frage")):
        """Gibt eine zufällige Antwort auf eine Frage des Users"""
        antworten = [
            "Ja! ✅",
            "Nein! ❌",
            "Vielleicht... 🤔",
            "Frag später nochmal! ⏳",
            "Definitiv! 🎉",
            "Auf keinen Fall! 🚫",
            "Ich bin mir nicht sicher... 😕",
            "Die Zeichen stehen gut! 🍀",
            "Besser nicht... ⚠️",
            "Das bleibt ein Geheimnis! 🤫"
        ]

        # Zufällige Antwort auswählen
        antwort = random.choice(antworten)

        # Antwort senden
        await ctx.respond(f"❓ **Frage:** {frage}\n🎱 **Antwort:** {antwort}")


    async def combine_avatars(self, user1: discord.Member, user2: discord.Member):
        """Erstellt ein gemeinsames Bild aus den Profilbildern der beiden User."""
        avatar1 = Image.open(BytesIO(await user1.display_avatar.read())).resize((100, 100))
        avatar2 = Image.open(BytesIO(await user2.display_avatar.read())).resize((100, 100))

        # Neues Bild erstellen (200x100) mit weißem Hintergrund
        combined = Image.new("RGBA", (220, 110), (255, 255, 255, 0))

        # Abgerundete Ränder für Avatare
        mask = Image.new("L", (100, 100), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 100, 100), fill=255)

        avatar1.putalpha(mask)
        avatar2.putalpha(mask)

        # Avatare nebeneinander platzieren
        combined.paste(avatar1, (10, 5), avatar1)
        combined.paste(avatar2, (110, 5), avatar2)

        # Bild speichern und zurückgeben
        image_bytes = BytesIO()
        combined.save(image_bytes, format="PNG")
        image_bytes.seek(0)
        return image_bytes


    @slash_command(name="ship", description="Shippe dich mit jemandem und finde eure Kompatibilität heraus!")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def ship(self,ctx,user1: Option(discord.Member, "Wähle die erste Person"),user2: Option(discord.Member, "Wähle die zweite Person (oder lass es leer für dich selbst)", required=False)):
        """Shippt zwei User und gibt eine zufällige Kompatibilitätsbewertung aus."""
        user2 = user2 or ctx.author  # Falls user2 nicht angegeben ist, wird der User selbst genommen

        # Selbstliebe-Special
        if user1 == user2:
            embed = discord.Embed(
                title="💖 Selbstliebe! 💖",
                description=f"{user1.mention}, du brauchst niemand anderen! Selbstliebe ist die beste Liebe. 💕✨",
                color=discord.Color.magenta()
            )
            embed.set_thumbnail(url=user1.display_avatar.url)
            await ctx.respond(embed=embed)
            return

        # Zufällige Kompatibilitätsbewertung (0-100%)
        score = random.randint(0, 100)

        # Fortschrittsbalken (10 Blöcke)
        filled_blocks = round(score / 10)
        progress_bar = "█" * filled_blocks + "░" * (10 - filled_blocks)

        # Kompatibilitäts-Nachricht basierend auf dem Score
        if score < 30:
            message = "💔 Das wird wohl nichts... 😢"
            color = discord.Color.red()
        elif score < 60:
            message = "🤔 Könnte klappen, wenn ihr euch Mühe gebt! 💕"
            color = discord.Color.orange()
        elif score < 85:
            message = "💖 Ihr seid ein tolles Paar! 😍"
            color = discord.Color.green()
        else:
            message = "💞 Perfekte Seelenverwandte! 💍💘"
            color = discord.Color.gold()

        # Embed erstellen
        embed = discord.Embed(
            title="💘 Ship-Ergebnis 💘",
            description=f"{user1.mention} ❤️ {user2.mention}\n\n"
                        f"💑 **Kompatibilität:** **{score}%**\n"
                        f"`{progress_bar}`\n\n"
                        f"{message}",
            color=color
        )

        # Kombiniertes Avatar-Bild generieren
        image_bytes = await self.combine_avatars(user1, user2)
        file = discord.File(image_bytes, filename="ship.png")
        embed.set_image(url="attachment://ship.png")

        # Nachricht senden
        await ctx.respond(embed=embed, file=file)

    @slash_command(name="roulette", description="Spiele russisches Roulette und teste dein Glück! 💀")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def roulette(self,ctx,mode: Option(str, "Wähle den Modus", choices=["6-Schuss", "12-Schuss", "1-Schuss"], default="6-Schuss")):
        """Simuliert russisches Roulette mit verschiedenen Chancen."""
        if mode == "6-Schuss":
            chance = 1 / 6  # 16,67% Verlustchance
        elif mode == "12-Schuss":
            chance = 1 / 12  # 8,33% Verlustchance
        else:
            chance = 1 / 1  # 100% Verlustchance (Spaßmodus!)

        # Zufallsgenerator entscheidet
        if random.random() < chance:
            embed = discord.Embed(
                title="💥 *BOOM!* 💥",
                description=f"Oh nein, {ctx.author.mention} hat verloren! 😵",
                color=discord.Color.red()
            )
            embed.set_image(url="https://tenor.com/de/view/finger-gun-barney-himym-nph-neil-patrick-harris-gif-4524247")  # Lustige Explosion
        else:
            embed = discord.Embed(
                title="🔫 *Klick... nichts passiert!*",
                description=f"Glück gehabt, {ctx.author.mention}! 🎉 Du hast überlebt! 😎",
                color=discord.Color.green()
            )
            embed.set_image(url="https://tenor.com/de/view/finger-gun-barney-himym-nph-neil-patrick-harris-gif-4524247")  # Spannende Szene

        await ctx.respond(embed=embed)





def setup(bot):
    bot.add_cog(RandomChoice(bot))
