import asyncio
import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from backend.config import settings

async def main():
    try:
        print("Connecting to:", settings.MONGODB_URI.replace(settings.MONGODB_URI.split('@')[0], "mongodb+srv://***"))
        client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            tlsCAFile=certifi.where()
        )
        await client.admin.command('ping')
        print("✅ Ping successful!")
    except Exception as e:
        print("❌ Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
