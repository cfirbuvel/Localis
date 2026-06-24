import os
import httpx
from typing import Optional, List
from sqlalchemy.orm import Session
from backend import config, models

import json

class PersistentDict(dict):
    def __init__(self, filepath):
        self.filepath = filepath
        super().__init__()
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    super().clear()
                    self.update(data)
            except Exception as e:
                print(f"Error loading persistent states: {e}")

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving persistent states: {e}")

    def __setitem__(self, key, value):
        super().__setitem__(str(key), value)
        self.save()

    def __delitem__(self, key):
        super().__delitem__(str(key))
        self.save()

    def get(self, key, default=None):
        return super().get(str(key), default)

    def pop(self, key, default=None):
        val = super().pop(str(key), default)
        self.save()
        return val

# Persistent states for WhatsApp users to survive container restarts/hot-reloads
states_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_states_wa.json")
USER_STATES_WA = PersistentDict(states_path)

def get_or_create_user_wa(db: Session, whatsapp_number: str, name: str) -> models.User:
    user = db.query(models.User).filter(models.User.whatsapp_number == whatsapp_number).first()
    if not user:
        user = models.User(
            whatsapp_number=whatsapp_number,
            username=name or f"WA_{whatsapp_number}",
            phone_number=whatsapp_number
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

async def send_whatsapp_request(payload: dict) -> bool:
    """Sends a request to the official WhatsApp Cloud Graph API if token is configured."""
    token = config.WHATSAPP_ACCESS_TOKEN
    phone_id = config.WHATSAPP_PHONE_NUMBER_ID
    if not token or not phone_id or "EAAG" in token:  # Detect placeholder
        print(f"[WHATSAPP MOCK SEND] payload={payload}")
        return True

    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, headers=headers, timeout=10.0)
            print(f"[WHATSAPP API RESPONSE] status={res.status_code} body={res.text[:150]}")
            return res.status_code == 200
    except Exception as e:
        print(f"[WHATSAPP API ERROR] Failed to send message: {e}")
        return False

async def send_wa_text(to: str, text: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    await send_whatsapp_request(payload)

async def send_wa_buttons(to: str, text: str, buttons: List[dict]):
    # WhatsApp buttons are limited to maximum 3 inline buttons.
    # buttons: List of {"id": "callback_id", "title": "Button Title"}
    wa_buttons = []
    for btn in buttons[:3]:
        wa_buttons.append({
            "type": "reply",
            "reply": {
                "id": btn["id"],
                "title": btn["title"][:20]  # Max 20 characters title limit in WhatsApp
            }
        })
        
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {"buttons": wa_buttons}
        }
    }
    await send_whatsapp_request(payload)

async def handle_whatsapp_webhook(payload: dict, db: Session):
    """
    Main webhook entry point. Parses WhatsApp Webhook JSON format.
    """
    if "entry" not in payload:
        return

    for entry in payload["entry"]:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if "messages" not in value:
                continue

            for msg in value["messages"]:
                from_num = msg["from"]
                contacts = value.get("contacts", [])
                profile_name = contacts[0].get("profile", {}).get("name", f"WA_{from_num}") if contacts else f"WA_{from_num}"

                user = get_or_create_user_wa(db, from_num, profile_name)
                if user.is_banned:
                    await send_wa_text(from_num, "❌ Your account is banned from using this service.")
                    return

                # Check if interactive button click
                msg_type = msg.get("type")
                text_body = ""
                media_id = None

                if msg_type == "text":
                    text_body = msg.get("text", {}).get("body", "").strip()
                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    if interactive.get("type") == "button_reply":
                        text_body = interactive.get("button_reply", {}).get("id", "")
                elif msg_type == "image":
                    media_id = msg.get("image", {}).get("id")
                elif msg_type == "document":
                    media_id = msg.get("document", {}).get("id")

                await process_wa_message(from_num, text_body, media_id, user, db)

