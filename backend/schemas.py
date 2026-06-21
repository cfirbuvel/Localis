from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Auth Schemas
class LoginRequest(BaseModel):
    username: str
    password: str

class UserMini(BaseModel):
    id: str
    username: str
    phone_number: Optional[str] = None
    telegram_id: Optional[str] = None
    whatsapp_number: Optional[str] = None
    is_banned: bool
    is_muted: bool

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserMini
    role: str  # Maximum role: 'SUPER_ADMIN', 'MANAGER', 'MODERATOR', or 'CITIZEN'

# User Management Schemas
class RoleAssignmentResponse(BaseModel):
    id: int
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    role: str
    assigned_at: datetime

    class Config:
        from_attributes = True

class UserSearchResponse(BaseModel):
    id: str
    username: Optional[str] = None
    phone_number: Optional[str] = None
    telegram_id: Optional[str] = None
    whatsapp_number: Optional[str] = None
    is_banned: bool
    is_muted: bool
    roles: List[RoleAssignmentResponse] = []

    class Config:
        from_attributes = True

# Role Assignment Request
class RoleAssignRequest(BaseModel):
    user_id: str
    location_id: Optional[int] = None  # None for SUPER_ADMIN (only set by another Super Admin)
    role: str  # 'MANAGER', 'MODERATOR'

# Location Schemas
class LocationCreate(BaseModel):
    name: str
    level: str  # 'COUNTRY', 'CITY', 'NEIGHBORHOOD', 'STREET', 'BUILDING'
    parent_id: Optional[int] = None

class GroupChatResponse(BaseModel):
    id: int
    platform: str
    chat_id: str
    type: str
    invite_link: Optional[str] = None

    class Config:
        from_attributes = True

class LocationResponse(BaseModel):
    id: int
    name: str
    level: str
    parent_id: Optional[int] = None
    groups: List[GroupChatResponse] = []

    class Config:
        from_attributes = True

# Verification Schemas
class VerificationResponse(BaseModel):
    id: int
    user: UserMini
    building_id: int
    building_name: str
    proof_url: str
    status: str
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class VerificationReview(BaseModel):
    status: str  # 'APPROVED', 'REJECTED'
    rejection_reason: Optional[str] = None

# Emergency Schemas
class EmergencyCreate(BaseModel):
    location_id: int
    message: str

class EmergencyResponse(BaseModel):
    id: int
    user: UserMini
    location_id: int
    location_name: str
    message: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Moderation Logs
class ModerationLogResponse(BaseModel):
    id: int
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    user: Optional[UserMini] = None
    message_text: str
    ai_analysis: Optional[dict] = None
    flagged_at: datetime

    class Config:
        from_attributes = True

class ActionResponse(BaseModel):
    success: bool
    message: str
