import re

import discord
import aiosqlite
import asyncio
from discord.ext import commands, tasks
from discord.ui import View, Button

class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_cleanup.start()  # Task für automatische Ticket-Löschung

    async def create_tables(self):
        """Erstellt die notwendigen Tabellen in der Datenbank."""
        async with aiosqlite.connect("channels.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    user_id INTEGER,
                    user_name TEXT,
                    guild_id INTEGER,
                    message_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'open',
                    FOREIGN KEY (guild_id) REFERENCES servers (guild_id)
                )
            """)
            await db.commit()

    async def update_ticket_embed(self, channel, new_status):
        """Aktualisiert das Embed eines Tickets mit einem neuen Status."""
        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT message_id FROM tickets WHERE channel_id = ?", (channel.id,))
            result = await row.fetchone()

        if not result:
            return  # Falls die Nachricht nicht in der DB gespeichert ist

        message_id = result[0]
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            print(f"⚠ Ticket-Nachricht in {channel.name} nicht gefunden.")
            return

        # **Neues Status-Embed generieren**
        embed = message.embeds[0] if message.embeds else discord.Embed(title="🎫 Ticket")
        status_field_index = None

        for i, field in enumerate(embed.fields):
            if field.name == "⏳ Status":
                status_field_index = i
                break

        if status_field_index is not None:
            embed.set_field_at(status_field_index, name="⏳ Status", value=f"**{new_status}**", inline=True)
        else:
            embed.add_field(name="⏳ Status", value=f"**{new_status}**", inline=True)

        await message.edit(embed=embed)

    async def get_ticket_embed(self, guild, user):
        """Lädt das Ticket-Setup-Embed aus der Datenbank & ersetzt Platzhalter."""
        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute(
                "SELECT ticket_embed_title, ticket_embed_description, ticket_embed_color FROM servers WHERE guild_id = ?",
                (guild.id,))
            result = await row.fetchone()

        if not result:
            return None

        titel, beschreibung, farbe = result

        # **Platzhalter in Titel & Beschreibung ersetzen**
        titel = await self.replace_placeholders(titel, guild, user)
        beschreibung = await self.replace_placeholders(beschreibung, guild, user)

        # **HEX-Farbe umwandeln**
        try:
            color = discord.Color(int(farbe.replace("#", ""), 16))
        except ValueError:
            color = discord.Color.blue()

        embed = discord.Embed(title=titel, description=beschreibung, color=color)
        embed.set_footer(text="Klicke auf den Button, um ein Ticket zu erstellen!")
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2972/2972473.png")
        return embed

    async def replace_placeholders(self, text, guild, user):
        """Ersetzt Platzhalter wie @user, @rolle:Admin, @channel:Support durch Erwähnungen."""
        text = text.replace("@user", user.mention)

        # Rollen ersetzen
        role_matches = re.findall(r"@rolle:([A-Za-z0-9-_]+)", text)
        for role_name in role_matches:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                text = text.replace(f"@rolle:{role_name}", role.mention)
            else:
                text = text.replace(f"@rolle:{role_name}", f"`{role_name} (nicht gefunden)`")

        # Kanäle ersetzen
        channel_matches = re.findall(r"@channel:([A-Za-z0-9-_]+)", text)
        for channel_name in channel_matches:
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                text = text.replace(f"@channel:{channel_name}", channel.mention)
            else:
                text = text.replace(f"@channel:{channel_name}", f"`#{channel_name} (nicht gefunden)`")

        return text

    @commands.Cog.listener()
    async def on_ready(self):
        """Prüft, ob Ticket-Setup-Nachricht und bestehende Tickets existieren, und registriert Buttons."""
        await self.create_tables()

        # **Views neu registrieren**
        self.bot.add_view(TicketButton(self.bot))
        self.bot.add_view(TicketActions(self.bot))
        print("✅ Ticket-Buttons wurden nach Neustart wiederhergestellt.")

        async with aiosqlite.connect("channels.db") as db:
            # **Prüfen, ob die Ticket-Setup-Nachricht noch existiert**
            rows = await db.execute("SELECT guild_id, text_setup, message_id FROM servers")
            rows = await rows.fetchall()

            for row in rows:
                guild_id, text_setup, message_id = row
                guild = self.bot.get_guild(guild_id)

                if guild:
                    setup_channel = guild.get_channel(text_setup)
                    if setup_channel:
                        try:
                            await setup_channel.fetch_message(message_id)  # Prüft, ob die Nachricht existiert
                            print(f"✅ Ticket-Setup-Nachricht in {guild.name} ist vorhanden.")
                        except discord.NotFound:
                            print(f"⚠ Ticket-Setup-Nachricht in {guild.name} nicht gefunden. Erstelle sie neu.")
                            await self.send_ticket_message(setup_channel, guild_id)

            # **Prüfen, ob Tickets noch existieren (Falls Kanal gelöscht wurde, Ticket aus DB entfernen)**
            ticket_rows = await db.execute("SELECT channel_id FROM tickets")
            ticket_rows = await ticket_rows.fetchall()

            for row in ticket_rows:
                channel_id = row[0]
                channel = self.bot.get_channel(channel_id)

                if channel is None:  # Kanal existiert nicht mehr
                    await db.execute("DELETE FROM tickets WHERE channel_id = ?", (channel_id,))
                    await db.commit()
                    print(
                        f"🗑 Ticket mit Kanal-ID {channel_id} wurde aus der Datenbank entfernt, da es nicht mehr existiert.")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Entfernt das Ticket aus der Datenbank, wenn der Kanal gelöscht wird."""
        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT ticket_id FROM tickets WHERE channel_id = ?", (channel.id,))
            result = await row.fetchone()

            if result:
                await db.execute("DELETE FROM tickets WHERE channel_id = ?", (channel.id,))
                await db.commit()
                print(f"🗑 Ticket {channel.name} wurde aus der Datenbank entfernt, da der Kanal gelöscht wurde.")

    @tasks.loop(hours=1)
    async def ticket_cleanup(self):
        """Löscht alte, unbeantwortete Tickets nach 24 Stunden."""
        async with aiosqlite.connect("channels.db") as db:
            rows = await db.execute(
                "SELECT channel_id, user_id FROM tickets WHERE status = 'open' AND created_at <= datetime('now', '-1 day')")
            rows = await rows.fetchall()

            for row in rows:
                channel_id, user_id = row
                channel = self.bot.get_channel(channel_id)
                user = self.bot.get_user(user_id)
                if channel:
                    await self.delete_ticket(channel, user)
                    print(f"🗑 Ticket {channel.name} wurde wegen Inaktivität gelöscht.")

    async def get_ticket_open_embed(self, guild, user):
        """Erstellt das Ticket-Embed & ersetzt Platzhalter."""
        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT ticket_embed_description FROM servers WHERE guild_id = ?", (guild.id,))
            result = await row.fetchone()

        beschreibung = result[0] if result else "Ein Teammitglied wird sich bald um dich kümmern."

        # **Platzhalter ersetzen**
        beschreibung = await self.replace_placeholders(beschreibung, guild, user)

        embed = discord.Embed(title="🎫 Dein Ticket wurde erstellt!", description=beschreibung,
                              color=discord.Color.green())
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1828/1828919.png")
        embed.add_field(name="📌 Ticket-Ersteller", value=user.mention, inline=True)
        embed.add_field(name="⏳ Status", value="**Offen**", inline=True)
        embed.set_footer(text="Bitte warte auf eine Antwort des Supports.")
        return embed

    async def send_ticket_message(self, channel, guild_id):
        """Sendet die Ticket-Embed-Nachricht mit Button."""
        embed = discord.Embed(title="🎫 Ticketsystem", description="Klicke auf den Button, um ein Ticket zu erstellen.", color=discord.Color.blue())
        view = TicketButton(self.bot)

        message = await channel.send(embed=embed, view=view)

        async with aiosqlite.connect("channels.db") as db:
            await db.execute("UPDATE servers SET message_id = ? WHERE guild_id = ?", (message.id, guild_id))
            await db.commit()

    @commands.slash_command(name="ticket-setup", description="Legt den Ticket-Setup-Channel fest.")
    @commands.has_permissions(administrator=True)
    async def ticket_setup(self, ctx):
        """Setzt den Setup-Channel für das Ticketsystem und sendet die Embed-Nachricht."""
        guild = ctx.guild
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")

        setup_channel = discord.utils.get(guild.text_channels, name="🎫-ticket-erstellen")
        if not setup_channel:
            setup_channel = await guild.create_text_channel("🎫-ticket-erstellen", category=category)

        async with aiosqlite.connect("channels.db") as db:
            await db.execute("UPDATE servers SET text_setup = ? WHERE guild_id = ?", (setup_channel.id, guild.id))
            await db.commit()

        embed = await self.get_ticket_embed(ctx.guild, ctx.author)  # ✅ FIXED: ctx.author als `user` übergeben
        view = TicketButton(self.bot)

        message = await setup_channel.send(embed=embed, view=view)

        async with aiosqlite.connect("channels.db") as db:
            await db.execute("UPDATE servers SET message_id = ? WHERE guild_id = ?", (message.id, guild.id))
            await db.commit()

        await ctx.respond(f"✅ Das Ticketsystem wurde eingerichtet! Nachricht gesendet in {setup_channel.mention}.",
                          ephemeral=True)

    @commands.slash_command(name="set-ticket-embed", description="Ändert die Embed-Nachricht für das Ticket-Setup.")
    @commands.has_permissions(administrator=True)
    async def set_ticket_embed(self, ctx, titel: str, beschreibung: str, farbe: str):
        """Erlaubt Admins, die Ticket-Setup-Nachricht mit Variablen zu bearbeiten."""
        async with aiosqlite.connect("channels.db") as db:
            await db.execute(
                "UPDATE servers SET ticket_embed_title = ?, ticket_embed_description = ?, ticket_embed_color = ? WHERE guild_id = ?",
                (titel, beschreibung, farbe, ctx.guild.id))
            await db.commit()

        await ctx.respond("✅ Die Ticket-Setup-Nachricht wurde aktualisiert!", ephemeral=True)

        # Bestehende Nachricht updaten
        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT text_setup, message_id FROM servers WHERE guild_id = ?", (ctx.guild.id,))
            result = await row.fetchone()

        if result:
            setup_channel = ctx.guild.get_channel(result[0])
            if setup_channel:
                try:
                    message = await setup_channel.fetch_message(result[1])
                    embed = await self.get_ticket_embed(ctx.guild, ctx.user)  # Embed mit Platzhaltern aktualisieren
                    await message.edit(embed=embed)
                    print("✅ Ticket-Setup-Embed wurde aktualisiert.")
                except discord.NotFound:
                    print("⚠ Ticket-Setup-Nachricht existiert nicht mehr.")


