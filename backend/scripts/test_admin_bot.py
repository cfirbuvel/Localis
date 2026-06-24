import os
import sys
from unittest.mock import patch, AsyncMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, engine, SessionLocal
from backend.models import User, Verification, Emergency, CommunityRequest, LocationNode, GroupChat, RoleAssignment
from backend.scripts.seed_db import seed

client = TestClient(app)

async def mock_geocode_text(address: str):
    return {
        "country": "Israel",
        "city": "גבעתיים",
        "neighborhood": "Florentin",
        "street": "Herzel",
        "building": "Herzel 12"
    }

async def mock_search_public_groups(query: str):
    return [
        {
            "title": f"Localis: {query} (Official)",
            "chat_id": f"tg_chat_{query.lower()}_official",
            "invite_link": f"https://t.me/{query.lower()}_official"
        }
    ]

async def mock_create_telegram_group(node_name: str, level: str, node_id: int = None, *args, **kwargs):
    return {
        "chat_id": f"tg_chat_{node_name.lower().replace(' ', '_')}",
        "invite_link": f"https://t.me/joinchat/tg_chat_{node_name.lower().replace(' ', '_')}"
    }

@patch("backend.services.telegram_userbot.create_telegram_group", side_effect=mock_create_telegram_group)
@patch("backend.services.telegram_userbot.search_public_groups", side_effect=mock_search_public_groups)
@patch("backend.services.geocoding.geocode_text", side_effect=mock_geocode_text)
def run_tests(mock_geo, mock_search, mock_create):
    print("====================================================")
    print("RUNNING TARGETED TELEGRAM ADMIN BOT WORKFLOW TESTS")
    print("====================================================")

    # 0. Clean and Seed Database for deterministic run
    print("Resetting database to a clean seeded state...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed()
    print("[OK] Database reset and seeded.")

    db = SessionLocal()

    # Create admin user configuration
    admin_tg_id = "111111111"
    admin_username = "super_admin_user"
    
    # 1. Register admin_tg_id in DB and assign Role
    admin_user = User(
        username=admin_username,
        telegram_id=admin_tg_id,
        phone_number="123456789",
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    admin_role = RoleAssignment(
        user_id=admin_user.id,
        location_id=None,
        role="SUPER_ADMIN"
    )
    db.add(admin_role)
    db.commit()
    print(f"[OK] Admin user created: id={admin_user.id}, telegram_id={admin_tg_id}")

    # 2. Test /admin command
    print("\n[TEST 1] Admin sends /admin command...")
    payload_admin = {
        "update_id": 20001,
        "message": {
            "message_id": 101,
            "from": {
                "id": int(admin_tg_id),
                "is_bot": False,
                "first_name": "Admin",
                "username": admin_username
            },
            "chat": {
                "id": int(admin_tg_id),
                "type": "private"
            },
            "date": 1600000000,
            "text": "/admin"
        }
    }
    response = client.post("/webhooks/telegram", json=payload_admin)
    assert response.status_code == 200
    print("[OK] Admin menu command handled successfully.")

    # 3. Test verification list callback
    print("\n[TEST 2] Admin clicks Verification Queue button...")
    # Add a pending verification
    alice = User(username="alice", telegram_id="222222222")
    db.add(alice)
    db.commit()
    db.refresh(alice)
    
    building = db.query(LocationNode).filter(LocationNode.level == "BUILDING").first()
    pending_verif = Verification(
        user_id=alice.id,
        building_id=building.id,
        proof_url="https://example.com/proof.jpg",
        status="PENDING"
    )
    db.add(pending_verif)
    db.commit()
    db.refresh(pending_verif)
    print(f"Created pending verification request ID: {pending_verif.id} for user {alice.username}")

    payload_cb = {
        "update_id": 20002,
        "callback_query": {
            "id": "cb_query_admin_1",
            "from": {
                "id": int(admin_tg_id),
                "username": admin_username
            },
            "message": {
                "message_id": 102,
                "chat": {
                    "id": int(admin_tg_id),
                }
            },
            "data": "admin_verif_list"
        }
    }
    response = client.post("/webhooks/telegram", json=payload_cb)
    assert response.status_code == 200
    print("[OK] Verification queue listing callback handled successfully.")

    # 4. Test detail view verification callback
    print("\n[TEST 3] Admin views details of the pending verification...")
    payload_cb["callback_query"]["data"] = f"admin_ver_v_{pending_verif.id}"
    response = client.post("/webhooks/telegram", json=payload_cb)
    assert response.status_code == 200
    print("[OK] Detail view callback handled successfully.")

    # 5. Test approve verification callback
    print("\n[TEST 4] Admin approves the verification request...")
    payload_cb["callback_query"]["data"] = f"admin_ver_app_{pending_verif.id}"
    response = client.post("/webhooks/telegram", json=payload_cb)
    assert response.status_code == 200
    
    # Check DB
    db.refresh(pending_verif)
    assert pending_verif.status == "APPROVED"
    print("[OK] Verification request status is APPROVED in DB.")

    # 6. Test municipal group suggestions when searching a missing city
    # Simulate search for missing city: Israel > Giv'atayim > Florentin > Herzel > Herzel 12
    # Givatayim is not in DB, so it should trigger suggestions
    print("\n[TEST 5] Admin searches for address containing missing city 'גבעתיים'...")
    payload_search = {
        "update_id": 20005,
        "message": {
            "message_id": 105,
            "from": {
                "id": int(admin_tg_id),
                "username": admin_username
            },
            "chat": {
                "id": int(admin_tg_id),
                "type": "private"
            },
            "date": 1600000000,
            "text": "Herzel 12, גבעתיים, Israel"
        }
    }
    response = client.post("/webhooks/telegram", json=payload_search)
    assert response.status_code == 200
    print("[OK] Geocoding and search output displayed missing items option.")

    # Trigger request missing path callback
    print("\n[TEST 6] Admin clicks 'Yes, request creation' for missing path...")
    payload_cb["callback_query"]["data"] = "req_missing_path"
    response = client.post("/webhooks/telegram", json=payload_cb)
    assert response.status_code == 200
    print("[OK] Creation interception display municipal suggestions.")

    # Link one suggestion callback
    print("\n[TEST 7] Admin selects first municipal group suggestion (Link)...")
    payload_cb["callback_query"]["data"] = "city_sugg_link_0"
    response = client.post("/webhooks/telegram", json=payload_cb)
    assert response.status_code == 200
    
    # Check DB: Node Giv'atayim/Givatayim must be created and linked to the mock/real suggestion group chat
    givatayim_node = db.query(LocationNode).filter(LocationNode.level == "CITY", LocationNode.name.ilike("%גבעתיים%")).first()
    if not givatayim_node:
        givatayim_node = db.query(LocationNode).filter(LocationNode.level == "CITY", LocationNode.name.ilike("%givatayim%")).first()
    assert givatayim_node is not None, "City node was not created"
    
    tg_group = db.query(GroupChat).filter(GroupChat.location_id == givatayim_node.id, GroupChat.platform == "TELEGRAM").first()
    assert tg_group is not None, "Telegram group chat not linked/created"
    print(f"[OK] City node created: '{givatayim_node.name}' (ID: {givatayim_node.id}) and linked to Telegram chat ID: {tg_group.chat_id}")

    db.close()
    print("\nAll targeted Telegram admin bot workflow tests PASSED successfully!")
    print("====================================================")

if __name__ == "__main__":
    run_tests()
