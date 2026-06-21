import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import User, LocationNode, RoleAssignment
from backend.services.auth import get_password_hash

client = TestClient(app)

def test_flow():
    print("Starting API integration verification tests (In-Memory)...")

    # 1. Login with Super Admin credentials
    print("Testing Login...")
    response = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "adminpass"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    token_data = response.json()
    token = token_data["access_token"]
    print("[OK] Super Admin login successful.")

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get location hierarchy
    print("Testing Location Retrieval...")
    response = client.get("/api/locations", headers=headers)
    assert response.status_code == 200
    locations = response.json()
    assert len(locations) > 0
    print(f"[OK] Found {len(locations)} seeded locations.")
    
    # Grab the City node 'Tel Aviv'
    city_node = next(l for l in locations if l["level"] == "CITY" and l["name"] == "Tel Aviv")
    print(f"  Target city node: {city_node['name']} (ID: {city_node['id']})")

    # 3. Create a new neighborhood under Tel Aviv
    print("Testing Location Creation under City...")
    response = client.post("/api/locations", json={
        "name": "Neve Tzedek",
        "level": "NEIGHBORHOOD",
        "parent_id": city_node["id"]
    }, headers=headers)
    assert response.status_code == 200
    new_loc = response.json()
    assert new_loc["name"] == "Neve Tzedek"
    print("[OK] Successfully created location 'Neve Tzedek'.")

    # 4. Search users
    print("Testing User Searching...")
    response = client.get("/api/users?q=admin", headers=headers)
    assert response.status_code == 200
    users = response.json()
    assert len(users) > 0
    admin_user_id = users[0]["id"]
    print(f"[OK] Found admin user. ID: {admin_user_id}")

    # 5. Create a test citizen and assign them to be Manager of Neve Tzedek
    print("Seeding test manager...")
    db = SessionLocal()
    test_user = db.query(User).filter(User.username == "florentin_manager").first()
    if not test_user:
        test_user = User(
            username="florentin_manager",
            password_hash=get_password_hash("managerpass"),
            phone_number="+972541111111"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
    db.close()

    print("Testing Manager Assignment...")
    response = client.post("/api/roles/assign", json={
        "user_id": test_user.id,
        "location_id": new_loc["id"],
        "role": "MANAGER"
    }, headers=headers)
    assert response.status_code == 200
    print("[OK] Successfully assigned MANAGER role to 'florentin_manager' for Neve Tzedek.")

    # 6. Test permission boundary: Log in as florentin_manager and try to add a street under Neve Tzedek (should succeed)
    print("Testing Manager login and parent permission inheritance...")
    login_res = client.post("/api/auth/login", json={
        "username": "florentin_manager",
        "password": "managerpass"
    })
    assert login_res.status_code == 200
    mgr_token = login_res.json()["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    response = client.post("/api/locations", json={
        "name": "Shabazi Street",
        "level": "STREET",
        "parent_id": new_loc["id"]
    }, headers=mgr_headers)
    assert response.status_code == 200, f"Manager failed to add child street: {response.text}"
    print("[OK] Success: florentin_manager created Shabazi Street under Neve Tzedek.")

    # 7. Test permission boundary: Try to add a street under Florentin (should FAIL because manager is only for Neve Tzedek)
    florentin_node = next(l for l in locations if l["level"] == "NEIGHBORHOOD" and l["name"] == "Florentin")
    print("Testing forbidden boundary (adding location in neighbor branch)...")
    response = client.post("/api/locations", json={
        "name": "Unauthorized Street",
        "level": "STREET",
        "parent_id": florentin_node["id"]
    }, headers=mgr_headers)
    assert response.status_code == 403
    print("[OK] Success: florentin_manager blocked from editing Florentin branch (403 Forbidden).")

    print("\nAll integration verification tests PASSED successfully!")

if __name__ == "__main__":
    test_flow()
