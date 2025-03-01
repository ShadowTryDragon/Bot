import discord
import asyncio
from discord.ext import commands
from discord.ui import View, Button, Select


class TicketView(View):
    """Ticket-Erstellungs-View mit Kategorie-Auswahl"""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🎟️ Ticket eröffnen", style=discord.ButtonStyle.primary)
    async def open_ticket_prompt(self, button: Button, interaction: discord.Interaction):
        """Zeigt die Ticket-Kategorie-Auswahl"""
        await interaction.response.send_message("📝 Bitte wähle die Art deines Tickets aus:", view=TicketCategorySelect(self.bot), ephemeral=True)


class TicketCategorySelect(View):
    """Zeigt eine Auswahl für den Ticket-Typ"""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.select(
        placeholder="Bitte wähle eine Ticket-Kategorie...",
        options=[
            discord.SelectOption(label="Allgemeine Frage", description="Allgemeine Anliegen oder Fragen."),
            discord.SelectOption(label="Technischer Support", description="Technische Probleme oder Software."),
            discord.SelectOption(label="Account-Probleme", description="Fragen zu deinem Konto oder Login."),
        ]
    )
    async def select_category(self, select: Select, interaction: discord.Interaction):
        category_name = select.values[0]  # Gewählte Kategorie
        await TicketSystem().open_ticket(interaction, category_name)


class TicketSystem:
    """Funktion zur Erstellung von Tickets"""

    async def open_ticket(self, interaction: discord.Interaction, category_name: str):
        """Erstellt einen Ticket-Channel mit dem gewählten Typ"""
        guild = interaction.guild
        user = interaction.user

        # Kategorie für Tickets suchen oder erstellen
        category = discord.utils.get(guild.categories, name="📩 Tickets")
        if category is None:
            category = await guild.create_category("📩 Tickets")

        # Prüfen, ob der User bereits ein Ticket hat
        for channel in category.text_channels:
            if channel.topic and f"Ticket von {user.id}" in channel.topic:
                return await interaction.response.send_message("❌ Du hast bereits ein offenes Ticket!", ephemeral=True)

        # Ticket-Channel erstellen
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        ticket_channel = await category.create_text_channel(f"ticket-{user.name}", overwrites=overwrites)
        await ticket_channel.edit(topic=f"Ticket von {user.id} ({category_name})")

        # Schließen- und Archivierungs-Buttons senden
        view = CloseOrArchiveView()
        embed = discord.Embed(
            title="🎫 Ticket geöffnet",
            description=f"{user.mention}, dein Ticket wurde in der Kategorie **{category_name}** erstellt. Ein Teammitglied wird sich bald melden!",
            color=discord.Color.green()
        )
        await ticket_channel.send(content=user.mention, embed=embed, view=view)

        # Auto-Close nach 24 Stunden starten (nur für nicht-archivierte Tickets)
        asyncio.create_task(auto_close_ticket(ticket_channel))

        # Antwort an den User
        await interaction.response.send_message(f"✅ Ticket erstellt: {ticket_channel.mention}", ephemeral=True)


class CloseOrArchiveView(View):
    """Bietet die Option, ein Ticket zu schließen oder zu archivieren"""

    def __init__(self):
        super().__init__(timeout=None)
        self.archived = False  # Verhindert doppelte Archivierung

    @discord.ui.button(label="❌ Ticket schließen", style=discord.ButtonStyle.danger)
    async def close_ticket(self, button: Button, interaction: discord.Interaction):
        """Bestätigungsabfrage für das Schließen des Tickets"""
        await interaction.response.send_message("⚠️ Bist du sicher, dass du das Ticket schließen möchtest?", view=ConfirmCloseView(), ephemeral=True)

    @discord.ui.button(label="📂 Ticket archivieren", style=discord.ButtonStyle.secondary)
    async def archive_ticket(self, button: Button, interaction: discord.Interaction):
        """Archiviert das Ticket einmalig & entfernt den Zugriff für den Ersteller"""
        if self.archived:
            return await interaction.response.send_message("❌ Dieses Ticket wurde bereits archiviert!", ephemeral=True)

        guild = interaction.guild
        channel = interaction.channel

        # Archiv-Kategorie suchen oder erstellen
        archive_category = discord.utils.get(guild.categories, name="📂 Archiv")
        if archive_category is None:
            archive_category = await guild.create_category("📂 Archiv")

        # Den Ersteller des Tickets herausfinden
        user_id = None
        if channel.topic and "Ticket von" in channel.topic:
            user_id = int(channel.topic.split("Ticket von ")[1].split(" ")[0])

        member = guild.get_member(user_id) if user_id else None

        if member:
            await channel.set_permissions(member, view_channel=False, send_messages=False, read_message_history=False)

            # DM an den User senden
            try:
                await member.send(f"📂 Dein Ticket `{channel.name}` wurde archiviert und ist nicht mehr für dich sichtbar.")
            except discord.Forbidden:
                print(f"❌ Konnte {member} keine DM senden.")

        await channel.edit(name=f"archived-{channel.name}", category=archive_category)
        self.archived = True  # Blockiert doppelte Archivierung

        await interaction.response.send_message("✅ Das Ticket wurde archiviert.", ephemeral=True)


