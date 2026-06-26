import os
import sys

# Add the parent directory of backend to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import SessionLocal
from backend import config
from backend.models import User, LocationNode, GroupChat, RoleAssignment, Verification, Emergency, CommunityRequest
from backend.services.auth import get_password_hash
from backend.database_chats import SessionLocalChats, ChatMessage

def clean():
    print("Purging all mock/fake locations and active data from neighborhoods.db...")
    db = SessionLocal()
    try:
        db.query(RoleAssignment).delete()
        db.query(Verification).delete()
        db.query(Emergency).delete()
        db.query(GroupChat).delete()
        db.query(LocationNode).delete()
        db.query(CommunityRequest).delete()
        db.query(User).delete()
        db.commit()

        # Re-create Super Admin
        admin_username = config.SUPER_ADMIN_USERNAME
        print(f"Re-creating Super Admin user: {admin_username}")
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
        admin_role = RoleAssignment(
            user_id=admin.id,
            location_id=None,
            role="SUPER_ADMIN"
        )
        db.add(admin_role)
        db.commit()
        print("Super Admin re-created and assigned role successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error cleaning neighborhoods database: {e}")
        raise e
    finally:
        db.close()

    print("Purging all chat message logs from chats.db...")
    chats_db = SessionLocalChats()
    try:
        chats_db.query(ChatMessage).delete()
        chats_db.commit()
        print("Chats database purged successfully.")
    except Exception as e:
        chats_db.rollback()
        print(f"Error cleaning chats database: {e}")
    finally:
        chats_db.close()

    print("Database cleanup completed successfully!")

if __name__ == "__main__":
    clean()
