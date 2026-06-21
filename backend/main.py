import os
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend import config, models, schemas
from backend.database import get_db, engine
from backend.services import auth
from backend.services.location import (
    get_location_ancestors,
    get_location_descendants,
    is_descendant_of,
    auto_create_node_path
)

app = FastAPI(title="Global Neighborhood Platform API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# Authentication Dependency
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    payload = auth.verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been banned.",
        )
    return user

# Helper function to get maximum role of current user
def get_user_max_role(user: models.User, db: Session) -> str:
    assignments = db.query(models.RoleAssignment).filter(models.RoleAssignment.user_id == user.id).all()
    roles = [a.role for a in assignments]
    if "SUPER_ADMIN" in roles:
        return "SUPER_ADMIN"
    elif "MANAGER" in roles:
        return "MANAGER"
    elif "MODERATOR" in roles:
        return "MODERATOR"
    return "CITIZEN"

# Check if current user is authorized to perform action on a location
def check_user_hierarchy_permission(
    user: models.User,
    location_id: Optional[int],
    required_roles: List[str],
    db: Session
) -> bool:
    """
    Checks if the user has one of the required_roles on the location_id or any of its ancestors.
    If location_id is None, it checks for SUPER_ADMIN role.
    """
    # 1. Query all roles assigned to user
    roles_assigned = db.query(models.RoleAssignment).filter(models.RoleAssignment.user_id == user.id).all()
    
    # 2. Check for SUPER_ADMIN (global bypass)
    is_super = any(a.role == "SUPER_ADMIN" for a in roles_assigned)
    if is_super:
        return True
        
    if "SUPER_ADMIN" in required_roles and not is_super:
        return False
        
    if not location_id:
        return False

    # 3. Check for roles at specific node or any ancestor nodes
    ancestors = get_location_ancestors(db, location_id)
    target_nodes = [location_id] + ancestors

    for assign in roles_assigned:
        if assign.location_id in target_nodes:
            # If manager, can act as manager or moderator
            if assign.role == "MANAGER" and ("MANAGER" in required_roles or "MODERATOR" in required_roles):
                return True
            # If moderator, must match moderator requirement
            if assign.role == "MODERATOR" and "MODERATOR" in required_roles:
                return True
                
    return False

# ==========================================
# AUTHENTICATION ENDPOINTS
# ==========================================

