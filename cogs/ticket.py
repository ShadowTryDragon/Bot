import discord
from discord.ext import commands
from discord.ui import View, Button, Select


class TicketCategorySelect(View):


    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.select(
        placeholder="Bitte wähle eine Ticket-Kategorie aus...",
        options=[
            discord.SelectOption(label="Charakter Archiv", description="Fragen rund ums Charakter Archiv ."),
            discord.SelectOption(label="Rechte", description="Probleme mit den Rechten im Archiv."),
            discord.SelectOption(label="Sonstiges", description="Sonstige Anliegen."),
        ]
    )
    async def select_category(self, select: Select, interaction: discord.Interaction):
        category_name = select.values[0]  # Gewählte Kategorie
        await TicketView(self.bot).open_ticket(interaction, category_name)


class TicketView(View):


    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🎟️ Ticket eröffnen", style=discord.ButtonStyle.primary)
    async def open_ticket_prompt(self, button: Button, interaction: discord.Interaction):

        await interaction.response.send_message("📝 Bitte wähle die Art deines Tickets aus:",
                                                view=TicketCategorySelect(self.bot), ephemeral=True)

    async def open_ticket(self, interaction: discord.Interaction, category_name: str):

        guild = interaction.guild
        user = interaction.user


        category = discord.utils.get(guild.categories, name="📩 Tickets")
        if category is None:
            category = await guild.create_category("📩 Tickets")


        for channel in category.text_channels:
            if channel.topic and f"Ticket von {user.id}" in channel.topic:
                return await interaction.response.send_message("❌ Du hast bereits ein offenes Ticket!", ephemeral=True)


        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        ticket_channel = await category.create_text_channel(f"ticket-{user.name}", overwrites=overwrites)
        await ticket_channel.edit(topic=f"Ticket von {user.id} ({category_name})")


        view = CloseOrArchiveView()
        embed = discord.Embed(
            title="🎫 Ticket geöffnet",
            description=f"{user.mention}, dein Ticket wurde in der Kategorie **{category_name}** erstellt. Ein Teammitglied wird sich bald melden!",
            color=discord.Color.green()
        )
        await ticket_channel.send(content=user.mention, embed=embed, view=view)


        await interaction.response.send_message(f"✅ Ticket erstellt: {ticket_channel.mention}", ephemeral=True)


class CloseOrArchiveView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.archived = False  # Neu: Verhindert doppelte Archivierung



    @discord.ui.button(label="❌ Ticket schließen", style=discord.ButtonStyle.danger)
    async def close_ticket(self, button: Button, interaction: discord.Interaction):

        await interaction.response.send_message("⚠️ Bist du sicher, dass du das Ticket schließen möchtest?",
                                                view=ConfirmCloseView(), ephemeral=True)

    @discord.ui.button(label="📂 Ticket archivieren", style=discord.ButtonStyle.secondary)
    async def archive_ticket(self, button: Button, interaction: discord.Interaction):
        """Archiviert das Ticket und entfernt den Zugriff für den Ersteller"""
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
            user_id = int(channel.topic.split("Ticket von ")[1].split(" ")[0])  # Extrahiert die User-ID

        if user_id:
            member = guild.get_member(user_id)
            if member:
                await channel.set_permissions(member, view_channel=False, send_messages=False,
                                              read_message_history=False)

        await channel.edit(category=archive_category)
        self.archived = True  # Blockiert doppelte Archivierung

        await interaction.response.send_message("✅ Das Ticket wurde archiviert.", ephemeral=True)
        print(f"📂 Ticket {channel.name} archiviert. Zugriff für {member} entfernt.")  # Debugging


class ConfirmCloseView(View):


    @discord.ui.button(label="✅ Bestätigen", style=discord.ButtonStyle.success)
    async def confirm_close(self, button: Button, interaction: discord.Interaction):
        await interaction.channel.delete()

    @discord.ui.button(label="❌ Abbrechen", style=discord.ButtonStyle.danger)
    async def cancel_close(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_message("❌ Ticket-Schließung abgebrochen!", ephemeral=True)


class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("🎟️ Ticket-System geladen!")

        # Bot-Start: Suche nach offenen Tickets
        for guild in self.bot.guilds:
            for category_name in ["📩 Tickets", "📂 Archiv"]:
                category = discord.utils.get(guild.categories, name=category_name)
                if category:
                    for channel in category.text_channels:
                        if channel.topic and "Ticket von" in channel.topic:
                            print(f"🔄 Ticket erkannt: {channel.name} (Kategorie: {category_name})")
                            view = CloseOrArchiveView()
                            await channel.edit(view=view)  # Kein Message-Senden, nur Buttons aktualisieren

        # Bot-Start: Suche nach Ticket-Setup-Nachricht
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                async for message in channel.history(limit=10):
                    if message.embeds and len(message.embeds) > 0 and message.embeds[0].title:
                        if "🎟️ Support-Tickets" in message.embeds[0].title:
                            print(f"🔄 Ticket-Setup gefunden in {channel.name}, Buttons werden wiederhergestellt.")
                            view = TicketView(self.bot)
                            await message.edit(view=view)
                            return

        print("⚠️ Kein Ticket-Setup gefunden! Ein Admin muss /ticketsetup ausführen.")

    @commands.slash_command(name="ticketsetup", description="Erstellt das Ticket-System")
    @commands.has_permissions(administrator=True)
    async def ticketsetup(self, ctx):
        embed = discord.Embed(title="🎟️ Support-Tickets",
                              description="Drücke auf den Button, um ein Ticket zu erstellen.",
                              color=discord.Color.blue())
        view = TicketView(self.bot)
        await ctx.send(embed=embed, view=view)
        await ctx.respond("Ticket Setup Erfolgreich")


def setup(bot):
    bot.add_cog(TicketCog(bot))