class TicketButton(View):
    def __init__(self, bot):
        super().__init__(timeout=None)  # ✅ Timeout deaktiviert
        self.bot = bot

    @discord.ui.button(label="🎫 Ticket erstellen", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, button: Button, interaction: discord.Interaction):
        """Erstellt ein Ticket mit den richtigen Berechtigungen für den Nutzer."""
        guild = interaction.guild
        user = interaction.user

        ticket_cog = self.bot.get_cog("TicketSystem")  # ✅ TicketSystem-Cog abrufen
        if not ticket_cog:
            return await interaction.response.send_message("⚠ Fehler: Ticket-System ist nicht geladen.", ephemeral=True)

        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute(
                "SELECT channel_id FROM tickets WHERE user_id = ? AND guild_id = ? AND status = 'open'",
                (user.id, guild.id))
            existing_ticket = await row.fetchone()

        if existing_ticket:
            return await interaction.response.send_message("⚠ Du hast bereits ein offenes Ticket!", ephemeral=True)

        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")  # Erstellt Kategorie, falls nicht vorhanden

        # ✅ Ticket-Channel mit korrekten Berechtigungen erstellen
        ticket_channel = await guild.create_text_channel(
            f"ticket-{user.name}",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),  # Blockiert andere User
                user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True,
                                                  embed_links=True)
            }
        )

        embed = await ticket_cog.get_ticket_open_embed(guild, user)  # ✅ Ticket-Embed abrufen
        view = TicketActions(self.bot)

        message = await ticket_channel.send(embed=embed, view=view)

        async with aiosqlite.connect("channels.db") as db:
            await db.execute(
                "INSERT INTO tickets (channel_id, user_id, user_name, guild_id, message_id, status) VALUES (?, ?, ?, ?, ?, 'open')",
                (ticket_channel.id, user.id, user.name, guild.id, message.id)
            )
            await db.commit()

        await interaction.response.send_message(f"✅ Ticket erstellt! {ticket_channel.mention}", ephemeral=True)


