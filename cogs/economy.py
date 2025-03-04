import discord
import sqlite3
import random
import datetime

from discord import slash_command
from discord.ext import commands

from cooldown_handler import check_cooldown

DATABASE = "economy.db"


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_init()



    def db_init(self):
        """Erstellt die Economy-Tabelle, falls sie nicht existiert"""
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 100,
                    bank INTEGER DEFAULT 0,
                    last_daily TEXT,
                    last_quest TEXT,
                    quest_status TEXT DEFAULT 'offen',
                    quest_reward INTEGER DEFAULT 0,
                    quest_description TEXT
                )
            """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER,
                item TEXT,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, item)
            )
        """)
        # Nachrichtentracking für Quests
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # Glücksspiel-Tracking für Quests
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS gambles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    result TEXT CHECK(result IN ('win', 'lose'))
                )
            """)

        # Transaktions-Tracking für Quests
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER,
                    receiver_id INTEGER,
                    amount INTEGER,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()
        conn.close()
    def get_balance(self, user_id):
        """Holt den aktuellen Kontostand (Wallet & Bank)"""
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT balance, bank FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result if result else (0, 0)
    def update_balance(self, user_id, wallet_change=0, bank_change=0):
        """Fügt Coins zur Wallet oder Bank hinzu/zieht sie ab"""
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (user_id, balance, bank) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?, bank = bank + ?",
            (user_id, wallet_change, bank_change, wallet_change, bank_change))
        conn.commit()
        conn.close()
    def add_item(self, user_id, item):
        """Fügt ein Item ins Inventar hinzu"""
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO inventory (user_id, item, quantity) VALUES (?, ?, 1) ON CONFLICT(user_id, item) DO UPDATE SET quantity = quantity + 1",
            (user_id, item))
        conn.commit()
        conn.close()
    def has_item(self, user_id, item):
        """Prüft, ob der User ein bestimmtes Item besitzt"""
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item = ?", (user_id, item))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    @commands.Cog.listener()
    async def on_ready(self):
        """Fügt alle Mitglieder zur Datenbank hinzu, sobald der Bot bereit ist"""
        await self.bot.wait_until_ready()
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        for guild in self.bot.guilds:
            for member in guild.members:
                if not member.bot:  # Nur echte User hinzufügen
                    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (member.id,))
                    cursor.execute("INSERT OR IGNORE INTO inventory (user_id, item, quantity) VALUES (?, ?, ?)",
                                   (member.id, 'start-item', 1))
                    cursor.execute("INSERT OR IGNORE INTO messages (user_id) VALUES (?)", (member.id,))
                    cursor.execute("INSERT OR IGNORE INTO gambles (user_id, result) VALUES (?, ?)", (member.id, 'lose'))
                    cursor.execute(
                        "INSERT OR IGNORE INTO transactions (sender_id, receiver_id, amount) VALUES (?, ?, ?)",
                        (member.id, 0, 0))

        conn.commit()
        conn.close()
        print("✅  Alle Mitglieder wurden zur Datenbank hinzugefügt.")
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Fügt neue Mitglieder automatisch in alle Tabellen ein."""
        if member.bot:  # Bots ignorieren
            return

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (member.id,))
        cursor.execute("INSERT OR IGNORE INTO inventory (user_id, item, quantity) VALUES (?, ?, ?)",
                       (member.id, 'start-item', 1))
        cursor.execute("INSERT OR IGNORE INTO messages (user_id) VALUES (?)", (member.id,))
        cursor.execute("INSERT OR IGNORE INTO gambles (user_id, result) VALUES (?, ?)", (member.id, 'lose'))
        cursor.execute("INSERT OR IGNORE INTO transactions (sender_id, receiver_id, amount) VALUES (?, ?, ?)",
                       (member.id, 0, 0))

        conn.commit()
        conn.close()
        print(f"✅ {member.name} wurde in die Datenbank eingefügt.")
    @slash_command(name="balance", description="Zeigt deinen Kontostand")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def balance(self, ctx):
        """Zeigt den Wallet- und Bank-Kontostand"""
        balance, bank = self.get_balance(ctx.author.id)
        await ctx.respond(f"💰 Wallet: **{balance} Coins**\n🏦 Bank: **{bank} Coins**")

    @slash_command(name="daily", description="Erhalte einmal pro Tag Coins")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def daily(self, ctx):
        """User können einmal pro Tag Coins abholen"""
        user_id = ctx.author.id
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        today = datetime.date.today().isoformat()

        if result and result[0] == today:
            await ctx.respond("❌ Du hast deine täglichen Coins heute schon abgeholt.")
        else:
            reward = random.randint(100, 300)  # Zufälliger Daily-Bonus
            self.update_balance(user_id, reward)
            cursor.execute(
                "INSERT INTO users (user_id, last_daily) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_daily = ?",
                (user_id, today, today))
            conn.commit()
            await ctx.respond(f"✅ Du hast **{reward} Coins** erhalten!")

        conn.close()

    @slash_command(name="deposit", description="Lege Geld auf die Bank")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def deposit(self, ctx, amount: int):
        """User können Geld auf die Bank legen"""
        balance, bank = self.get_balance(ctx.author.id)

        if amount <= 0 or amount > balance:
            await ctx.respond("❌ Ungültige Menge oder nicht genug Coins.")
            return

        self.update_balance(ctx.author.id, -amount, amount)
        await ctx.respond(f"✅ Du hast **{amount} Coins** auf die Bank eingezahlt!")

    @slash_command(name="withdraw", description="Hebe Geld von der Bank ab")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def withdraw(self, ctx, amount: int):
        """User können Geld von der Bank abheben"""
        balance, bank = self.get_balance(ctx.author.id)

        if amount <= 0 or amount > bank:
            await ctx.respond("❌ Ungültige Menge oder nicht genug Coins auf der Bank.")
            return

        self.update_balance(ctx.author.id, amount, -amount)
        await ctx.respond(f"✅ Du hast **{amount} Coins** von der Bank abgehoben!")

    @slash_command(name="shop", description="Zeigt den virtuellen Shop")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def slash_command(self, ctx):
        """Zeigt eine Liste von kaufbaren Items"""
        embed = discord.Embed(title="🛒 Virtueller Shop", color=discord.Color.gold())
        embed.add_field(name="🎩 Glückshut", value="5000 Coins - Erhöht die Casino-Gewinnchance", inline=False)
        embed.add_field(name="🕶️ Diebesmaske", value="3000 Coins - Erhöht die Raub-Erfolgsrate", inline=False)
        await ctx.respond(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Speichert jede gesendete Nachricht in der Datenbank"""
        if message.author.bot:
            return  # Bots ignorieren
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (user_id, timestamp) VALUES (?, CURRENT_TIMESTAMP)
        """, (message.author.id,))

        conn.commit()
        conn.close()

    @commands.slash_command(name="buy", description="Kaufe ein Item aus dem Shop")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def buy(self, ctx, item: str):
        """User können Items kaufen, falls sie genug Coins haben"""
        prices = {"glückshut": 5000, "diebesmaske": 3000}
        item = item.lower()

        if item not in prices:
            await ctx.respond("❌ Dieses Item existiert nicht.")
            return

        price = prices[item]
        balance, _ = self.get_balance(ctx.author.id)

        if balance < price:
            await ctx.respond("❌ Du hast nicht genug Coins für dieses Item.")
            return

        self.update_balance(ctx.author.id, -price)
        self.add_item(ctx.author.id, item)
        await ctx.respond(f"✅ Du hast **{item.capitalize()}** für **{price} Coins** gekauft!")

    @commands.slash_command(name="gamble", description="Spiele und verdopple dein Geld oder verliere es")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def gamble(self, ctx, amount: int):
        """User können Coins setzen – mit Bonus, falls sie einen Glückshut haben"""
        balance, _ = self.get_balance(ctx.author.id)

        if amount <= 0 or amount > balance:
            await ctx.respond("❌ Ungültige Menge oder nicht genug Coins.")
            return

        win_chance = 50  # Standard Gewinnchance

        # 🎩 Prüfen, ob der User einen Glückshut besitzt
        if self.has_item(ctx.author.id, "glückshut"):
            win_chance += 20  # Erhöht die Chance um 20% (50% → 70%)

        gamble_result = "lose"

        if random.randint(1, 100) <= win_chance:
            bonus = random.randint(100, 1000)  # Zufälliger Bonus
            self.update_balance(ctx.author.id, amount + bonus)
            gamble_result = "win"
            await ctx.respond(
                f"🎰 **Glückwunsch!** Du hast **{amount} Coins** gewonnen und einen Bonus von **{bonus} Coins** erhalten! 🎉")
        else:
            self.update_balance(ctx.author.id, -amount)
            await ctx.respond(f"💀 **Pech gehabt!** Du hast **{amount} Coins** verloren. 😢")

        # Glücksspiel-Ergebnis speichern
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO gambles (user_id, result) VALUES (?, ?)
        """, (ctx.author.id, gamble_result))
        conn.commit()
        conn.close()

        print(f"✅ Glücksspiel gespeichert: {ctx.author} - {gamble_result}")

    @commands.slash_command(name="dailyquest",description="Zeigt deine aktuelle Tagesquest oder gibt eine neue, falls 24 Stunden vorbei sind")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def dailyquest(self, ctx):
        """Zeigt die aktuelle Tagesquest oder vergibt eine neue nach 24 Stunden"""
        quests = [
            "Sende eine freundliche Nachricht in den Chat.",
            "Gewinne eine Wette im Casino.",
            "Schicke einem Freund 50 Coins.",

        ]
        quest_rewards = {
            "Sende eine freundliche Nachricht in den Chat.": 200,
            "Gewinne eine Wette im Casino.": 300,
            "Schicke einem Freund 50 Coins.": 150,

        }

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # 🔍 Aktuelle Quest abrufen
        cursor.execute("SELECT last_quest, quest_status, quest_reward, quest_description FROM users WHERE user_id = ?",
                       (ctx.author.id,))
        result = cursor.fetchone()

        now = datetime.datetime.now()
        last_quest_time = datetime.datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S") if result and result[0] else None
        quest_status, quest_reward, current_quest = result[1:] if result else ("offen", 0, "Keine Quest vorhanden.")

        # Prüfen, ob 24 Stunden seit der letzten Quest vergangen sind
        if not last_quest_time or (now - last_quest_time).total_seconds() >= 86400:  # 86400 Sekunden = 24 Stunden
            new_quest = random.choice(quests)
            quest_reward = quest_rewards[new_quest]

            cursor.execute("""
                UPDATE users 
                SET last_quest = ?, quest_status = 'offen', quest_reward = ?, quest_description = ? 
                WHERE user_id = ?
            """, (now.strftime("%Y-%m-%d %H:%M:%S"), quest_reward, new_quest, ctx.author.id))

            conn.commit()
            current_quest = new_quest  # Aktualisierte Quest setzen
            quest_status = "offen"

        conn.close()

        # 📝 Embed zur Anzeige der aktuellen Quest
        embed = discord.Embed(title="📜 Deine Tagesquest", color=discord.Color.blue())
        embed.add_field(name="🔹 Aufgabe:", value=f"**{current_quest}**", inline=False)
        embed.add_field(name="💰 Belohnung:", value=f"**{quest_reward} Coins**", inline=False)

        # Falls die Quest schon abgeschlossen ist
        if quest_status == "abgeschlossen":
            embed.color = discord.Color.green()
            embed.set_footer(text="✅ Diese Quest wurde bereits abgeschlossen.")

        # Falls die Quest noch offen ist, berechne die verbleibende Zeit
        elif last_quest_time:
            remaining_time = 86400 - (now - last_quest_time).total_seconds()
            hours, minutes = divmod(remaining_time // 60, 60)
            embed.set_footer(text=f"🔄 Nächste Quest in {int(hours)} Stunden und {int(minutes)} Minuten verfügbar.")

        await ctx.respond(embed=embed)

    @commands.slash_command(name="completequest",description="Überprüft und beendet deine Tagesquest, wenn sie abgeschlossen ist.")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def completequest(self, ctx):
        """Prüft, ob der User seine Tagesquest erfüllt hat und gibt die Belohnung."""
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # 🛠 Richtige Spalten aus der Datenbank abrufen!
        cursor.execute("SELECT last_quest, quest_status, quest_reward, quest_description FROM users WHERE user_id = ?",
                       (ctx.author.id,))
        result = cursor.fetchone()

        if not result:
            await ctx.respond("❌ Du hast keine aktive Tagesquest.", ephemeral=True)
            return

        quest_date, quest_status, quest_reward, current_quest = result  # 🟢 Jetzt wird die Quest richtig geholt!

        if quest_status != "offen":
            embed = discord.Embed(title="🎯 Quest Status", description="✅ Deine Tagesquest wurde bereits abgeschlossen!",
                                  color=discord.Color.green())
            await ctx.respond(embed=embed)
            return

        import datetime

        # 🛠 `quest_date` aus der DB abrufen
        cursor.execute("SELECT last_quest FROM users WHERE user_id = ?", (ctx.author.id,))
        result = cursor.fetchone()
        quest_date = result[0] if result else None  # `None`, falls kein Wert vorhanden ist

        if quest_date:
            try:
                # Falls `quest_date` bereits ein String ist, in `datetime` umwandeln
                quest_date = datetime.datetime.strptime(quest_date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                print(f"❌ Fehler: `quest_date` hat falsches Format: {quest_date}")  # Debugging
                await ctx.respond("❌ Ein Fehler ist aufgetreten. Bitte kontaktiere einen Admin.", ephemeral=True)
                return

            # In das richtige Format für SQLite umwandeln
            quest_date = quest_date.strftime("%Y-%m-%d %H:%M:%S")

        # 🛠 SQL-Abfrage mit richtigem `quest_date`
        cursor.execute("""
            SELECT COUNT(*) FROM messages 
            WHERE user_id = ? 
            AND datetime(timestamp) >= datetime(?)
        """, (ctx.author.id, quest_date))
        messages_sent = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM gambles WHERE user_id = ? AND timestamp >= ? AND result = 'win'",
                       (ctx.author.id, quest_date))
        gambles_won = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM transactions WHERE sender_id = ? AND timestamp >= ? AND amount >= 50",
                       (ctx.author.id, quest_date))
        coins_sent = cursor.fetchone()[0]

        quest_completed = False

        if "freundliche Nachricht" in current_quest.lower() and messages_sent > 0:
            quest_completed = True
        elif "wette im casino gewinnen" in current_quest.lower() and gambles_won > 0:
            quest_completed = True
        elif "freund 50 coins senden" in current_quest.lower() and coins_sent > 0:
            quest_completed = True

        if not quest_completed:
            embed = discord.Embed(title="❌ Quest nicht erfüllt", color=discord.Color.red())
            embed.add_field(name="📜 Deine aktuelle Quest:", value=f"**{current_quest}**",
                            inline=False)  # ✅ Jetzt zeigt es die richtige Quest!
            embed.add_field(name="🔄 Status:", value="Noch nicht abgeschlossen!", inline=False)
            await ctx.respond(embed=embed, ephemeral=True)
            return

        # 🏆 Quest abschließen & Belohnung geben
        self.update_balance(ctx.author.id, quest_reward)
        cursor.execute("UPDATE users SET quest_status = 'abgeschlossen' WHERE user_id = ?", (ctx.author.id,))
        conn.commit()
        conn.close()

        # Erfolgreiches Abschluss-Embed
        embed = discord.Embed(title="🎉 Quest abgeschlossen!", color=discord.Color.gold())
        embed.add_field(name="📜 Deine Quest:", value=f"**{current_quest}**", inline=False)
        embed.add_field(name="💰 Belohnung:", value=f"**{quest_reward} Coins**", inline=False)

        await ctx.respond(embed=embed)

        # Optional: DM an den User senden
        try:
            await ctx.author.send(f"🎉 Deine Tagesquest wurde abgeschlossen! Du hast **{quest_reward} Coins** erhalten.")
        except discord.Forbidden:
            print(f"❌ Konnte {ctx.author} keine DM senden.")

    @commands.slash_command(name="rob", description="Versuche, einen User auszurauben")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def rob(self, ctx, member: discord.Member):
        """User können versuchen, andere auszurauben (nur Wallet-Geld, mit Item-Bonus)"""
        if ctx.author.id == member.id:
            await ctx.respond("❌ Du kannst dich nicht selbst ausrauben!")
            return

        victim_balance, _ = self.get_balance(member.id)

        if victim_balance < 100:
            await ctx.respond(f"❌ {member.mention} hat nicht genug Coins in der Wallet zum Ausrauben.")
            return

        # Standardmäßige Erfolgswahrscheinlichkeit (60%)
        success_chance = 60

        # Prüfen, ob der User eine Diebesmaske hat → Erfolgsrate auf 85% erhöhen
        if self.has_item(ctx.author.id, "diebesmaske"):
            success_chance = 85

        # Erfolgswurf (Zahl zwischen 1-100, muss unterhalb der Erfolgsrate liegen)
        if random.randint(1, 100) <= success_chance:
            stolen_amount = random.randint(50, min(victim_balance, 300))  # Max. 300 Coins klauen
            self.update_balance(ctx.author.id, stolen_amount)  # Dieb bekommt Coins
            self.update_balance(member.id, -stolen_amount)  # Opfer verliert Coins

            await ctx.respond(f"🕵️‍♂️ Du hast **{stolen_amount} Coins** von {member.mention} gestohlen! 🏴‍☠️")
        else:
            # Wenn der Diebstahl fehlschlägt, verliert der Dieb 100 Coins als Strafe
            self.update_balance(ctx.author.id, -100)
            await ctx.respond(
                f"🚔 Pech gehabt! {member.mention} hat dich erwischt! Du verlierst **100 Coins** als Strafe! 😡")

    @commands.slash_command(name="give", description="Sende Coins an einen anderen User")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def give(self, ctx, member: discord.Member, amount: int):
        sender_id = ctx.author.id
        receiver_id = member.id

        # ❌ Selbstüberweisung verhindern
        if sender_id == receiver_id:
            await ctx.respond("❌ Du kannst dir selbst kein Geld senden!", ephemeral=True)
            return

        # ❌ Betrag muss positiv sein
        if amount <= 0:
            await ctx.respond("❌ Du kannst keine negativen oder 0 Coins senden.", ephemeral=True)
            return

        # 💰 Kontostand des Senders abrufen
        sender_balance, _ = self.get_balance(sender_id)

        # ❌ Überprüfung, ob der User genug Geld hat
        if sender_balance < amount:
            await ctx.respond("❌ Du hast nicht genug Coins!", ephemeral=True)
            return

        # ✅ Geld übertragen
        self.update_balance(sender_id, -amount)
        self.update_balance(receiver_id, amount)

        # ✅ Transaktion speichern
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transactions (sender_id, receiver_id, amount, timestamp) 
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (sender_id, receiver_id, amount))
        conn.commit()
        conn.close()

        # ✅ Debugging-Bestätigung in der Konsole
        print(f"✅ DEBUG: {ctx.author} ({sender_id}) → {member} ({receiver_id}): {amount} Coins überwiesen.")

        # ✅ Erfolgreiche Überweisung
        await ctx.respond(f"✅ {ctx.author.mention} hat **{amount} Coins** an {member.mention} gesendet!")

    @commands.slash_command(name="top", description="Zeigt das reichste Ranking auf dem Server")
    @commands.check(check_cooldown)  # ✅ Cooldown für diesen Befehl aktivieren
    async def top(self, ctx):
        """Zeigt ein Leaderboard mit den reichsten Spielern (Wallet + Bank kombiniert)"""
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Holen aller Nutzer nach Balance + Bank, absteigend sortiert
        cursor.execute("SELECT user_id, balance, bank FROM users ORDER BY (balance + bank) DESC LIMIT 10")
        top_users = cursor.fetchall()
        conn.close()

        # Falls keine Daten vorhanden sind
        if not top_users:
            await ctx.respond("❌ Es gibt noch keine Daten für das Leaderboard!")
            return

        # Leaderboard erstellen
        embed = discord.Embed(title="🏆 Leaderboard - Reichste Spieler", color=discord.Color.gold())

        for rank, (user_id, balance, bank) in enumerate(top_users, start=1):
            user = self.bot.get_user(user_id)  # Holt den Discord-Benutzer
            username = user.name if user else f"Unbekannt ({user_id})"
            total_money = balance + bank

            embed.add_field(name=f"**#{rank} {username}**", value=f"💰 {total_money} Coins", inline=False)

        # Benutzer-ID des Autors für Hervorhebung
        user_id = ctx.author.id
        user_rank = None

        # Prüfen, ob der aktuelle Benutzer in den Top 10 ist
        for rank, (u_id, _, _) in enumerate(top_users, start=1):
            if u_id == user_id:
                user_rank = rank
                break

        if user_rank:
            embed.set_footer(text=f"Du bist aktuell auf Platz #{user_rank}!")
        else:
            embed.set_footer(text="Spiele mehr, um in die Top 10 zu kommen!")

        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Economy(bot))