async def process_wa_message(from_num: str, text: str, media_id: Optional[str], user: models.User, db: Session):
    state = USER_STATES_WA.get(from_num, {})

    # Audit message text using AI moderator (excluding commands/button callbacks)
    is_callback = any(text.startswith(prefix) for prefix in ["node_", "verify_", "add_", "browse_", "/"]) or text.lower() == "start"
    if text and not is_callback:
        from backend.services.ai_moderator import audit_user_message
        is_flagged = await audit_user_message(db, user.id, state.get("node_id"), text)
        if is_flagged:
            db.refresh(user)
            if user.is_muted:
                await send_wa_text(from_num, "⚠️ Inappropriate Content Flagged!\nYou have been muted by the AI Moderator.")
                return

    # Action: Awaiting photo/file proof upload for Building verification
    if state.get("action") == "awaiting_document":
        if media_id:
            building_id = state.get("node_id")
            building = db.query(models.LocationNode).filter(models.LocationNode.id == building_id).first()

            # Save verification request in database
            verif = models.Verification(
                user_id=user.id,
                building_id=building_id,
                proof_url=f"whatsapp_media_id:{media_id}",
                status="PENDING"
            )
            db.add(verif)
            db.commit()

            # Clear state
            USER_STATES_WA[from_num] = {}
            await send_wa_text(
                from_num,
                f"✅ Document Received!\nYour request to join {building.name} is pending review. You will receive an invite link once approved."
            )
            print(f"[SYSTEM ALERT] WA verification pending for building '{building.name}' by user '{user.username}'.")
            return
        else:
            await send_wa_text(from_num, "⚠️ Please upload an image or utility bill document. Or send /cancel to abort.")
            return

    # Action: Awaiting manual location creation name
    if state.get("action") == "awaiting_node_name":
        if text.startswith("/"):
            USER_STATES_WA[from_num] = {}
        else:
            parent_id = state.get("node_id")
            parent_node = db.query(models.LocationNode).filter(models.LocationNode.id == parent_id).first()
            
            levels = {
                "COUNTRY": "CITY",
                "CITY": "NEIGHBORHOOD",
                "NEIGHBORHOOD": "STREET",
                "STREET": "BUILDING"
            }
            child_level = levels.get(parent_node.level)
            if not child_level:
                await send_wa_text(from_num, "❌ Cannot add more levels.")
                USER_STATES_WA[from_num] = {}
                return

            node_name = text.strip()
            new_node = models.LocationNode(name=node_name, level=child_level, parent_id=parent_id)
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

            USER_STATES_WA[from_num] = {}
            await send_wa_text(from_num, f"✅ Created new {child_level.lower()}: {node_name}")
            await show_location_wa(from_num, new_node.id, db)
            return

    # Commands & Routing
    if text == "/start" or text == "start":
        await send_wa_buttons(
            from_num,
            "🌍 Welcome to the Global Neighborhood Platform!\nExplore locations and alert neighborhood managers in crisis.",
            [{"id": "browse_wa_root", "title": "🗺️ Browse Locations"}]
        )
        return

    if text == "/browse" or text == "browse_wa_root":
        await show_root_wa(from_num, db)
        return

    if text.startswith("node_"):
        node_id = int(text[5:])
        await show_location_wa(from_num, node_id, db)
        return

    if text.startswith("verify_"):
        building_id = int(text[7:])
        building = db.query(models.LocationNode).filter(models.LocationNode.id == building_id).first()

        USER_STATES_WA[from_num] = {
            "node_id": building_id,
            "action": "awaiting_document"
        }
        await send_wa_text(
            from_num,
            f"🏢 Building Verification for {building.name}:\nPlease upload a photo of your utility bill or lease agreement."
        )
        return

    if text.startswith("add_"):
        parent_id = int(text[4:])
        parent = db.query(models.LocationNode).filter(models.LocationNode.id == parent_id).first()
        USER_STATES_WA[from_num] = {
            "node_id": parent_id,
            "action": "awaiting_node_name"
        }
        child_type = {
            "COUNTRY": "City",
            "CITY": "Neighborhood",
            "NEIGHBORHOOD": "Street",
            "STREET": "Building"
        }[parent.level]
        await send_wa_text(from_num, f"➕ Manual Creation:\nPlease reply with the name of the new {child_type} under {parent.name}:")
        return

    if text.startswith("/emergency") or text.startswith("emergency"):
        desc = text.replace("/emergency", "").replace("emergency", "").strip()
        if not desc:
            await send_wa_text(from_num, "⚠️ Please specify details: emergency <description>")
            return

        user_node_id = state.get("node_id", 1)  # Default node is 1 (Israel)
        node = db.query(models.LocationNode).filter(models.LocationNode.id == user_node_id).first()

        emergency = models.Emergency(user_id=user.id, location_id=user_node_id, message=desc, status="ACTIVE")
        db.add(emergency)
        db.commit()

        await send_wa_text(
            from_num,
            f"🚨 Crisis Alert Sent!\nRegional managers of {node.name} have been notified. AI Coordinator has logged your request."
        )
        print(f"[CRISIS ALERTS WA] User {user.username} emergency at {node.name}: {desc}")
        return

    if text == "/cancel":
        USER_STATES_WA[from_num] = {}
        await send_wa_text(from_num, "🛑 Cancelled. Type start or browse to continue.")
        return

    await send_wa_text(from_num, "🤖 Command not recognized. Send /browse to explore locations.")

async def show_root_wa(from_num: str, db: Session):
    countries = db.query(models.LocationNode).filter(models.LocationNode.level == "COUNTRY").all()
    # List first 3 countries as buttons (WhatsApp Business reply button limit is 3)
    btns = []
    for c in countries[:3]:
        btns.append({"id": f"node_{c.id}", "title": c.name})
    
    await send_wa_buttons(
        from_num,
        "Select your Country below:",
        btns
    )

async def show_location_wa(from_num: str, node_id: int, db: Session):
    node = db.query(models.LocationNode).filter(models.LocationNode.id == node_id).first()
    if not node:
        await send_wa_text(from_num, "Location not found.")
        return

    # Track session state
    USER_STATES_WA[from_num] = {"node_id": node_id}

    # Fetch child nodes
    children = db.query(models.LocationNode).filter(models.LocationNode.parent_id == node_id).all()
    groups = db.query(models.GroupChat).filter(models.GroupChat.location_id == node_id).all()

    text_info = f"📍 Location: {node.name} ({node.level.title()})\n\n"
    if groups:
        text_info += "Chats:\n"
        for g in groups:
            text_info += f"- {g.platform.title()} {g.type.title()}: {g.invite_link}\n"
    
    # Render navigation choices using reply buttons
    btns = []
    
    if node.level == "BUILDING":
        btns.append({"id": f"verify_{node.id}", "title": "🔑 Verify Access"})
    else:
        # Show first 2 child nodes
        for child in children[:2]:
            btns.append({"id": f"node_{child.id}", "title": f"👉 {child.name}"})
        # Add "➕ Create Node" button
        btns.append({"id": f"add_{node.id}", "title": "➕ Create Subnode"})

    # Fallback to main menu if no buttons space
    if not btns:
        btns.append({"id": "browse_wa_root", "title": "🗺️ Main Menu"})
        
    await send_wa_buttons(from_num, text_info, btns)
