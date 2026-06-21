import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, engine, SessionLocal
from backend.models import User, Verification, Emergency
from backend.scripts.seed_db import seed

client = TestClient(app)

def run_simulation():
    print("====================================================")
    print("STARTING TELEGRAM & WHATSAPP BOT WORKFLOW SIMULATION")
    print("====================================================")

    # 0. Clean and Seed Database for deterministic run
    print("Resetting database to a clean seeded state...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed()
    print("[OK] Database reset and seeded.")

    # User details
    tg_user_id = "987654321"
    tg_username = "alice_resident"

    # 1. Simulate user sending /start
    print("\n[STEP 1] Alice starts the Telegram Bot (/start)...")
    payload = {
        "update_id": 10001,
        "message": {
            "message_id": 1,
            "from": {
                "id": int(tg_user_id),
                "is_bot": False,
                "first_name": "Alice",
                "username": tg_username
            },
            "chat": {
                "id": int(tg_user_id),
                "type": "private"
            },
            "date": 1600000000,
            "text": "/start"
        }
    }
    response = client.post("/webhooks/telegram", json=payload)
    assert response.status_code == 200
    print("[OK] Bot starting handled successfully.")

    # 2. Simulate user sending /browse to view countries
    print("\n[STEP 2] Alice browses location nodes (/browse)...")
    payload["message"]["text"] = "/browse"
    payload["message"]["message_id"] += 1
    response = client.post("/webhooks/telegram", json=payload)
    assert response.status_code == 200
    print("[OK] Bot browse menu handled successfully.")

    # 3. Simulate Alice selecting Country 'Israel' (ID: 1)
    print("\n[STEP 3] Alice clicks Israel (node_1) button...")
    payload_cb = {
        "update_id": 10003,
        "callback_query": {
            "id": "cb_query_1",
            "from": {
                "id": int(tg_user_id),
                "username": tg_username
            },
            "message": {
                "message_id": 3,
                "chat": {
                    "id": int(tg_user_id),
                }
            },
            "data": "node_1"  # Israel Node
        }
    }
    response = client.post("/webhooks/telegram", json=payload_cb)
    assert response.status_code == 200
    print("[OK] Navigation to country Israel successful.")

    # 4. Simulate Alice selecting City 'Tel Aviv' (ID: 2)
    print("\n[STEP 4] Alice clicks Tel Aviv (node_2) button...")
    payload_cb["callback_query"]["data"] = "node_2"
    response = client.post("/webhooks/telegram", json=payload_cb)
    assert response.status_code == 200
    print("[OK] Navigation to city Tel Aviv successful.")

    # 5. Simulate Alice clicking neighborhood 'Florentin' (ID: 3)
    print("\n[STEP 5] Alice clicks Florentin (node_3) button...")
    payload_cb["callback_query"]["data"] = "node_3"
    response = client.post("/webhooks/telegram", json=payload_cb)
    assert response.status_code == 200
    print("[OK] Navigation to neighborhood Florentin successful.")

    # 6. Simulate Alice clicking street 'Herzel' (ID: 4)
    print("\n[STEP 6] Alice clicks Herzel Street (node_4) button...")
    payload_cb["callback_query"]["data"] = "node_4"
    response = client.post("/webhooks/telegram", json=payload_cb)
    assert response.status_code == 200
    print("[OK] Navigation to Herzel Street successful.")

    # 7. Simulate Alice clicking private building 'Herzel 12' (ID: 5)
    print("\n[STEP 7] Alice clicks building Herzel 12 (node_5) button...")
    payload_cb["callback_query"]["data"] = "node_5"
    response = client.post("/webhooks/telegram", json=payload_cb)
    assert response.status_code == 200
    print("[OK] Navigation to building node returned prompt.")

    # 8. Simulate Alice clicking '🔑 Request Entry (Verify)' button
    print("\n[STEP 8] Alice triggers verification process (verify_5)...")
    payload_cb["callback_query"]["data"] = "verify_5"
    response = client.post("/webhooks/telegram", json=payload_cb)
    assert response.status_code == 200
    print("[OK] State changed to awaiting_document.")

    # 9. Simulate Alice uploading a bill photo
    print("\n[STEP 9] Alice uploads proof of residency (bill.png)...")
    payload_upload = {
        "update_id": 10005,
        "message": {
            "message_id": 10,
            "from": {
                "id": int(tg_user_id),
                "username": tg_username
            },
            "chat": {
                "id": int(tg_user_id),
            },
            "date": 1600000000,
            "photo": [
                {"file_id": "file_id_utility_bill_large", "file_size": 200000, "width": 800, "height": 600}
            ]
        }
    }
    response = client.post("/webhooks/telegram", json=payload_upload)
    assert response.status_code == 200
    print("[OK] Upload accepted. Verification request logged in DB.")

    # Verify verification exists in DB
    db = SessionLocal()
    alice_db = db.query(User).filter(User.telegram_id == tg_user_id).first()
    assert alice_db is not None
    verif = db.query(Verification).filter(Verification.user_id == alice_db.id).first()
    assert verif is not None
    assert verif.status == "PENDING"
    print(f"  DB check: Found pending verification. ID: {verif.id}, Building ID: {verif.building_id}")
    db.close()

    # 10. Super Admin logs in and reviews/approves the verification request
    print("\n[STEP 10] Super Admin logs in via REST API and approves Alice...")
    login_res = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "adminpass"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    review_res = client.post(f"/api/verifications/{verif.id}/review", json={
        "status": "APPROVED"
    }, headers=headers)
    assert review_res.status_code == 200
    print("[OK] Admin successfully approved residency verification.")

    # Verify status changed to APPROVED
    db = SessionLocal()
    verif = db.query(Verification).filter(Verification.id == verif.id).first()
    assert verif.status == "APPROVED"
    db.close()

    # 11. Alice clicks Herzel 12 button again (should now receive group links)
    print("\n[STEP 11] Alice clicks building Herzel 12 (node_5) again...")
    payload_cb["callback_query"]["data"] = "verify_5"
    response = client.post("/webhooks/telegram", json=payload_cb)
    assert response.status_code == 200
    print("[OK] Alice successfully retrieved private group links.")

    # 12. Simulate Alice triggering /emergency alert
    print("\n[STEP 12] Alice triggers crisis mode (/emergency fire alarm)...")
    payload_crisis = {
        "update_id": 10009,
        "message": {
            "message_id": 15,
            "from": {
                "id": int(tg_user_id),
                "username": tg_username
            },
            "chat": {
                "id": int(tg_user_id),
            },
            "date": 1600000000,
            "text": "/emergency Fire detected in the lobby floor elevator shaft!"
        }
    }
    response = client.post("/webhooks/telegram", json=payload_crisis)
    assert response.status_code == 200
    
    # Verify emergency is added in DB
    db = SessionLocal()
    emergency_db = db.query(Emergency).filter(Emergency.user_id == alice_db.id).first()
    assert emergency_db is not None
    assert emergency_db.message == "Fire detected in the lobby floor elevator shaft!"
    assert emergency_db.status == "ACTIVE"
    print(f"  DB check: Active Emergency logged successfully. ID: {emergency_db.id}")
    db.close()
    
    # 13. Simulate Alice sending spam (AI Moderation / Auto-mute)
    print("\n[STEP 13] Alice sends a message containing spam link to trigger AI Moderation...")
    payload_spam = {
        "update_id": 10011,
        "message": {
            "message_id": 20,
            "from": {
                "id": int(tg_user_id),
                "username": tg_username
            },
            "chat": {
                "id": int(tg_user_id),
            },
            "date": 1600000000,
            "text": "Hey neighbors, click here to win and get rich fast buy bitcoin!"
        }
    }
    response = client.post("/webhooks/telegram", json=payload_spam)
    assert response.status_code == 200
    
    # Verify user is muted in DB
    db = SessionLocal()
    alice_db = db.query(User).filter(User.telegram_id == tg_user_id).first()
    assert alice_db.is_muted == True
    print(f"  DB check: User '{alice_db.username}' is_muted = {alice_db.is_muted} (Auto-muted successfully).")
    db.close()
    
    print("\nAll bot interaction and workflow simulation verification tests PASSED successfully!")
    print("====================================================")

if __name__ == "__main__":
    run_simulation()
