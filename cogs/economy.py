import discord
import sqlite3
import random
import datetime
from discord.ext import commands

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
                    quest_reward INTEGER DEFAULT 0
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

    @commands.slash_command(name="balance", description="Zeigt deinen Kontostand")
    async def balance(self, ctx):
        """Zeigt den Wallet- und Bank-Kontostand"""
        balance, bank = self.get_balance(ctx.author.id)
        await ctx.respond(f"💰 Wallet: **{balance} Coins**\n🏦 Bank: **{bank} Coins**")

    @commands.slash_command(name="daily", description="Erhalte einmal pro Tag Coins")
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

    @commands.slash_command(name="deposit", description="Lege Geld auf die Bank")
    async def deposit(self, ctx, amount: int):
        """User können Geld auf die Bank legen"""
        balance, bank = self.get_balance(ctx.author.id)

        if amount <= 0 or amount > balance:
            await ctx.respond("❌ Ungültige Menge oder nicht genug Coins.")
            return

        self.update_balance(ctx.author.id, -amount, amount)
        await ctx.respond(f"✅ Du hast **{amount} Coins** auf die Bank eingezahlt!")

    @commands.slash_command(name="withdraw", description="Hebe Geld von der Bank ab")
    async def withdraw(self, ctx, amount: int):
        """User können Geld von der Bank abheben"""
        balance, bank = self.get_balance(ctx.author.id)

        if amount <= 0 or amount > bank:
            await ctx.respond("❌ Ungültige Menge oder nicht genug Coins auf der Bank.")
            return

        self.update_balance(ctx.author.id, amount, -amount)
        await ctx.respond(f"✅ Du hast **{amount} Coins** von der Bank abgehoben!")

    @commands.slash_command(name="shop", description="Zeigt den virtuellen Shop")
    async def shop(self, ctx):
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

    @commands.slash_command(name="dailyquest", description="Erhalte eine tägliche Aufgabe für Coins")
    async def dailyquest(self, ctx):
        """Jeder User bekommt eine zufällige Tagesquest"""
        quests = [
            "Sende eine freundliche Nachricht in den Chat.",
            "Gewinne eine Wette im Casino.",
            "Schicke einem Freund 50 Coins.",

        ]
        quest_rewards = {"Sende eine freundliche Nachricht in den Chat.": 200,
                         "Gewinne eine Wette im Casino.": 300,
                         "Schicke einem Freund 50 Coins.": 150,
                     }

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT last_quest, quest_status FROM users WHERE user_id = ?", (ctx.author.id,))
        result = cursor.fetchone()
        today = datetime.date.today().isoformat()

        if result and result[0] == today and result[1] == "offen":
            await ctx.respond("❌ Du hast bereits eine aktive Tagesquest!")
            return
        elif result and result[0] == today and result[1] == "abgeschlossen":
            await ctx.respond("✅ Du hast deine Tagesquest bereits abgeschlossen.")
            return

        quest = random.choice(quests)
        reward = quest_rewards[quest]

        cursor.execute(
            "INSERT INTO users (user_id, last_quest, quest_status, quest_reward) VALUES (?, ?, 'offen', ?) ON CONFLICT(user_id) DO UPDATE SET last_quest = ?, quest_status = 'offen', quest_reward = ?",
            (ctx.author.id, today, reward, today, reward))
        conn.commit()
        conn.close()

        await ctx.respond(
            f"📜 Deine Tagesquest: **{quest}**\nBelohnung: **{reward} Coins**\nMelde dich nach Erfüllung bei einem Admin!")

    @commands.slash_command(name="completequest",
                            description="Überprüft und beendet deine Tagesquest, wenn sie abgeschlossen ist.")
    async def completequest(self, ctx):
        """Prüft, ob der User seine Tagesquest erfüllt hat und gibt die Belohnung."""
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Aktuelle Quest des Nutzers abrufen
        cursor.execute("SELECT last_quest, quest_status, quest_reward, quest_status FROM users WHERE user_id = ?",
                       (ctx.author.id,))
        result = cursor.fetchone()

        if not result:
            await ctx.respond("❌ Du hast keine aktive Tagesquest.", ephemeral=True)
            return

        quest_date, quest_status, quest_reward, current_quest = result

        if quest_status != "offen":
            await ctx.respond("✅ Deine Tagesquest wurde bereits abgeschlossen oder existiert nicht.", ephemeral=True)
            return

        # Quest-Bedingungen aus der Datenbank prüfen
        cursor.execute("SELECT COUNT(*) FROM messages WHERE user_id = ? AND timestamp >= ?",
                       (ctx.author.id, quest_date))
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
            await ctx.respond("❌ Du hast die Quest-Bedingungen noch nicht erfüllt!", ephemeral=True)
            return

        # Quest abschließen & Belohnung auszahlen
        self.update_balance(ctx.author.id, quest_reward)
        cursor.execute("UPDATE users SET quest_status = 'abgeschlossen' WHERE user_id = ?", (ctx.author.id,))
        conn.commit()
        conn.close()

        await ctx.respond(f"✅ Deine Tagesquest wurde abgeschlossen! Du hast **{quest_reward} Coins** erhalten.")

        try:
            await ctx.author.send(f"🎉 Deine Tagesquest wurde abgeschlossen! Du hast **{quest_reward} Coins** erhalten.")
        except discord.Forbidden:
            print(f"❌ Konnte {ctx.author} keine DM senden.")


    @commands.slash_command(name="rob", description="Versuche, einen User auszurauben")
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
    async def give(self, ctx, member: discord.Member, amount: int):
        sender_id = ctx.author.id
        receiver_id = member.id

        if amount <= 0:
            return await ctx.respond("❌ Du kannst keine negativen oder 0 Coins senden.")

        sender_balance, _ = self.get_balance(sender_id)

        if sender_balance < amount:
            return await ctx.respond("❌ Du hast nicht genug Coins!")

        # Geld übertragen
        self.update_balance(sender_id, -amount)
        self.update_balance(receiver_id, amount)

        # Transaktion speichern
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transactions (sender_id, receiver_id, amount) VALUES (?, ?, ?)
        """, (sender_id, receiver_id, amount))
        conn.commit()
        conn.close()

        await ctx.respond(f"✅ {ctx.author.mention} hat **{amount} Coins** an {member.mention} gesendet!")

    @commands.slash_command(name="addcoins", description="Fügt einem User Coins hinzu (Admin)")
    @commands.has_permissions(administrator=True)
    async def addcoins(self, ctx, member: discord.Member, amount: int):
        """Admins können Coins an User vergeben"""
        if amount <= 0:
            await ctx.respond("❌ Betrag muss größer als 0 sein.")
            return

        self.update_balance(member.id, amount)
        await ctx.respond(f"✅ {amount} Coins wurden zu {member.mention} hinzugefügt.")

    @commands.slash_command(name="top", description="Zeigt das reichste Ranking auf dem Server")
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
