import os
import sys

# Add the parent directory of backend to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import Base, engine
from backend.models import User, LocationNode, GroupChat, RoleAssignment, Verification, Emergency, ModerationLog

def main():
    print("Initializing SQLite database...")
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized successfully.")

if __name__ == "__main__":
    main()
