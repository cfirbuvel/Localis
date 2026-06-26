import os
import sys
import asyncio
from sqlalchemy.orm import Session

# Add the parent directory of backend to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import SessionLocal, engine, Base
from backend.models import LocationNode, GroupChat
from backend.services.geocoding import geocode_text
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ExportChatInviteRequest

# Backup coordinates and radius mapping for locations
COORDINATES_FALLBACK = {
    1: {"latitude": 31.046051, "longitude": 34.851612, "radius": 100000.0},  # Israel
    2: {"latitude": 32.0853,   "longitude": 34.7818,   "radius": 15000.0},   # Tel Aviv District
    3: {"latitude": 32.015833, "longitude": 34.7875,   "radius": 2000.0},    # Holon City
    4: {"latitude": 32.0163,   "longitude": 34.7788,   "radius": 800.0},     # Ne'ot Rachel Neighborhood
    5: {"latitude": 32.0163,   "longitude": 34.7788,   "radius": 250.0},     # Manya VeIsrael Shohat Street
    6: {"latitude": 32.0163,   "longitude": 34.7788,   "radius": 50.0},      # Manya VeIsrael Shohat 5 Building
    7: {"latitude": 32.0167,   "longitude": 34.75,     "radius": 2000.0},    # Bat Yam City
    8: {"latitude": 32.0168,   "longitude": 34.7618,   "radius": 800.0},     # Yoseftal Neighborhood
    9: {"latitude": 32.0168,   "longitude": 34.7618,   "radius": 250.0},     # Yoseftal 39 Street (Bat Yam)
}

HIERARCHY_DEFINITION = [
    {"id": 1, "name": "Israel", "level": "COUNTRY", "parent_id": None, "query": "Israel"},
    {"id": 2, "name": "מחוז תל אביב", "level": "DISTRICT", "parent_id": 1, "query": "Tel Aviv District, Israel"},
    {"id": 3, "name": "Holon", "level": "CITY", "parent_id": 2, "query": "Holon, Israel"},
    {"id": 4, "name": "Ne'ot Rachel", "level": "NEIGHBORHOOD", "parent_id": 3, "query": "Ne'ot Rachel, Holon, Israel"},
    {"id": 5, "name": "Manya VeIsrael Shohat", "level": "STREET", "parent_id": 4, "query": "Manya VeIsrael Shohat, Holon, Israel"},
    {"id": 6, "name": "Manya VeIsrael Shohat 5", "level": "BUILDING", "parent_id": 5, "query": "Manya VeIsrael Shohat 5, Holon, Israel"},
    {"id": 7, "name": "Bat Yam", "level": "CITY", "parent_id": 2, "query": "Bat Yam, Israel"},
    {"id": 8, "name": "Yoseftal", "level": "NEIGHBORHOOD", "parent_id": 7, "query": "Yoseftal, Bat Yam, Israel"},
    {"id": 9, "name": "Yoseftal 39", "level": "STREET", "parent_id": 8, "query": "Yoseftal 39, Bat Yam, Israel"},
]

