import asyncio
from datetime import datetime, timedelta
from backend.database_chats import SessionLocalChats, ChatMessage

async def start_retention_worker():
    """Background task that runs every 24 hours to delete chat logs older than 14 days."""
    while True:
        try:
            print("[Retention Worker] Running chat history cleanup...")
            db = SessionLocalChats()
            limit_date = datetime.utcnow() - timedelta(days=14)
            # Delete messages older than 14 days
            deleted = db.query(ChatMessage).filter(ChatMessage.timestamp < limit_date).delete()
            db.commit()
            print(f"[Retention Worker] Deleted {deleted} chat messages older than 14 days.")
            db.close()
        except Exception as e:
            print(f"[Retention Worker Error] Cleanup failed: {e}")
        
        # Sleep for 24 hours (86400 seconds)
        await asyncio.sleep(86400)