@app.post("/api/auth/login", response_model=schemas.TokenResponse)
def login(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    # Check if Super Admin login
    if request.username == config.SUPER_ADMIN_USERNAME:
        # Find in DB
        admin_user = db.query(models.User).filter(models.User.username == config.SUPER_ADMIN_USERNAME).first()
        if admin_user and auth.verify_password(request.password, admin_user.password_hash):
            token = auth.create_access_token({"sub": admin_user.id})
            return {
                "access_token": token,
                "token_type": "bearer",
                "user": admin_user,
                "role": "SUPER_ADMIN"
            }

    # Standard User login (for managers/moderators who have a password)
    user = db.query(models.User).filter(models.User.username == request.username).first()
    if not user or not user.password_hash or not auth.verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    max_role = get_user_max_role(user, db)
    token = auth.create_access_token({"sub": user.id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
        "role": max_role
    }

# ==========================================
# USER DIRECTORY ENDPOINTS
# ==========================================

@app.get("/api/users", response_model=List[schemas.UserSearchResponse])
def search_users(
    q: Optional[str] = Query(None, description="Search query (username, phone number, telegram id)"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.User)
    if q:
        query = query.filter(
            (models.User.username.ilike(f"%{q}%")) |
            (models.User.phone_number.ilike(f"%{q}%")) |
            (models.User.telegram_id.ilike(f"%{q}%")) |
            (models.User.whatsapp_number.ilike(f"%{q}%"))
        )
    users = query.limit(50).all()
    
    # Map roles manually to populate names
    results = []
    for u in users:
        roles_mapped = []
        for assign in u.role_assignments:
            loc_name = assign.location.name if assign.location else "Global (System)"
            roles_mapped.append({
                "id": assign.id,
                "location_id": assign.location_id,
                "location_name": loc_name,
                "role": assign.role,
                "assigned_at": assign.assigned_at
            })
        results.append({
            "id": u.id,
            "username": u.username,
            "phone_number": u.phone_number,
            "telegram_id": u.telegram_id,
            "whatsapp_number": u.whatsapp_number,
            "is_banned": u.is_banned,
            "is_muted": u.is_muted,
            "roles": roles_mapped
        })
    return results

# ==========================================
# LOCATION HIERARCHY ENDPOINTS
# ==========================================

@app.get("/api/locations", response_model=List[schemas.LocationResponse])
def get_locations(
    parent_id: Optional[int] = None,
    level: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.LocationNode)
    if parent_id is not None:
        query = query.filter(models.LocationNode.parent_id == parent_id)
    if level is not None:
        query = query.filter(models.LocationNode.level == level)
    return query.all()

@app.post("/api/locations", response_model=schemas.LocationResponse)
def create_location(
    loc: schemas.LocationCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify permission: Must be MANAGER or SUPER_ADMIN on parent node
    if loc.parent_id:
        if not check_user_hierarchy_permission(current_user, loc.parent_id, ["MANAGER"], db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to add locations under this parent node."
            )
    else:
        # Creating a Country node requires Super Admin
        if not check_user_hierarchy_permission(current_user, None, ["SUPER_ADMIN"], db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Super Admins can create root Country nodes."
            )

    new_node = models.LocationNode(name=loc.name, level=loc.level, parent_id=loc.parent_id)
    db.add(new_node)
    db.commit()
    db.refresh(new_node)
    
    # Auto create public chats
    gtype = "PRIVATE" if loc.level == "BUILDING" else "PUBLIC"
    tg_chat_id = f"tg_chat_{loc.name.lower().replace(' ', '_')}"
    wa_chat_id = f"wa_chat_{loc.name.lower().replace(' ', '_')}"
    
    tg_group = models.GroupChat(location_id=new_node.id, platform="TELEGRAM", chat_id=tg_chat_id, type=gtype, invite_link=f"https://t.me/joinchat/{tg_chat_id}")
    wa_group = models.GroupChat(location_id=new_node.id, platform="WHATSAPP", chat_id=wa_chat_id, type=gtype, invite_link=f"https://chat.whatsapp.com/{wa_chat_id}")
    db.add(tg_group)
    db.add(wa_group)
    db.commit()
    db.refresh(new_node)
    
    return new_node

# ==========================================
# ROLE MANAGEMENT ENDPOINTS
# ==========================================

@app.post("/api/roles/assign", response_model=schemas.ActionResponse)
def assign_role(
    req: schemas.RoleAssignRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Authorize: Assigning a role requires matching permissions on the target node.
    if not req.location_id:
        # Assigning Super Admin requires Super Admin
        if not check_user_hierarchy_permission(current_user, None, ["SUPER_ADMIN"], db):
            raise HTTPException(status_code=403, detail="Only Super Admins can assign other Super Admins.")
    else:
        # Assigning Manager/Moderator on location requires Manager on that node or parent nodes
        if not check_user_hierarchy_permission(current_user, req.location_id, ["MANAGER"], db):
            raise HTTPException(status_code=403, detail="You do not have manager privileges to assign roles at this location.")

    # 2. Prevent moderator from assigning roles (already handled by role permission check)
    # 3. Create role assignment
    user_to_assign = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user_to_assign:
         raise HTTPException(status_code=404, detail="User to assign not found.")

    # Check if duplicate assignment
    dup = db.query(models.RoleAssignment).filter(
        models.RoleAssignment.user_id == req.user_id,
        models.RoleAssignment.location_id == req.location_id,
        models.RoleAssignment.role == req.role
    ).first()
    if dup:
        return {"success": True, "message": "User already has this role assignment."}

    # Ensure standard user has password_hash to login if they are becoming manager/mod
    if not user_to_assign.password_hash:
        user_to_assign.password_hash = auth.get_password_hash("defaultpass123")
        db.add(user_to_assign)

    new_assign = models.RoleAssignment(
        user_id=req.user_id,
        location_id=req.location_id,
        role=req.role
    )
    db.add(new_assign)
    db.commit()
    return {"success": True, "message": f"Successfully assigned {req.role} role to user."}

# ==========================================
# VERIFICATION PIPELINE ENDPOINTS
# ==========================================

@app.get("/api/verifications/pending", response_model=List[schemas.VerificationResponse])
def get_pending_verifications(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Find locations current user manages/moderates
    roles = db.query(models.RoleAssignment).filter(models.RoleAssignment.user_id == current_user.id).all()
    is_super = any(r.role == "SUPER_ADMIN" for r in roles)
    
    if is_super:
        # Super Admin sees all
        verifs = db.query(models.Verification).filter(models.Verification.status == "PENDING").all()
    else:
        # Managers and moderators see verifications for buildings in their location branches
        managed_location_ids = [r.location_id for r in roles if r.location_id is not None]
        descendant_ids = set()
        for lid in managed_location_ids:
            descendant_ids.add(lid)
            descendant_ids.update(get_location_descendants(db, lid))
            
        verifs = db.query(models.Verification).filter(
            models.Verification.status == "PENDING",
            models.Verification.building_id.in_(list(descendant_ids))
        ).all()

    # Map details manually to include building names
    results = []
    for v in verifs:
        results.append({
            "id": v.id,
            "user": v.user,
            "building_id": v.building_id,
            "building_name": v.building.name,
            "proof_url": v.proof_url,
            "status": v.status,
            "rejection_reason": v.rejection_reason,
            "created_at": v.created_at,
            "updated_at": v.updated_at
        })
    return results

@app.post("/api/verifications/{verification_id}/review", response_model=schemas.ActionResponse)
def review_verification(
    verification_id: int,
    review: schemas.VerificationReview,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    v = db.query(models.Verification).filter(models.Verification.id == verification_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Verification request not found.")

    # Check permission: Must have Moderator/Manager role on the building node or ancestors
    if not check_user_hierarchy_permission(current_user, v.building_id, ["MODERATOR", "MANAGER"], db):
        raise HTTPException(status_code=403, detail="You do not have permission to moderate this building's queue.")

    v.status = review.status
    v.reviewed_by = current_user.id
    v.rejection_reason = review.rejection_reason
    db.commit()

    # Trigger sending invite link if approved
    if review.status == "APPROVED":
        # Find building group invite links
        groups = db.query(models.GroupChat).filter(
            models.GroupChat.location_id == v.building_id,
            models.GroupChat.type == "PRIVATE"
        ).all()
        # In a real app: Send API message to User via Bot
        print(f"[BOT OUTBOX] Approved verification. Sending citizen building links: {[g.invite_link for g in groups]}")
        
    return {"success": True, "message": f"Verification request has been {review.status}."}

# ==========================================
# EMERGENCY & MODERATION LOG ENDPOINTS
# ==========================================

@app.get("/api/emergencies", response_model=List[schemas.EmergencyResponse])
def get_emergencies(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    roles = db.query(models.RoleAssignment).filter(models.RoleAssignment.user_id == current_user.id).all()
    is_super = any(r.role == "SUPER_ADMIN" for r in roles)
    
    if is_super:
        emergencies = db.query(models.Emergency).order_by(models.Emergency.created_at.desc()).all()
    else:
        managed_location_ids = [r.location_id for r in roles if r.location_id is not None]
        descendant_ids = set()
        for lid in managed_location_ids:
            descendant_ids.add(lid)
            descendant_ids.update(get_location_descendants(db, lid))
            
        # Also include ancestors so local managers know if an emergency was registered for their child locations
        emergencies = db.query(models.Emergency).filter(
            models.Emergency.location_id.in_(list(descendant_ids))
        ).order_by(models.Emergency.created_at.desc()).all()

    results = []
    for e in emergencies:
        results.append({
            "id": e.id,
            "user": e.user,
            "location_id": e.location_id,
            "location_name": e.location.name,
            "message": e.message,
            "status": e.status,
            "created_at": e.created_at
        })
    return results

@app.post("/api/emergencies/resolve/{id}", response_model=schemas.ActionResponse)
def resolve_emergency(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    e = db.query(models.Emergency).filter(models.Emergency.id == id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Emergency not found.")

    if not check_user_hierarchy_permission(current_user, e.location_id, ["MODERATOR", "MANAGER"], db):
        raise HTTPException(status_code=403, detail="You do not have permission to moderate reports at this location.")

    e.status = "RESOLVED"
    db.commit()
    return {"success": True, "message": "Emergency marked as resolved."}

@app.get("/api/moderation/logs", response_model=List[schemas.ModerationLogResponse])
def get_moderation_logs(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    roles = db.query(models.RoleAssignment).filter(models.RoleAssignment.user_id == current_user.id).all()
    is_super = any(r.role == "SUPER_ADMIN" for r in roles)
    
    if is_super:
        logs = db.query(models.ModerationLog).order_by(models.ModerationLog.flagged_at.desc()).all()
    else:
        managed_location_ids = [r.location_id for r in roles if r.location_id is not None]
        descendant_ids = set()
        for lid in managed_location_ids:
            descendant_ids.add(lid)
            descendant_ids.update(get_location_descendants(db, lid))
            
        logs = db.query(models.ModerationLog).filter(
            models.ModerationLog.location_id.in_(list(descendant_ids))
        ).order_by(models.ModerationLog.flagged_at.desc()).all()

    results = []
    for l in logs:
        results.append({
            "id": l.id,
            "location_id": l.location_id,
            "location_name": l.location.name if l.location else "System",
            "user": l.user,
            "message_text": l.message_text,
            "ai_analysis": l.ai_analysis,
            "flagged_at": l.flagged_at
        })
    return results

# ==========================================
# CITIZEN PUNISHMENT ENDPOINTS
# ==========================================

@app.post("/api/users/{user_id}/ban", response_model=schemas.ActionResponse)
def ban_user(
    user_id: str,
    ban: bool = True,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    # Only managers/super admin can ban
    # To check permission, we need to know the target context. Since bans are global/local, 
    # let's require SUPER_ADMIN or general MANAGER role.
    if not check_user_hierarchy_permission(current_user, None, ["SUPER_ADMIN"], db):
        # Fallback: check if the manager manages at least one location (is not a simple citizen)
        mgr_assignments = db.query(models.RoleAssignment).filter(
            models.RoleAssignment.user_id == current_user.id,
            models.RoleAssignment.role == "MANAGER"
        ).all()
        if not mgr_assignments:
            raise HTTPException(status_code=403, detail="Only managers or super admins can ban users.")

    target.is_banned = ban
    db.commit()
    
    # In a real app: Trigger Bot API kick out of all groups
    action = "banned" if ban else "unbanned"
    print(f"[BOT ACTIONS] User {target.username} has been {action} by admin.")
    
    return {"success": True, "message": f"User successfully {action}."}

@app.post("/api/users/{user_id}/mute", response_model=schemas.ActionResponse)
def mute_user(
    user_id: str,
    mute: bool = True,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    # Requires same permission level as ban
    if not check_user_hierarchy_permission(current_user, None, ["SUPER_ADMIN"], db):
        mgr_assignments = db.query(models.RoleAssignment).filter(
            models.RoleAssignment.user_id == current_user.id,
            models.RoleAssignment.role == "MANAGER"
        ).all()
        if not mgr_assignments:
            raise HTTPException(status_code=403, detail="Only managers or super admins can mute users.")

    target.is_muted = mute
    db.commit()
    
    # In a real app: Trigger Bot API mute in group permissions
    action = "muted" if mute else "unmuted"
    print(f"[BOT ACTIONS] User {target.username} has been {action} by admin.")
    
    return {"success": True, "message": f"User successfully {action}."}

# ==========================================
# TELEGRAM / WHATSAPP BOT WEBHOOK MOCKS (Stubs)
# ==========================================

@app.post("/webhooks/telegram")
async def telegram_webhook(payload: dict, db: Session = Depends(get_db)):
    from backend.services.bot_telegram import handle_telegram_update
    await handle_telegram_update(payload, db)
    return {"status": "ok"}

@app.get("/webhooks/whatsapp")
async def whatsapp_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    if hub_verify_token == config.WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Invalid verify token")

@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(payload: dict, db: Session = Depends(get_db)):
    from backend.services.bot_whatsapp import handle_whatsapp_webhook
    await handle_whatsapp_webhook(payload, db)
    return {"status": "ok"}