class TicketActions(View):
    """Buttons zum Archivieren und Löschen eines Tickets"""
    def __init__(self, bot):
        super().__init__(timeout=None)  # ✅ Timeout deaktiviert
        self.bot = bot

    @discord.ui.button(label="📁 Archivieren", style=discord.ButtonStyle.secondary, custom_id="archive_ticket")
    async def archive_ticket(self, button: Button, interaction: discord.Interaction):
        """Fragt den Nutzer, ob er das Ticket wirklich archivieren möchte."""
        channel = interaction.channel
        ticket_cog = self.bot.get_cog("TicketSystem")

        if not ticket_cog:
            return await interaction.response.send_message("⚠ Fehler: Ticket-System nicht gefunden.", ephemeral=True)

        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT status FROM tickets WHERE channel_id = ?", (channel.id,))
            ticket_status = await row.fetchone()

        # **Falls Ticket bereits archiviert ist, abbrechen**
        if ticket_status and ticket_status[0] == "archived":
            return await interaction.response.send_message("⚠ Dieses Ticket wurde bereits archiviert!", ephemeral=True)

        # **Bestätigungsabfrage senden**
        view = TicketArchiveConfirm(self.bot, channel)
        embed = discord.Embed(
            title="📁 Ticket-Archivierung",
            description="⚠ Bist du sicher, dass du dieses Ticket archivieren möchtest?",
            color=discord.Color.orange()
        )
        embed.add_field(name="📌 Ticket", value=channel.mention, inline=False)
        embed.set_footer(text="Drücke 'Bestätigen', um das Ticket zu archivieren.")

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🗑 Löschen", style=discord.ButtonStyle.danger, custom_id="delete_ticket")
    async def delete_ticket(self, button: Button, interaction: discord.Interaction):
        """Fragt den Nutzer, ob er das Ticket wirklich löschen möchte."""
        channel = interaction.channel

        # **Bestätigungsabfrage senden**
        view = TicketDeleteConfirm(self.bot, channel)
        await interaction.response.send_message("⚠ Bist du sicher, dass du dieses Ticket löschen möchtest?", view=view, ephemeral=True)



