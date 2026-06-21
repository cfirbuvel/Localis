import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import SessionLocal
from backend import config
from backend.models import User, LocationNode, GroupChat, RoleAssignment
from backend.services.auth import get_password_hash

def seed():
    db = SessionLocal()
    try:
        print("Seeding database...")

        # 1. Create Super Admin User if not exists
        admin_username = config.SUPER_ADMIN_USERNAME
        admin = db.query(User).filter(User.username == admin_username).first()
        if not admin:
            print(f"Creating Super Admin user: {admin_username}")
            admin = User(
                username=admin_username,
                telegram_id=config.SUPER_ADMIN_TELEGRAM_ID,
                whatsapp_number=config.SUPER_ADMIN_PHONE,
                phone_number=config.SUPER_ADMIN_PHONE,
                password_hash=get_password_hash(config.SUPER_ADMIN_PASSWORD)
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        else:
            print(f"Super Admin user {admin_username} already exists.")

        # 2. Assign Super Admin role
        admin_role = db.query(RoleAssignment).filter(
            RoleAssignment.user_id == admin.id,
            RoleAssignment.role == "SUPER_ADMIN"
        ).first()
        if not admin_role:
            print("Assigning SUPER_ADMIN role...")
            admin_role = RoleAssignment(
                user_id=admin.id,
                location_id=None,  # None means global (Super Admin)
                role="SUPER_ADMIN"
            )
            db.add(admin_role)
            db.commit()
        else:
            print("SUPER_ADMIN role already assigned.")

        # 3. Create Default Hierarchy: Country -> City -> Neighborhood -> Street -> Building
        # Country
        country = db.query(LocationNode).filter(LocationNode.level == "COUNTRY", LocationNode.name == "Israel").first()
        if not country:
            print("Seeding country: Israel")
            country = LocationNode(name="Israel", level="COUNTRY", parent_id=None)
            db.add(country)
            db.commit()
            db.refresh(country)

        # City
        city = db.query(LocationNode).filter(LocationNode.level == "CITY", LocationNode.name == "Tel Aviv").first()
        if not city:
            print("Seeding city: Tel Aviv")
            city = LocationNode(name="Tel Aviv", level="CITY", parent_id=country.id)
            db.add(city)
            db.commit()
            db.refresh(city)

        # Neighborhood
        neighborhood = db.query(LocationNode).filter(LocationNode.level == "NEIGHBORHOOD", LocationNode.name == "Florentin").first()
        if not neighborhood:
            print("Seeding neighborhood: Florentin")
            neighborhood = LocationNode(name="Florentin", level="NEIGHBORHOOD", parent_id=city.id)
            db.add(neighborhood)
            db.commit()
            db.refresh(neighborhood)

        # Street
        street = db.query(LocationNode).filter(LocationNode.level == "STREET", LocationNode.name == "Herzel").first()
        if not street:
            print("Seeding street: Herzel")
            street = LocationNode(name="Herzel", level="STREET", parent_id=neighborhood.id)
            db.add(street)
            db.commit()
            db.refresh(street)

        # Building
        building = db.query(LocationNode).filter(LocationNode.level == "BUILDING", LocationNode.name == "Herzel 12").first()
        if not building:
            print("Seeding building: Herzel 12")
            building = LocationNode(name="Herzel 12", level="BUILDING", parent_id=street.id)
            db.add(building)
            db.commit()
            db.refresh(building)

        # 4. Create Group Chats associated with these locations
        nodes_info = [
            (country, "PUBLIC", "tg_chat_israel", "wa_chat_israel"),
            (city, "PUBLIC", "tg_chat_tel_aviv", "wa_chat_tel_aviv"),
            (neighborhood, "PUBLIC", "tg_chat_florentin", "wa_chat_florentin"),
            (street, "PUBLIC", "tg_chat_herzel", "wa_chat_herzel"),
            (building, "PRIVATE", "tg_chat_herzel_12_private", "wa_chat_herzel_12_private")
        ]

        for node, gtype, tg_chat_id, wa_chat_id in nodes_info:
            # Check Telegram group
            tg_group = db.query(GroupChat).filter(
                GroupChat.location_id == node.id,
                GroupChat.platform == "TELEGRAM"
            ).first()
            if not tg_group:
                print(f"Creating Telegram {gtype} group for {node.name} ({node.level})")
                tg_group = GroupChat(
                    location_id=node.id,
                    platform="TELEGRAM",
                    chat_id=tg_chat_id,
                    type=gtype,
                    invite_link=f"https://t.me/joinchat/{tg_chat_id}"
                )
                db.add(tg_group)

            # Check WhatsApp group
            wa_group = db.query(GroupChat).filter(
                GroupChat.location_id == node.id,
                GroupChat.platform == "WHATSAPP"
            ).first()
            if not wa_group:
                print(f"Creating WhatsApp {gtype} group for {node.name} ({node.level})")
                wa_group = GroupChat(
                    location_id=node.id,
                    platform="WHATSAPP",
                    chat_id=wa_chat_id,
                    type=gtype,
                    invite_link=f"https://chat.whatsapp.com/{wa_chat_id}"
                )
                db.add(wa_group)

        db.commit()
        print("Database seeded successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed()
