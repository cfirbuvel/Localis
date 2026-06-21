import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    ForeignKeyConstraint
)
from sqlalchemy.orm import relationship
from backend.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    telegram_id = Column(String(50), unique=True, nullable=True, index=True)
    whatsapp_number = Column(String(50), unique=True, nullable=True, index=True)
    username = Column(String(100), nullable=True)
    phone_number = Column(String(50), nullable=True)
    is_banned = Column(Boolean, default=False)
    is_muted = Column(Boolean, default=False)
    password_hash = Column(String(255), nullable=True)  # Used for manager login to the dashboard
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    role_assignments = relationship("RoleAssignment", back_populates="user", cascade="all, delete-orphan")
    verifications = relationship("Verification", foreign_keys="Verification.user_id", back_populates="user")
    reviewed_verifications = relationship("Verification", foreign_keys="Verification.reviewed_by", back_populates="reviewer")
    emergencies = relationship("Emergency", back_populates="user")

class LocationNode(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    level = Column(String(20), nullable=False)  # 'COUNTRY', 'CITY', 'NEIGHBORHOOD', 'STREET', 'BUILDING'
    parent_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=True)

    # Relationships
    parent = relationship("LocationNode", remote_side=[id], backref="children")
    groups = relationship("GroupChat", back_populates="location", cascade="all, delete-orphan")
    role_assignments = relationship("RoleAssignment", back_populates="location", cascade="all, delete-orphan")
    verifications = relationship("Verification", back_populates="building", cascade="all, delete-orphan")
    emergencies = relationship("Emergency", back_populates="location", cascade="all, delete-orphan")

class GroupChat(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(20), nullable=False)  # 'TELEGRAM', 'WHATSAPP'
    chat_id = Column(String(100), nullable=False)  # Telegram chat ID or WhatsApp contact group JID
    type = Column(String(20), nullable=False)  # 'PUBLIC', 'PRIVATE', 'EMERGENCY'
    invite_link = Column(String(255), nullable=True)

    # Relationships
    location = relationship("LocationNode", back_populates="groups")

class RoleAssignment(Base):
    __tablename__ = "role_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=True)  # Null indicates global access (Super Admin)
    role = Column(String(20), nullable=False)  # 'SUPER_ADMIN', 'MANAGER', 'MODERATOR'
    assigned_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="role_assignments")
    location = relationship("LocationNode", back_populates="role_assignments")

class Verification(Base):
    __tablename__ = "verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    building_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False)
    proof_url = Column(String(255), nullable=False)  # File path or remote url
    status = Column(String(20), default="PENDING")  # 'PENDING', 'APPROVED', 'REJECTED'
    reviewed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejection_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="verifications")
    building = relationship("LocationNode", back_populates="verifications")
    reviewer = relationship("User", foreign_keys=[reviewed_by], back_populates="reviewed_verifications")

class Emergency(Base):
    __tablename__ = "emergencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), default="ACTIVE")  # 'ACTIVE', 'RESOLVED'
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="emergencies")
    location = relationship("LocationNode", back_populates="emergencies")

class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    message_text = Column(Text, nullable=False)
    ai_analysis = Column(JSON, nullable=True)  # JSON field representing categories and raw text scores
    flagged_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    location = relationship("LocationNode")
    user = relationship("User")
