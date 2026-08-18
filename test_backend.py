import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000/api"

async def main():
    async with httpx.AsyncClient() as client:
        print("1. Testing Health")
        resp = await client.get("http://localhost:8000/health")
        print("Health:", resp.status_code, resp.json())

        print("\n2. Testing Login")
        data = {"username": "admin", "password": "admin123"}
        resp = await client.post(f"{BASE_URL}/auth/login", data=data)
        print("Login:", resp.status_code)
        if resp.status_code != 200:
            print(resp.text)
            return
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        print("\n3. Testing Category Creation")
        cat_data = {"name": "Test Category", "description": "Test description"}
        resp = await client.post(f"{BASE_URL}/menu/categories", json=cat_data, headers=headers)
        print("Category:", resp.status_code, resp.json())

        print("\n4. Testing Menu Item Creation")
        item_data = {
            "name": "Test Pizza",
            "description": "Delicious test pizza",
            "category": "Test Category",
            "price": 12.5,
            "ingredients": ["dough", "cheese", "tomato"],
            "dietary_tags": ["veg"]
        }
        resp = await client.post(f"{BASE_URL}/menu/items", json=item_data, headers=headers)
        print("Menu Item:", resp.status_code, resp.json())

        print("\n5. Testing Twilio Incoming Call (Simulation)")
        twilio_data = {
            "From": "+1234567890",
            "CallSid": "CA12345678901234567890123456789012"
        }
        resp = await client.post(f"{BASE_URL}/twilio/incoming", data=twilio_data)
        print("Twilio Incoming:", resp.status_code)
        print(resp.text[:200])

if __name__ == "__main__":
    asyncio.run(main())
