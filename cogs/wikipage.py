import discord
from discord.ext import commands
from discord.commands import slash_command, Option
import aiohttp
import difflib

WIKI_API_URL = "https://naruto-unknown-times.fandom.com/de/api.php"
WIKI_BASE_URL = "https://naruto-unknown-times.fandom.com/de/wiki/"

class WikiDiff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(name="show_diff", description="Zeigt übersichtliche Änderungen einer Wiki-Seite (Admin only)")
    @commands.has_permissions(administrator=True)
    async def show_diff(
        self,
        ctx,
        seitenname: Option(str, "Name der Wiki-Seite")
    ):
        await ctx.defer()

        async with aiohttp.ClientSession() as session:
            async with session.get(WIKI_API_URL, params={
                "action": "query",
                "prop": "revisions",
                "titles": seitenname,
                "rvlimit": 2,
                "rvprop": "ids|user|comment|content",
                "format": "json"
            }) as resp:
                if resp.status != 200:
                    return await ctx.respond("❌ Fehler beim Abrufen der Revisionen.")
                data = await resp.json()

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return await ctx.respond("❌ Seite nicht gefunden.")

        page = next(iter(pages.values()))
        revisions = page.get("revisions", [])
        if len(revisions) < 2:
            return await ctx.respond("❌ Nicht genügend Revisionen zum Vergleich.")

        newer = revisions[0]
        older = revisions[1]
        title = page.get("title", seitenname)

        old_text = older.get("*") or older.get("slots", {}).get("main", {}).get("*", "")
        new_text = newer.get("*") or newer.get("slots", {}).get("main", {}).get("*", "")

        if not old_text or not new_text:
            return await ctx.respond("❌ Quelltext konnte nicht geladen werden.")

        # Vergleich durchführen
        diff = list(difflib.ndiff(old_text.splitlines(), new_text.splitlines()))
        removed = [line[2:] for line in diff if line.startswith("- ")]
        added = [line[2:] for line in diff if line.startswith("+ ")]

        before_text = "\n".join(removed).strip() or "–"
        after_text = "\n".join(added).strip() or "–"

        if len(before_text) > 1000:
            before_text = before_text[:1000] + "\n... (gekürzt)"
        if len(after_text) > 1000:
            after_text = after_text[:1000] + "\n... (gekürzt)"

        embed = discord.Embed(
            title=f"📄 Änderungen in: {title}",
            url=f"{WIKI_BASE_URL}{title.replace(' ', '_')}?diff={newer['revid']}&oldid={older['revid']}",
            description=(
                f"**Bearbeiter:** `{newer.get('user', 'Unbekannt')}`\n"
                f"**Kommentar:** _{newer.get('comment', '–')}_"
            ),
            color=discord.Color.blue()
        )

        embed.add_field(name="❌ Vorher", value=f"```diff\n- {before_text}\n```", inline=False)
        embed.add_field(name="✅ Nachher", value=f"```diff\n+ {after_text}\n```", inline=False)

        embed.set_footer(text="Quelltextvergleich – automatisch generiert")

        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(WikiDiff(bot))
