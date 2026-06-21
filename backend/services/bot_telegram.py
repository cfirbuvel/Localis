import os
import sys
import httpx
from typing import Optional
from sqlalchemy.orm import Session
from backend import config, models

from backend.services.location import get_location_ancestors, get_location_descendants

# In-memory session states for bot users
# Format: {telegram_id: {"node_id": int, "action": str}}
# Action can be 'awaiting_document' or 'awaiting_node_name'
USER_STATES = {}

def get_or_create_user(db: Session, telegram_id: str, username: Optional[str] = None) -> models.User:
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        # Create standard citizen user
        user = models.User(
            telegram_id=telegram_id,
            username=username or f"TG_{telegram_id}",
            phone_number=None
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def safe_print(msg: str):
    """Print safely on Windows consoles with limited encoding (e.g. cp1255)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8', errors='replace'))

async def send_telegram_request(method: str, payload: dict) -> bool:
    """Sends a request to the real Telegram Bot API if token is configured."""
    token = config.TELEGRAM_BOT_TOKEN
    # Detect missing or clearly placeholder token
    if not token or ":" not in token:
        safe_print(f"[TELEGRAM MOCK SEND] method={method}")
        return True
    
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, timeout=10.0)
            safe_print(f"[TELEGRAM API RESPONSE] status={res.status_code} body={res.text[:150]}")
            return res.status_code == 200
    except Exception as e:
        safe_print(f"[TELEGRAM API ERROR] Failed to call {method}: {e}")
        return False

async def send_message(chat_id: str, text: str, reply_markup: dict = None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    await send_telegram_request("sendMessage", payload)

async def handle_telegram_update(update: dict, db: Session):
    """
    Core entrypoint for processing Telegram bot updates.
    Handles messages, commands, and callback queries.
    """
    if "callback_query" in update:
        await handle_callback_query(update["callback_query"], db)
        return

    if "message" not in update:
        return

    message = update["message"]
    chat_id = str(message["chat"]["id"])
    text = message.get("text", "")
    from_user = message.get("from", {})
    username = from_user.get("username")
    telegram_id = str(from_user.get("id", chat_id))

    user = get_or_create_user(db, telegram_id, username)
    if user.is_banned:
        await send_message(chat_id, "❌ Your account is banned from using this service.")
        return

    # 1. Handle user actions/state machines
    state = USER_STATES.get(telegram_id, {})
    
    # Audit message text using AI moderator (excluding commands)
    if text and not text.startswith("/"):
        from backend.services.ai_moderator import audit_user_message
        is_flagged = await audit_user_message(db, user.id, state.get("node_id"), text)
        if is_flagged:
            db.refresh(user)
            if user.is_muted:
                await send_message(chat_id, "⚠️ *Inappropriate Content Flagged!*\nYou have been muted by the AI Moderator.")
                return

    # Action: Awaiting photo/file proof upload for Building verification
    if state.get("action") == "awaiting_document":
        document_url = None
        
        # Check if photo or document uploaded
        if "photo" in message:
            # Grab highest resolution photo
            photo = message["photo"][-1]
            file_id = photo["file_id"]
            document_url = f"telegram_file_id:{file_id}"
        elif "document" in message:
            file_id = message["document"]["file_id"]
            document_url = f"telegram_file_id:{file_id}"

        if document_url:
            building_id = state.get("node_id")
            building = db.query(models.LocationNode).filter(models.LocationNode.id == building_id).first()
            
            # Save verification request in database
            verif = models.Verification(
                user_id=user.id,
                building_id=building_id,
                proof_url=document_url,
                status="PENDING"
            )
            db.add(verif)
            db.commit()

            # Clear state
            USER_STATES[telegram_id] = {}
            
            await send_message(
                chat_id,
                f"✅ *Document Received!*\nYour request to join *{building.name}* is pending review by local managers. You will receive an invite link once approved."
            )
            
            # Alert nearby managers (in simulation)
            print(f"[SYSTEM ALERT] Verification pending for building '{building.name}' by user '{user.username}'.")
            return
        else:
            await send_message(chat_id, "⚠️ Please upload an image or utility bill document. Or type /cancel to abort.")
            return

    # Action: Awaiting manual location creation name
    if state.get("action") == "awaiting_node_name":
        if text.startswith("/"):
            USER_STATES[telegram_id] = {}
        else:
            parent_id = state.get("node_id")
            parent_node = db.query(models.LocationNode).filter(models.LocationNode.id == parent_id).first()
            
            # Determine child level
            parent_level = parent_node.level
            level_map = {
                "COUNTRY": "CITY",
                "CITY": "NEIGHBORHOOD",
                "NEIGHBORHOOD": "STREET",
                "STREET": "BUILDING"
            }
            child_level = level_map.get(parent_level)
            
            if not child_level:
                await send_message(chat_id, "❌ Cannot add more levels here.")
                USER_STATES[telegram_id] = {}
                return

            # Create node
            node_name = text.strip()
            new_node = models.LocationNode(
                name=node_name,
                level=child_level,
                parent_id=parent_id
            )
            db.add(new_node)
            db.commit()
            db.refresh(new_node)

            # Auto create public/private mock groupchats
            gtype = "PRIVATE" if child_level == "BUILDING" else "PUBLIC"
            tg_chat_id = f"tg_chat_{node_name.lower().replace(' ', '_')}"
            wa_chat_id = f"wa_chat_{node_name.lower().replace(' ', '_')}"
            
            tg_group = models.GroupChat(location_id=new_node.id, platform="TELEGRAM", chat_id=tg_chat_id, type=gtype, invite_link=f"https://t.me/joinchat/{tg_chat_id}")
            wa_group = models.GroupChat(location_id=new_node.id, platform="WHATSAPP", chat_id=wa_chat_id, type=gtype, invite_link=f"https://chat.whatsapp.com/{wa_chat_id}")
            db.add(tg_group)
            db.add(wa_group)
            db.commit()

            # Clear state and show keyboard for new node
            USER_STATES[telegram_id] = {}
            await send_message(chat_id, f"✅ Created new {child_level.lower()}: *{node_name}*")
            await show_location_node(chat_id, new_node.id, db)
            return

    # 2. Command Handlers
    if text == "/start":
        await send_message(
            chat_id,
            "🌍 *Welcome to the Global Neighborhood Platform!*\n\nThis platform connects countries, cities, neighborhoods, and buildings securely.\n\nCommands:\n/browse - Explore location groups\n/emergency <desc> - Alert neighborhood managers",
            reply_markup={
                "inline_keyboard": [[
                    {"text": "🗺️ Browse Locations", "callback_data": "browse_root"}
                ]]
            }
        )
        return

    if text == "/browse":
        await show_root_locations(chat_id, db)
        return

    if text.startswith("/emergency"):
        desc = text[len("/emergency"):].strip()
        if not desc:
            await send_message(chat_id, "⚠️ Please specify a description. Example: `/emergency Fire on third floor of Herzel 12`")
            return

        # Fetch user's last navigated location or default to Country root
        user_node_id = state.get("node_id", 1)  # Default node is 1 (Israel)
        emergency = models.Emergency(
            user_id=user.id,
            location_id=user_node_id,
            message=desc,
            status="ACTIVE"
        )
        db.add(emergency)
        db.commit()

        # Get node
        node = db.query(models.LocationNode).filter(models.LocationNode.id == user_node_id).first()
        
        await send_message(
            chat_id,
            f"🚨 *Crisis Alert Sent!*\nAll regional managers of *{node.name}* and emergency services have been alerted. AI moderator is coordinating."
        )

        # Broadcast crisis (in simulation)
        print(f"[CRISIS ALERTS] User {user.username} raised emergency at {node.name} ({node.level}): {desc}")
        return

    if text == "/cancel":
        USER_STATES[telegram_id] = {}
        await send_message(chat_id, "🛑 Action cancelled. Use /browse to continue.")
        return

    # Default fallback
    await send_message(chat_id, "🤖 Command not recognized. Type /browse to browse locations.")

async def show_root_locations(chat_id: str, db: Session):
    countries = db.query(models.LocationNode).filter(models.LocationNode.level == "COUNTRY").all()
    
    keyboard = []
    for c in countries:
        keyboard.append([{"text": f"📍 {c.name}", "callback_data": f"node_{c.id}"}])

    await send_message(
        chat_id,
        "🗺️ *Select your Country:*",
        reply_markup={"inline_keyboard": keyboard}
    )

async def show_location_node(chat_id: str, node_id: int, db: Session):
    node = db.query(models.LocationNode).filter(models.LocationNode.id == node_id).first()
    if not node:
        await send_message(chat_id, "❌ Location not found.")
        return

    # Track last navigated location node
    # Find user ID based on chat_id
    user = db.query(models.User).filter(models.User.telegram_id == chat_id).first()
    if user:
        USER_STATES[chat_id] = {"node_id": node_id}

    # Fetch child nodes
    children = db.query(models.LocationNode).filter(models.LocationNode.parent_id == node_id).all()
    
    # Fetch public chats for this node
    groups = db.query(models.GroupChat).filter(models.GroupChat.location_id == node_id).all()

    # Generate keyboard
    keyboard = []
    
    # 1. Child buttons
    for child in children:
        keyboard.append([{"text": f"👉 {child.name}", "callback_data": f"node_{child.id}"}])

    # 2. Add manually option
    if node.level != "BUILDING":
        child_type = {
            "COUNTRY": "City",
            "CITY": "Neighborhood",
            "NEIGHBORHOOD": "Street",
            "STREET": "Building"
        }[node.level]
        keyboard.append([{"text": f"➕ Add {child_type} here", "callback_data": f"add_{node.id}"}])

    # 3. Action buttons
    if node.level == "BUILDING":
        keyboard.append([{"text": "🔑 Request Entry (Verify)", "callback_data": f"verify_{node.id}"}])

    # 4. Navigation
    nav_row = []
    if node.parent_id:
        nav_row.append({"text": "⬅️ Back", "callback_data": f"node_{node.parent_id}"})
    else:
        nav_row.append({"text": "⬅️ Main Menu", "callback_data": "browse_root"})
    keyboard.append(nav_row)

    # Text content
    text_info = f"📍 *Location:* {node.name} ({node.level.title()})\n\n"
    if groups:
        text_info += "*Chats available:*\n"
        for g in groups:
            text_info += f"- [{g.platform.title()} {g.type.title()} Chat]({g.invite_link})\n"
    else:
        text_info += "No active groups for this level."

    await send_message(
        chat_id,
        text_info,
        reply_markup={"inline_keyboard": keyboard}
    )

async def handle_callback_query(callback: dict, db: Session):
    chat_id = str(callback["message"]["chat"]["id"])
    data = callback["data"]
    telegram_id = str(callback["from"]["id"])
    
    user = get_or_create_user(db, telegram_id)
    if user.is_banned:
        return

    if data == "browse_root":
        await show_root_locations(chat_id, db)
        return

    if data.startswith("node_"):
        node_id = int(data[5:])
        await show_location_node(chat_id, node_id, db)
        return

    if data.startswith("add_"):
        parent_id = int(data[4:])
        parent = db.query(models.LocationNode).filter(models.LocationNode.id == parent_id).first()
        
        USER_STATES[telegram_id] = {
            "node_id": parent_id,
            "action": "awaiting_node_name"
        }
        
        child_type = {
            "COUNTRY": "City",
            "CITY": "Neighborhood",
            "NEIGHBORHOOD": "Street",
            "STREET": "Building"
        }[parent.level]

        await send_message(
            chat_id,
            f"✍️ *Manual Creation:*\nPlease enter the name of the new *{child_type}* under *{parent.name}*:"
        )
        return

    if data.startswith("verify_"):
        building_id = int(data[7:])
        building = db.query(models.LocationNode).filter(models.LocationNode.id == building_id).first()
        
        # Check if already has a pending or approved request
        existing = db.query(models.Verification).filter(
            models.Verification.user_id == user.id,
            models.Verification.building_id == building_id
        ).first()

        if existing:
            if existing.status == "APPROVED":
                groups = db.query(models.GroupChat).filter(
                    models.GroupChat.location_id == building_id,
                    models.GroupChat.type == "PRIVATE"
                ).all()
                links = "\n".join([f"- [{g.platform.title()} Group]({g.invite_link})" for g in groups])
                await send_message(
                    chat_id,
                    f"✅ *Approved!* You already have verified access to *{building.name}*.\n\n*Links:*\n{links}"
                )
            elif existing.status == "PENDING":
                await send_message(chat_id, "⏳ Your verification request is still pending manager review.")
            else:
                # Rejected, allow resubmission
                USER_STATES[telegram_id] = {
                    "node_id": building_id,
                    "action": "awaiting_document"
                }
                await send_message(
                    chat_id,
                    f"🏢 *Resubmit Verification:*\nYour previous request for *{building.name}* was rejected. Re-upload a photo of your utility bill or lease agreement:"
                )
        else:
            USER_STATES[telegram_id] = {
                "node_id": building_id,
                "action": "awaiting_document"
            }
            await send_message(
                chat_id,
                f"🏢 *Building Verification:*\nTo join *{building.name}* private group, please upload a photo of your utility bill, rental agreement, or ID showing residency:"
            )
        return