async def fetch_telegram_groups():
    api_id = int(os.getenv("TELEGRAM_API_ID"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_string = os.getenv("TELEGRAM_SESSION_STRING")

    print("Connecting to Telegram userbot...")
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        print("Error: Userbot is not authorized!")
        await client.disconnect()
        return {}

    print("Fetching dialogs...")
    dialogs = await client.get_dialogs(limit=100)
    groups_data = {}

    for d in dialogs:
        if d.is_group or d.is_channel:
            title = d.name
            if "localis" in title.lower():
                chat_id = str(d.id)
                username = getattr(d.entity, 'username', None)
                
                # Default invite link for public groups
                invite_link = f"https://t.me/{username}" if username else None
                
                # Fetch private group invite link
                if not invite_link:
                    try:
                        invite = await client(ExportChatInviteRequest(peer=d.entity, request_needed=True))
                        invite_link = invite.link
                    except Exception as e:
                        try:
                            # Try exporting without request_needed
                            invite = await client(ExportChatInviteRequest(peer=d.entity))
                            invite_link = invite.link
                        except Exception as e2:
                            print(f"Could not export invite link for {title}: {e2}")
                
                groups_data[chat_id] = {
                    "title": title,
                    "username": username,
                    "invite_link": invite_link
                }
                print(f"Found group on Telegram: '{title}' -> ID: {chat_id}, Link: {invite_link}")

    await client.disconnect()
    return groups_data

def match_node_to_telegram(node_id, node_name, node_level, telegram_groups):
    """Matches a database location node to its corresponding Telegram group."""
    suffix = f"_{node_level.lower()}_{node_id}"
    
    # 1. First pass: strict username suffix match (strongest match)
    for chat_id, group in telegram_groups.items():
        username = group["username"]
        if username and username.endswith(suffix):
            return chat_id, group
            
    # 2. Second pass: precise title matching
    for chat_id, group in telegram_groups.items():
        title = group["title"].lower().strip()
        
        if node_id == 1 and title == "localis: israel":
            return chat_id, group
        if node_id == 2 and title == "localis: מחוז תל אביב":
            return chat_id, group
        if node_id == 4 and title == "localis: ne'ot rachel":
            return chat_id, group
        if node_id == 5 and title == "localis: manya veisrael shohat":
            return chat_id, group
        if node_id == 6 and title == "localis: manya veisrael shohat 5":
            return chat_id, group
        if node_id == 7 and "bat yam" in title and "yoseftal" not in title:
            return chat_id, group
        if node_id == 8 and "yoseftal" in title and "39" not in title:
            return chat_id, group
        if node_id == 9 and ("yoseftal 39" in title or "רחוב yoseftal 39" in title):
            return chat_id, group

    return None, None

async def main():
    # 1. Fetch live groups from Telegram
    telegram_groups = await fetch_telegram_groups()

    # 2. Re-create locations and groups in the database
    db = SessionLocal()
    try:
        # Clean up existing locations and groups to prevent duplicates
        print("Cleaning up locations and groups tables...")
        db.query(GroupChat).delete()
        db.query(LocationNode).delete()
        db.commit()

        for defn in HIERARCHY_DEFINITION:
            node_id = defn["id"]
            name = defn["name"]
            level = defn["level"]
            parent_id = defn["parent_id"]
            address_query = defn["query"]

            # Geocode coordinate lookup
            print(f"Geocoding location: {address_query}...")
            lat, lon = None, None
            try:
                res = await geocode_text(address_query)
                if res and res.get("latitude") is not None and res.get("longitude") is not None:
                    lat = res["latitude"]
                    lon = res["longitude"]
                    print(f"  Geocoded successfully: {lat}, {lon}")
            except Exception as e:
                print(f"  Geocoding error for {address_query}: {e}")

            # Fallback to coordinates dictionary if geocoding returns None
            fallback = COORDINATES_FALLBACK[node_id]
            if lat is None or lon is None:
                lat = fallback["latitude"]
                lon = fallback["longitude"]
                print(f"  Using fallback coordinates: {lat}, {lon}")

            radius = fallback["radius"]

            # Create LocationNode with explicit ID
            node = LocationNode(
                id=node_id,
                name=name,
                level=level,
                parent_id=parent_id,
                latitude=lat,
                longitude=lon,
                radius=radius
            )
            db.add(node)
            db.commit()
            db.refresh(node)
            print(f"Created location node: ID {node.id} -> '{name}' ({level})")

            # Match and add Telegram group chat
            gtype = "PRIVATE" if level == "BUILDING" else "PUBLIC"
            chat_id, group_info = match_node_to_telegram(node_id, name, level, telegram_groups)

            if chat_id:
                tg_chat_id = chat_id
                tg_invite_link = group_info["invite_link"]
                print(f"  Matched Telegram Group: ID {tg_chat_id}, Link: {tg_invite_link}")
            else:
                # Fallback to mock group if no matching group on Telegram
                tg_chat_id = f"tg_chat_{name.lower().replace(' ', '_')}"
                tg_invite_link = f"https://t.me/joinchat/{tg_chat_id}"
                print(f"  No live Telegram group found. Using mock: ID {tg_chat_id}")

            tg_group = GroupChat(
                location_id=node.id,
                platform="TELEGRAM",
                chat_id=tg_chat_id,
                type=gtype,
                invite_link=tg_invite_link
            )
            db.add(tg_group)

            # Add exactly one mock WhatsApp group
            wa_chat_id = f"wa_chat_{name.lower().replace(' ', '_')}"
            wa_group = GroupChat(
                location_id=node.id,
                platform="WHATSAPP",
                chat_id=wa_chat_id,
                type=gtype,
                invite_link=f"https://chat.whatsapp.com/{wa_chat_id}"
            )
            db.add(wa_group)
            db.commit()
            print(f"  Created Group Chat links for node {node.id}")

        print("Database restoration complete and committed successfully!")

    finally:
        db.close()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv("backend/.env")
    asyncio.run(main())