class ConfirmCloseView(View):
    """Bestätigung für das Löschen eines Tickets"""

    @discord.ui.button(label="✅ Bestätigen", style=discord.ButtonStyle.success)
    async def confirm_close(self, button: Button, interaction: discord.Interaction):
        """Schließt und löscht das Ticket, nachdem der User bestätigt hat"""
        channel = interaction.channel
        guild = interaction.guild

        # Den Ersteller des Tickets herausfinden
        user_id = None
        if channel.topic and "Ticket von" in channel.topic:
            user_id = int(channel.topic.split("Ticket von ")[1].split(" ")[0])

        member = guild.get_member(user_id) if user_id else None

        # DM an den User senden
        if member:
            try:
                await member.send(f"❌ Dein Ticket `{channel.name}` wurde geschlossen und gelöscht.")
            except discord.Forbidden:
                print(f"❌ Konnte {member} keine DM senden.")

        await interaction.channel.delete()

async def auto_close_ticket(channel: discord.TextChannel):
    """Schließt Tickets nach 24h Inaktivität mit einer 10s Verzögerung vor der Löschung."""
    await asyncio.sleep(86400)  # 24 Stunden warten

    # Prüfen, ob der Channel noch existiert
    if not channel or not channel.guild or channel not in channel.guild.channels:
        print(f"⚠️ Channel {channel} existiert nicht mehr, Auto-Close abgebrochen.")
        return  # Falls der Channel nicht mehr existiert, wird die Funktion beendet

    # Prüfen, ob das Ticket noch in der "📩 Tickets"-Kategorie ist (nicht archiviert)
    if channel.category and channel.category.name == "📩 Tickets":
        try:
            messages = [msg async for msg in channel.history(limit=1)]
        except discord.errors.NotFound:
            print(f"⚠️ Channel {channel.name} wurde gelöscht, Auto-Close gestoppt.")
            return  # Falls der Channel nicht existiert, abbrechen

        # Prüfen, ob 24h Inaktivität vorliegt
        if not messages or (discord.utils.utcnow() - messages[0].created_at).total_seconds() > 86400:
            guild = channel.guild

            # Den Ersteller des Tickets herausfinden
            user_id = None
            if channel.topic and "Ticket von" in channel.topic:
                user_id = int(channel.topic.split("Ticket von ")[1].split(" ")[0])

            member = guild.get_member(user_id) if user_id else None

            # DM an den User senden
            if member:
                try:
                    await member.send(f"⏳ Dein Ticket `{channel.name}` wurde wegen 24h Inaktivität automatisch geschlossen.")
                except discord.Forbidden:
                    print(f"⚠️ Konnte {member} keine DM senden.")

            # Nachricht im Ticket senden
            try:
                await channel.send("⏳ Dieses Ticket wurde wegen Inaktivität geschlossen und wird in **10 Sekunden** gelöscht.")
                await asyncio.sleep(10)  # 10 Sekunden warten
                await channel.delete()
            except discord.errors.NotFound:
                print(f"⚠️ Channel {channel.name} wurde bereits gelöscht.")


class TicketCog(commands.Cog):
    """Das Hauptmodul für das Ticket-System"""

    def __init__(self, bot):
        self.bot = bot  # Speichert die Bot-Instanz

    @commands.Cog.listener()
    async def on_ready(self):
        """Erkennt bestehende Tickets & das Ticket-Setup nach einem Neustart"""
        await self.bot.wait_until_ready()  # Wartet, bis alle Daten geladen sind
        print("🎟️ Ticket-System geladen!")

        for guild in self.bot.guilds:
            # 🔄 1. Offene & archivierte Tickets erkennen
            for category_name in ["📩 Tickets", "📂 Archiv"]:
                category = discord.utils.get(guild.categories, name=category_name)
                if category:
                    for channel in category.text_channels:
                        if channel.topic and "Ticket von" in channel.topic or "ticket-" in channel.name:
                            print(f"🔄 Ticket erkannt: {channel.name} (Kategorie: {category_name})")
                            view = CloseOrArchiveView()
                            try:
                                await channel.send("🔄 Der Bot wurde neugestartet. Dein Ticket ist weiterhin aktiv.", view=view)
                            except discord.Forbidden:
                                print(f"⚠️ Keine Schreibrechte in {channel.name}")

            # 🔄 2. Ticket-Setup Nachricht wiederherstellen
            for channel in guild.text_channels:
                try:
                    async for message in channel.history(limit=50):  # Sucht nach der Setup-Nachricht
                        if message.embeds and message.embeds[0].title and "🎟️ Support-Tickets" in message.embeds[0].title:
                            print(f"🔄 Ticket-Setup gefunden in {channel.name}, Buttons werden wiederhergestellt.")
                            view = TicketView(self.bot)
                            await message.edit(view=view)
                            return
                except discord.Forbidden:
                    print(f"⚠️ Bot hat keine Berechtigung, Nachrichten in {channel.name} zu lesen.")

        print("⚠️ Kein Ticket-Setup gefunden! Ein Admin muss /ticketsetup ausführen.")

    @commands.slash_command(name="ticketsetup", description="Erstellt das Ticket-System")
    @commands.has_permissions(administrator=True)
    async def ticketsetup(self, ctx):
        """Erstellt die Ticket-Setup-Nachricht mit Button"""
        embed = discord.Embed(
            title="🎟️ Support-Tickets",
            description="Drücke auf den Button, um ein Ticket zu erstellen.",
            color=discord.Color.blue()
        )
        view = TicketView(self.bot)
        await ctx.send(embed=embed, view=view)

def setup(bot):
    """Fügt den Cog dem Bot hinzu"""
    bot.add_cog(TicketCog(bot))

