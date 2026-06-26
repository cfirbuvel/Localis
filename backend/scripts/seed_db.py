import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import SessionLocal
from backend import config
from backend.models import User, RoleAssignment
from backend.services.auth import get_password_hash

def seed():
    db = SessionLocal()
    try:
        # Create Super Admin User if it doesn't exist
        admin_username = config.SUPER_ADMIN_USERNAME
        exists = db.query(User).filter(User.username == admin_username).first()
        if not exists:
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

            # Assign Super Admin role
            print("Assigning SUPER_ADMIN role...")
            admin_role = RoleAssignment(
                user_id=admin.id,
                location_id=None,  # None means global (Super Admin)
                role="SUPER_ADMIN"
            )
            db.add(admin_role)
            db.commit()
            print("Super Admin seeded successfully!")
        else:
            print("Super Admin user already exists, skipping seeding.")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed()