class TicketDeleteConfirm(View):
    """Bestätigungsabfrage für das Löschen eines Tickets"""
    def __init__(self, bot, channel):
        super().__init__(timeout=None)
        self.bot = bot
        self.channel = channel

    @discord.ui.button(label="✅ Bestätigen", style=discord.ButtonStyle.green, custom_id="confirm_delete")
    async def confirm_delete(self, button: Button, interaction: discord.Interaction):
        """Löscht das Ticket nach Bestätigung."""
        user = interaction.user

        if not self.channel:
            return await interaction.response.send_message("⚠ Fehler: Dieses Ticket wurde bereits gelöscht.",
                                                           ephemeral=True)

        await self.channel.send("⚠ Dieses Ticket wird in **10 Sekunden** gelöscht.")
        await asyncio.sleep(10)

        # **Prüfen, ob der Kanal noch existiert**
        if self.channel and interaction.guild.get_channel(self.channel.id):
            try:
                await self.channel.delete()
            except discord.NotFound:
                print(f"⚠ Ticket-Channel {self.channel.id} wurde bereits gelöscht.")
        else:
            print(f"⚠ Ticket-Channel {self.channel.id} existiert nicht mehr.")

        # **Nutzer per DM benachrichtigen**
        try:
            await user.send("🚫 Dein Ticket wurde geschlossen.")
        except discord.Forbidden:
            print(f"⚠ Konnte {user} keine DM senden.")

        # **Ticket aus der Datenbank entfernen**
        async with aiosqlite.connect("channels.db") as db:
            await db.execute("DELETE FROM tickets WHERE channel_id = ?", (self.channel.id,))
            await db.commit()

        print(f"🗑 Ticket {self.channel.name} wurde gelöscht.")

    @discord.ui.button(label="❌ Abbrechen", style=discord.ButtonStyle.gray, custom_id="cancel_delete")
    async def cancel_delete(self, button: Button, interaction: discord.Interaction):
        """Bricht den Ticket-Löschprozess ab."""
        await interaction.response.send_message("✅ Ticket-Löschung abgebrochen.", ephemeral=True)



