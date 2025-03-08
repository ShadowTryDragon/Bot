import aiohttp

async def fetch_bot_settings():
    """Holt sich die aktuellen Einstellungen aus der Web-API."""
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:5000/settings") as response:
            if response.status == 200:
                return await response.json()
            return None

async def update_bot_config():
    """Aktualisiert die Bot-Einstellungen nach einem Neustart."""
    settings = await fetch_bot_settings()
    if settings:
        print(f"✅ Einstellungen geladen: {settings}")
