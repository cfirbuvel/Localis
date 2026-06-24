import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_CHATS_URL = os.getenv("DATABASE_CHATS_URL", "sqlite:///./chats.db")

# For SQLite, specify connect_args
if DATABASE_CHATS_URL.startswith("sqlite"):
    engine_chats = create_engine(
        DATABASE_CHATS_URL, connect_args={"check_same_thread": False}
    )
else:
    engine_chats = create_engine(DATABASE_CHATS_URL)

SessionLocalChats = sessionmaker(autocommit=False, autoflush=False, bind=engine_chats)

BaseChats = declarative_base()

class ChatMessage(BaseChats):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False)      # 'TELEGRAM', 'WHATSAPP'
    chat_id = Column(String(100), nullable=False, index=True)      # Group Chat JID/ID
    user_id = Column(String(100), nullable=False, index=True)      # Sender Platform ID
    username = Column(String(100), nullable=True)
    message_text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

# Create tables
BaseChats.metadata.create_all(bind=engine_chats)

def get_db_chats():
    db = SessionLocalChats()
    try:
        yield db
    finally:
        db.close()