class TicketArchiveConfirm(View):
    """Bestätigungsabfrage für das Archivieren eines Tickets"""

    def __init__(self, bot, channel):
        super().__init__(timeout=None)
        self.bot = bot
        self.channel = channel

    @discord.ui.button(label="✅ Bestätigen", style=discord.ButtonStyle.green, custom_id="confirm_archive")
    async def confirm_archive(self, button: Button, interaction: discord.Interaction):
        """Bestätigt das Archivieren des Tickets & entzieht dem User die Rechte."""
        guild = interaction.guild

        # ✅ Kategorie "Archivierte Tickets" erstellen, falls nicht vorhanden
        archive_category = discord.utils.get(guild.categories, name="📁 Archivierte Tickets")
        if not archive_category:
            archive_category = await guild.create_category("📁 Archivierte Tickets")

        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (self.channel.id,))
            ticket_owner_id = await row.fetchone()

        if not ticket_owner_id:
            return await interaction.response.send_message("⚠ Fehler: Ticket-Daten nicht gefunden!", ephemeral=True)

        ticket_owner = guild.get_member(ticket_owner_id[0])  # ✅ Ticket-Ersteller abrufen

        # ✅ Falls Ticket bereits archiviert ist, abbrechen
        async with aiosqlite.connect("channels.db") as db:
            row = await db.execute("SELECT status FROM tickets WHERE channel_id = ?", (self.channel.id,))
            ticket_status = await row.fetchone()

        if ticket_status and ticket_status[0] == "archived":
            return await interaction.response.send_message("⚠ Dieses Ticket wurde bereits archiviert!", ephemeral=True)

        # ✅ Ticket verschieben & Rechte entfernen
        await self.channel.edit(category=archive_category)
        await self.channel.set_permissions(ticket_owner, overwrite=discord.PermissionOverwrite(read_messages=False))

        await interaction.response.send_message("✅ Das Ticket wurde archiviert!", ephemeral=True)

        # ✅ Datenbank aktualisieren
        async with aiosqlite.connect("channels.db") as db:
            await db.execute("UPDATE tickets SET status = 'archived' WHERE channel_id = ?", (self.channel.id,))
            await db.commit()
            print(f"📁 Ticket {self.channel.name} wurde in der Datenbank als 'archived' markiert.")

    @discord.ui.button(label="❌ Abbrechen", style=discord.ButtonStyle.gray, custom_id="cancel_archive")
    async def cancel_archive(self, button: Button, interaction: discord.Interaction):
        """Bricht die Archivierung ab."""
        await interaction.response.send_message("✅ Archivierung abgebrochen.", ephemeral=True)


def setup(bot):
    bot.add_cog(TicketSystem(bot))