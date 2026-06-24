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
