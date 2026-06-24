import os
import sys
import httpx
from typing import Optional
from sqlalchemy.orm import Session
from backend import config, models

from backend.services.location import get_location_ancestors, get_location_descendants, normalize_location_name

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

# Persistent session states for bot users to survive container restarts/hot-reloads
states_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_states.json")
USER_STATES = PersistentDict(states_path)

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

def update_user_tracking_info(db: Session, user: models.User, from_user: dict, text: str = None, location: dict = None):
    from datetime import datetime
    user.first_name = from_user.get("first_name")
    user.last_name = from_user.get("last_name")
    user.language_code = from_user.get("language_code")
    user.is_bot = from_user.get("is_bot", False)
    user.last_active_at = datetime.utcnow()
    if text:
        user.last_interaction_text = text
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                user.start_payload = parts[1]
    if location:
        user.latitude = location.get("latitude")
        user.longitude = location.get("longitude")
    db.commit()


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

async def edit_message(chat_id: str, message_id: int, text: str, reply_markup: dict = None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    await send_telegram_request("editMessageText", payload)

async def answer_callback_query(callback_query_id: str):
    await send_telegram_request("answerCallbackQuery", {"callback_query_id": callback_query_id})


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
    update_user_tracking_info(db, user, from_user, text, message.get("location"))
    if user.is_banned:
        await send_message(chat_id, "❌ Your account is banned from using this service.")
        return

    # Check for location attachment
    if "location" in message:
        loc = message["location"]
        await process_location_search(chat_id, db, user, lat=loc["latitude"], lon=loc["longitude"])
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
            normalized_node_name = normalize_location_name(node_name, child_level)
            
            # Check if duplicate node already exists under parent (case-insensitive)
            existing = db.query(models.LocationNode).filter(
                models.LocationNode.name.ilike(normalized_node_name),
                models.LocationNode.level == child_level,
                models.LocationNode.parent_id == parent_id
            ).first()
            
            if existing:
                USER_STATES[telegram_id] = {}
                await send_message(chat_id, f"⚠️ The {child_level.lower()} *{existing.name}* already exists under this parent.")
                await show_location_node(chat_id, existing.id, db)
                return

            new_node = models.LocationNode(
                name=normalized_node_name,
                level=child_level,
                parent_id=parent_id,
                created_by_id=user.id
            )
            db.add(new_node)
            db.commit()
            db.refresh(new_node)

            # Auto create public/private mock groupchats
            gtype = "PRIVATE" if child_level == "BUILDING" else "PUBLIC"
            tg_chat_id = f"tg_chat_{normalized_node_name.lower().replace(' ', '_')}"
            wa_chat_id = f"wa_chat_{normalized_node_name.lower().replace(' ', '_')}"
            
            tg_group = models.GroupChat(location_id=new_node.id, platform="TELEGRAM", chat_id=tg_chat_id, type=gtype, invite_link=f"https://t.me/joinchat/{tg_chat_id}")
            wa_group = models.GroupChat(location_id=new_node.id, platform="WHATSAPP", chat_id=wa_chat_id, type=gtype, invite_link=f"https://chat.whatsapp.com/{wa_chat_id}")
            db.add(tg_group)
            db.add(wa_group)
            db.commit()

            # Clear state and show keyboard for new node
            USER_STATES[telegram_id] = {}
            await send_message(chat_id, f"✅ Created new {child_level.lower()}: *{normalized_node_name}*")
            await show_location_node(chat_id, new_node.id, db)
            return

    # Action: Awaiting community request name (Citizen)
    if state.get("action") == "awaiting_node_name_request":
        if text.startswith("/"):
            USER_STATES[telegram_id] = {}
        else:
            parent_id = state.get("node_id")
            parent_node = db.query(models.LocationNode).filter(models.LocationNode.id == parent_id).first()
            
            parent_level = parent_node.level
            level_map = {
                "COUNTRY": "CITY",
                "CITY": "NEIGHBORHOOD",
                "NEIGHBORHOOD": "STREET",
                "STREET": "BUILDING"
            }
            child_level = level_map.get(parent_level)
            
            node_name = text.strip()
            
            if child_level == "BUILDING":
                USER_STATES[telegram_id] = {
                    "node_id": parent_id,
                    "action": "awaiting_building_request_proof",
                    "temp_node_name": node_name
                }
                await send_message(
                    chat_id,
                    f"🏢 *Residency Verification Needed:*\nTo request the creation of the building *{node_name}*, please upload a photo of your utility bill, lease agreement, or ID showing residency. Type /cancel to abort."
                )
                return
            
            # Create CommunityRequest entry
            comm_req = models.CommunityRequest(
                user_id=user.id,
                parent_id=parent_id,
                name=node_name,
                level=child_level,
                status="PENDING"
            )
            db.add(comm_req)
            db.commit()
            
            USER_STATES[telegram_id] = {}
            await send_message(
                chat_id,
                f"✅ *Request Submitted!*\nYour request to create the {child_level.lower()} *{node_name}* under *{parent_node.name}* has been submitted for admin approval."
            )
            return

    # Action: Awaiting residency proof for building request manually added
    if state.get("action") == "awaiting_building_request_proof":
        document_url = None
        if "photo" in message:
            photo = message["photo"][-1]
            file_id = photo["file_id"]
            document_url = f"telegram_file_id:{file_id}"
        elif "document" in message:
            file_id = message["document"]["file_id"]
            document_url = f"telegram_file_id:{file_id}"

        if document_url:
            parent_id = state.get("node_id")
            node_name = state.get("temp_node_name")
            parent_node = db.query(models.LocationNode).filter(models.LocationNode.id == parent_id).first()
            
            comm_req = models.CommunityRequest(
                user_id=user.id,
                parent_id=parent_id,
                name=node_name,
                level="BUILDING",
                status="PENDING",
                proof_url=document_url
            )
            db.add(comm_req)
            db.commit()
            
            USER_STATES[telegram_id] = {}
            await send_message(
                chat_id,
                f"✅ *Request Submitted!*\nYour request to create the building *{node_name}* under *{parent_node.name}* (with residency proof) has been submitted for admin approval."
            )
            return
        else:
            await send_message(chat_id, "⚠️ Please upload an image or document proof. Or type /cancel to abort.")
            return

    # Action: Awaiting residency proof for building creation on a missing path request
    if state.get("action") == "awaiting_missing_path_proof":
        document_url = None
        if "photo" in message:
            photo = message["photo"][-1]
            file_id = photo["file_id"]
            document_url = f"telegram_file_id:{file_id}"
        elif "document" in message:
            file_id = message["document"]["file_id"]
            document_url = f"telegram_file_id:{file_id}"

        if document_url:
            pending_path = state.get("pending_path")
            await create_community_requests_for_path(
                db, user, telegram_id, chat_id, pending_path, limit_to_street=False, proof_url=document_url
            )
            return
        else:
            await send_message(chat_id, "⚠️ Please upload an image or document proof. Or type /cancel to abort.")
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

    if text == "/admin":
        from backend.main import check_user_hierarchy_permission
        is_admin = check_user_hierarchy_permission(user, None, ["SUPER_ADMIN"], db) or \
                   db.query(models.RoleAssignment).filter(models.RoleAssignment.user_id == user.id, models.RoleAssignment.role.in_(["MANAGER", "MODERATOR"])).first() is not None
        if not is_admin:
            await send_message(chat_id, "❌ Access Denied. You do not have administrator or moderator privileges.")
            return

        await show_admin_menu(chat_id, message_id=None)
        return

    if text == "/cancel":
        USER_STATES[telegram_id] = {}
        await send_message(chat_id, "🛑 Action cancelled. Use /browse to continue.")
        return

    # Default fallback - treat as location search
    if text and not text.startswith("/"):
        await process_location_search(chat_id, db, user, address_text=text)
        return

    await send_message(chat_id, "🤖 Command not recognized. Type /browse to browse locations or send a location to find groups.")


async def show_root_locations(chat_id: str, db: Session, message_id: Optional[int] = None):
    countries = db.query(models.LocationNode).filter(models.LocationNode.level == "COUNTRY").all()
    
    keyboard = []
    for c in countries:
        keyboard.append([{"text": f"📍 {c.name}", "callback_data": f"node_{c.id}"}])

    text = "🗺️ *Select your Country:*"
    if message_id:
        await edit_message(chat_id, message_id, text, reply_markup={"inline_keyboard": keyboard})
    else:
        await send_message(chat_id, text, reply_markup={"inline_keyboard": keyboard})


async def show_location_node(chat_id: str, node_id: int, db: Session, message_id: Optional[int] = None):
    node = db.query(models.LocationNode).filter(models.LocationNode.id == node_id).first()
    if not node:
        await send_message(chat_id, "❌ Location not found.")
        return

    # Track last navigated location node
    user = db.query(models.User).filter(models.User.telegram_id == chat_id).first()
    if user:
        USER_STATES[chat_id] = {"node_id": node_id}

    children = db.query(models.LocationNode).filter(models.LocationNode.parent_id == node_id).all()
    groups = db.query(models.GroupChat).filter(models.GroupChat.location_id == node_id).all()

    keyboard = []
    for child in children:
        keyboard.append([{"text": f"👉 {child.name}", "callback_data": f"node_{child.id}"}])

    from backend.services.location import get_child_level, get_country_flag
    if node.level != "BUILDING":
        child_lvl = get_child_level(node.level, node.name)
        if child_lvl:
            child_titles = {
                "DISTRICT": "District",
                "CITY": "City",
                "NEIGHBORHOOD": "Neighborhood",
                "STREET": "Street",
                "BUILDING": "Building"
            }
            c_title = child_titles.get(child_lvl, "Location")
            keyboard.append([{"text": f"➕ Add {c_title} here", "callback_data": f"add_{node.id}"}])

    if node.level == "BUILDING":
        keyboard.append([{"text": "🔑 Request Entry (Verify)", "callback_data": f"verify_{node.id}"}])

    nav_row = []
    if node.parent_id:
        nav_row.append({"text": "⬅️ Back", "callback_data": f"node_{node.parent_id}"})
    else:
        nav_row.append({"text": "⬅️ Main Menu", "callback_data": "browse_root"})
    keyboard.append(nav_row)

    map_preview = ""
    if node.level in ["CITY", "NEIGHBORHOOD", "STREET", "BUILDING"]:
        if node.latitude is None or node.longitude is None:
            from backend.services.location import geocode_node_coordinates_live
            lat, lon = await geocode_node_coordinates_live(db, node)
            if lat is not None and lon is not None:
                node.latitude = lat
                node.longitude = lon
                db.commit()
                
        if node.latitude is not None and node.longitude is not None:
            lat = node.latitude
            lon = node.longitude
            radius = node.radius or 500
            zoom = 14
            if node.level == "CITY":
                zoom = 12
            elif node.level == "NEIGHBORHOOD":
                zoom = 14
            elif node.level == "STREET":
                zoom = 16
            elif node.level == "BUILDING":
                zoom = 18
                
            import math
            R = 6378137
            circle_points = []
            for i in range(0, 360, 22):
                rad = math.radians(i)
                d_lat = (radius * math.cos(rad)) / R
                d_lon = (radius * math.sin(rad)) / (R * math.cos(math.radians(lat)))
                p_lat = lat + math.degrees(d_lat)
                p_lon = lon + math.degrees(d_lon)
                circle_points.append(f"{p_lon:.6f},{p_lat:.6f}")
            circle_points.append(circle_points[0])
            pts_str = ",".join(circle_points)
            
            # Get country name to determine locale
            country_name = None
            curr = node
            while curr:
                if curr.level == "COUNTRY":
                    country_name = curr.name
                    break
                curr = curr.parent
                
            locale = "en_US"
            if country_name:
                c = country_name.lower().strip()
                if "israel" in c or "ישראל" in c:
                    locale = "he_IL"
                elif "turkey" in c or "türkiye" in c:
                    locale = "tr_TR"
                elif "russia" in c:
                    locale = "ru_RU"
                elif "ukraine" in c:
                    locale = "uk_UA"
            
            map_url = f"https://static-maps.yandex.ru/1.x/?ll={lon},{lat}&z={zoom}&size=450,300&l=map&lang={locale}&pl=c:ff000080,f:ff000030,w:2,{pts_str}"
            map_preview = f"[\u200b]({map_url})"

    flag_str = ""
    if node.level == "COUNTRY":
        flag_str = f" {get_country_flag(node.name)}"
        
    text_info = f"{map_preview}📍 *Location:* {node.name}{flag_str} ({node.level.title()})\n\n"
    if groups:
        text_info += "*Chats available:*\n"
        for g in groups:
            text_info += f"- [{g.platform.title()} {g.type.title()} Chat]({g.invite_link})\n"
    else:
        text_info += "No active groups for this level."

    if message_id:
        await edit_message(chat_id, message_id, text_info, reply_markup={"inline_keyboard": keyboard})
    else:
        await send_message(chat_id, text_info, reply_markup={"inline_keyboard": keyboard})


async def show_admin_menu(chat_id: str, message_id: Optional[int] = None):
    text = "👑 *Localis Administrator Portal*\nSelect an option to manage the network:"
    keyboard = [
        [{"text": "📋 Verifications Queue", "callback_data": "admin_verif_list"}],
        [{"text": "✍️ Community Requests", "callback_data": "admin_req_list"}],
        [{"text": "🚨 Active Emergencies", "callback_data": "admin_emg_list"}],
        [{"text": "🛡️ Moderation Feed", "callback_data": "admin_mod_list"}],
        [{"text": "🚪 Exit Admin Menu", "callback_data": "admin_exit"}]
    ]
    if message_id:
        await edit_message(chat_id, message_id, text, reply_markup={"inline_keyboard": keyboard})
    else:
        await send_message(chat_id, text, reply_markup={"inline_keyboard": keyboard})


async def handle_callback_query(callback: dict, db: Session):
    chat_id = str(callback["message"]["chat"]["id"])
    data = callback["data"]
    telegram_id = str(callback["from"]["id"])
    callback_query_id = callback["id"]
    message_id = callback["message"]["message_id"]
    
    # Answer callback query to stop loading spinner
    await answer_callback_query(callback_query_id)
    
    user = get_or_create_user(db, telegram_id)
    if user.is_banned:
        return

    if data == "browse_root":
        await show_root_locations(chat_id, db, message_id=message_id)
        return

    if data.startswith("node_"):
        node_id = int(data[5:])
        await show_location_node(chat_id, node_id, db, message_id=message_id)
        return


    if data.startswith("add_"):
        parent_id = int(data[4:])
        parent = db.query(models.LocationNode).filter(models.LocationNode.id == parent_id).first()
        
        # Check permissions
        from backend.main import check_user_hierarchy_permission
        is_admin = check_user_hierarchy_permission(user, parent_id, ["MANAGER"], db)
        
        child_type = {
            "COUNTRY": "City",
            "CITY": "Neighborhood",
            "NEIGHBORHOOD": "Street",
            "STREET": "Building"
        }[parent.level]

        if is_admin:
            USER_STATES[telegram_id] = {
                "node_id": parent_id,
                "action": "awaiting_node_name"
            }
            await send_message(
                chat_id,
                f"👑 *Admin Manual Creation:*\nPlease enter the name of the new *{child_type}* under *{parent.name}*:"
            )
        else:
            USER_STATES[telegram_id] = {
                "node_id": parent_id,
                "action": "awaiting_node_name_request"
            }
            await send_message(
                chat_id,
                f"✍️ *Request Community Creation:*\nYou are requesting to create a new *{child_type}* under *{parent.name}*. Please enter the name of the new community/group:"
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

    if data == "req_missing_path":
        state = USER_STATES.get(telegram_id, {})
        pending_path = state.get("pending_path")
        if not pending_path:
            await send_message(chat_id, "❌ No pending location search found. Please send your location again.")
            return

        # Intercept and show city suggestions if CITY level is missing
        missing_levels = state.get("missing_levels", [])
        if "CITY" in missing_levels:
            path_items = state.get("path_items", [])
            city_name = None
            for lvl, name in path_items:
                if lvl == "CITY":
                    city_name = name
                    break
            
            if city_name:
                from backend.services.telegram_userbot import search_public_groups
                suggestions = await search_public_groups(city_name)
                if suggestions:
                    # Save suggestions to state
                    state["city_suggestions"] = suggestions
                    state["city_name"] = city_name
                    USER_STATES[telegram_id] = state
                    
                    keyboard = []
                    for idx, sugg in enumerate(suggestions):
                        keyboard.append([{"text": f"🔗 Link: {sugg['title']}", "callback_data": f"city_sugg_link_{idx}"}])
                    keyboard.append([{"text": "➕ Create New Group", "callback_data": "city_sugg_create_new"}])
                    keyboard.append([{"text": "❌ Cancel", "callback_data": "admin_exit"}])
                    
                    await send_message(
                        chat_id,
                        f"🔍 *City Group Suggestions for {city_name}:*\n"
                        f"Before creating a new city group, please check if one of these official public groups already exists for *{city_name}*:",
                        reply_markup={"inline_keyboard": keyboard}
                    )
                    return

        if "BUILDING" in state.get("missing_levels", []):
            await send_message(
                chat_id,
                "🏢 *Building Request Options:*\n"
                "Creating a building node requires proof of residency (e.g., utility bill, lease agreement).\n"
                "How would you like to proceed?",
                reply_markup={
                    "inline_keyboard": [
                        [
                            {"text": "🏢 Request with Building (Requires Proof)", "callback_data": "req_missing_with_building"},
                            {"text": "🛣️ Request up to Street (No Proof)", "callback_data": "req_missing_up_to_street"}
                        ]
                    ]
                }
            )
            return

        await create_community_requests_for_path(db, user, telegram_id, chat_id, pending_path, limit_to_street=False)
        return

    if data == "req_missing_with_building":
        state = USER_STATES.get(telegram_id, {})
        pending_path = state.get("pending_path")
        if not pending_path:
            await send_message(chat_id, "❌ No pending location search found. Please send your location again.")
            return
        state["action"] = "awaiting_missing_path_proof"
        USER_STATES[telegram_id] = state
        await send_message(
            chat_id,
            "🏢 *Upload Proof of Residency:*\n"
            "Please upload a photo of your utility bill, lease agreement, or ID showing residency to request creation of the building group. Or type /cancel to abort."
        )
        return

    if data == "req_missing_up_to_street":
        state = USER_STATES.get(telegram_id, {})
        pending_path = state.get("pending_path")
        if not pending_path:
            await send_message(chat_id, "❌ No pending location search found. Please send your location again.")
            return
        await create_community_requests_for_path(db, user, telegram_id, chat_id, pending_path, limit_to_street=True)
        return

    # -----------------------------------------------------------------
    # MUNICIPAL CITY GROUP SUGGESTION CALLBACK HANDLERS
    # -----------------------------------------------------------------
    if data.startswith("city_sugg_link_"):
        idx = int(data[15:])
        state = USER_STATES.get(telegram_id, {})
        suggestions = state.get("city_suggestions", [])
        pending_path = state.get("pending_path")
        
        if not pending_path or idx >= len(suggestions):
            await send_message(chat_id, "❌ Session expired or suggestion invalid. Please search for the location again.")
            return
            
        selected_sugg = suggestions[idx]
        custom_city_group = {
            "chat_id": selected_sugg["chat_id"],
            "invite_link": selected_sugg["invite_link"]
        }
        
        # Proceed with creation linking the selected public group
        await create_community_requests_for_path(
            db, user, telegram_id, chat_id, pending_path, limit_to_street=False, custom_city_group=custom_city_group
        )
        return

    if data == "city_sugg_create_new":
        state = USER_STATES.get(telegram_id, {})
        pending_path = state.get("pending_path")
        if not pending_path:
            await send_message(chat_id, "❌ Session expired. Please search for the location again.")
            return
            
        # Proceed to create a new group
        await create_community_requests_for_path(
            db, user, telegram_id, chat_id, pending_path, limit_to_street=False
        )
        return

    # -----------------------------------------------------------------
    # ADMIN SYSTEM MENU & FLOWS
    # -----------------------------------------------------------------
    if data == "admin_menu":
        await show_admin_menu(chat_id, message_id=message_id)
        return

    if data == "admin_exit":
        await edit_message(chat_id, message_id, "🚪 Exited Administrator Portal.")
        return

    # A. Verifications Queue
    if data == "admin_verif_list":
        pending_verifs = db.query(models.Verification).filter(models.Verification.status == "PENDING").all()
        if not pending_verifs:
            keyboard = [[{"text": "⬅️ Back", "callback_data": "admin_menu"}]]
            await edit_message(chat_id, message_id, "📋 *Verification Queue*:\nNo pending residency verifications.", reply_markup={"inline_keyboard": keyboard})
            return
        
        keyboard = []
        for pv in pending_verifs[:10]: # Limit to 10
            keyboard.append([{"text": f"👤 {pv.user.username} ({pv.building.name})", "callback_data": f"admin_ver_v_{pv.id}"}])
        keyboard.append([{"text": "⬅️ Admin Menu", "callback_data": "admin_menu"}])
        await edit_message(chat_id, message_id, "📋 *Select verification to review*:", reply_markup={"inline_keyboard": keyboard})
        return

    if data.startswith("admin_ver_v_"):
        verif_id = int(data[12:])
        pv = db.query(models.Verification).filter(models.Verification.id == verif_id).first()
        if not pv:
            await send_message(chat_id, "❌ Verification request not found.")
            return
        
        proof_text = f"📄 [Proof Document Link]({pv.proof_url})" if "http" in pv.proof_url else f"📎 File ID: `{pv.proof_url}`"
        text = (
            f"📋 *Verification Request Details*:\n\n"
            f"👤 *User*: @{pv.user.username or pv.user.telegram_id}\n"
            f"🏢 *Building*: {pv.building.name}\n"
            f"Proof: {proof_text}\n"
            f"Submitted: {pv.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Please approve or reject:"
        )
        keyboard = [
            [
                {"text": "✅ Approve", "callback_data": f"admin_ver_app_{pv.id}"},
                {"text": "❌ Reject", "callback_data": f"admin_ver_rej_{pv.id}"}
            ],
            [{"text": "⬅️ Back", "callback_data": "admin_verif_list"}]
        ]
        await edit_message(chat_id, message_id, text, reply_markup={"inline_keyboard": keyboard})
        return

    if data.startswith("admin_ver_app_"):
        verif_id = int(data[14:])
        pv = db.query(models.Verification).filter(models.Verification.id == verif_id).first()
        if not pv:
            await send_message(chat_id, "❌ Verification request not found.")
            return
        
        pv.status = "APPROVED"
        pv.reviewed_by = user.id
        db.commit()
        
        # Send private invite links to the user
        groups = db.query(models.GroupChat).filter(
            models.GroupChat.location_id == pv.building_id,
            models.GroupChat.type == "PRIVATE"
        ).all()
        links_text = "\n".join([f"- [{g.platform.title()} Group]({g.invite_link})" for g in groups])
        user_msg = (
            f"🎉 *Good news!*\nYour residency verification for *{pv.building.name}* has been approved by the administrators!\n\n"
            f"You can now join the private group chats:\n{links_text}"
        )
        await send_message(pv.user.telegram_id, user_msg)
        
        # Update current message
        keyboard = [[{"text": "⬅️ Back to Queue", "callback_data": "admin_verif_list"}]]
        await edit_message(chat_id, message_id, f"✅ Approved residency verification for *@{pv.user.username}* at *{pv.building.name}*.", reply_markup={"inline_keyboard": keyboard})
        return

    if data.startswith("admin_ver_rej_"):
        verif_id = int(data[14:])
        pv = db.query(models.Verification).filter(models.Verification.id == verif_id).first()
        if not pv:
            await send_message(chat_id, "❌ Verification request not found.")
            return
        
        pv.status = "REJECTED"
        pv.reviewed_by = user.id
        db.commit()
        
        # Notify user
        user_msg = f"❌ Your residency verification request for *{pv.building.name}* was rejected by the administrators."
        await send_message(pv.user.telegram_id, user_msg)
        
        keyboard = [[{"text": "⬅️ Back to Queue", "callback_data": "admin_verif_list"}]]
        await edit_message(chat_id, message_id, f"❌ Rejected residency verification for *@{pv.user.username}* at *{pv.building.name}*.", reply_markup={"inline_keyboard": keyboard})
        return

    # B. Community Requests
    if data == "admin_req_list":
        pending_reqs = db.query(models.CommunityRequest).filter(models.CommunityRequest.status == "PENDING").all()
        if not pending_reqs:
            keyboard = [[{"text": "⬅️ Back", "callback_data": "admin_menu"}]]
            await edit_message(chat_id, message_id, "✍️ *Community Requests*:\nNo pending creation requests.", reply_markup={"inline_keyboard": keyboard})
            return
        
        keyboard = []
        for pr in pending_reqs[:10]:
            keyboard.append([{"text": f"➕ {pr.name} ({pr.level.title()})", "callback_data": f"admin_req_v_{pr.id}"}])
        keyboard.append([{"text": "⬅️ Admin Menu", "callback_data": "admin_menu"}])
        await edit_message(chat_id, message_id, "✍️ *Select community request to review*:", reply_markup={"inline_keyboard": keyboard})
        return

    if data.startswith("admin_req_v_"):
        req_id = int(data[12:])
        pr = db.query(models.CommunityRequest).filter(models.CommunityRequest.id == req_id).first()
        if not pr:
            await send_message(chat_id, "❌ Request not found.")
            return
        
        text = (
            f"✍️ *Community Request Details*:\n\n"
            f"👤 *Requester*: @{pr.user.username or pr.user.telegram_id}\n"
            f"📍 *Proposed Name*: {pr.name} ({pr.level.title()})\n"
            f"Parent Node: {pr.parent.name if pr.parent else 'Global'}\n"
            f"Submitted: {pr.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        )
        
        # Search for existing Telegram groups to display suggestions
        from backend.services.telegram_userbot import search_public_groups
        suggestions = await search_public_groups(pr.name)
        
        keyboard = []
        if pr.level == "CITY" and suggestions:
            text += "🔍 *Suggested Existing Groups found on Telegram*:\n"
            for idx, sugg in enumerate(suggestions[:3]): # Max 3 suggestions
                text += f"- {sugg['title']} ({sugg['invite_link']})\n"
                keyboard.append([{"text": f"🔗 Link to: {sugg['title'][:20]}", "callback_data": f"admin_req_lnk_{pr.id}_{idx}"}])
            text += "\nChoose to link one of these groups, or create a brand new group:"
            
            # Store suggestions in state for callback reference
            state = USER_STATES.get(telegram_id, {})
            state[f"req_suggs_{pr.id}"] = suggestions
            USER_STATES[telegram_id] = state

        keyboard.append([{"text": "➕ Approve & Create New Group", "callback_data": f"admin_req_new_{pr.id}"}])
        keyboard.append([{"text": "❌ Reject Request", "callback_data": f"admin_req_rej_{pr.id}"}])
        keyboard.append([{"text": "⬅️ Back", "callback_data": "admin_req_list"}])
        await edit_message(chat_id, message_id, text, reply_markup={"inline_keyboard": keyboard})
        return

    if data.startswith("admin_req_lnk_"):
        parts = data.split("_")
        req_id = int(parts[3])
        sugg_idx = int(parts[4])
        
        pr = db.query(models.CommunityRequest).filter(models.CommunityRequest.id == req_id).first()
        if not pr:
            await send_message(chat_id, "❌ Request not found.")
            return
            
        state = USER_STATES.get(telegram_id, {})
        suggestions = state.get(f"req_suggs_{pr.id}", [])
        if sugg_idx >= len(suggestions):
            await send_message(chat_id, "❌ Suggestion no longer available.")
            return
            
        selected_sugg = suggestions[sugg_idx]
        
        # Approve request and link to selected suggestion
        pr.status = "APPROVED"
        
        # Create Node
        new_node = models.LocationNode(name=pr.name, level=pr.level, parent_id=pr.parent_id, created_by_id=pr.user_id)
        db.add(new_node)
        db.commit()
        db.refresh(new_node)
        
        # Create Group Chats linking the selected group
        gtype = "PRIVATE" if new_node.level == "BUILDING" else "PUBLIC"
        tg_group = models.GroupChat(
            location_id=new_node.id, platform="TELEGRAM", chat_id=selected_sugg["chat_id"], type=gtype, invite_link=selected_sugg["invite_link"]
        )
        wa_chat_id = f"wa_chat_{new_node.name.lower().replace(' ', '_')}"
        wa_group = models.GroupChat(
            location_id=new_node.id, platform="WHATSAPP", chat_id=wa_chat_id, type=gtype, invite_link=f"https://chat.whatsapp.com/{wa_chat_id}"
        )
        db.add(tg_group)
        db.add(wa_group)
        db.commit()
        
        # Notify user
        msg = (
            f"🎉 *Good news!*\nYour request to create the community *{pr.name}* ({pr.level.title()}) has been approved!\n\n"
            f"You can join the linked group here:\n"
            f"👉 [Telegram Chat]({selected_sugg['invite_link']})"
        )
        await send_message(pr.user.telegram_id, msg)
        
        keyboard = [[{"text": "⬅️ Back to Requests", "callback_data": "admin_req_list"}]]
        await edit_message(chat_id, message_id, f"✅ Linked and approved *{pr.name}* to existing group *{selected_sugg['title']}*.", reply_markup={"inline_keyboard": keyboard})
        return

    if data.startswith("admin_req_new_"):
        req_id = int(data[14:])
        pr = db.query(models.CommunityRequest).filter(models.CommunityRequest.id == req_id).first()
        if not pr:
            await send_message(chat_id, "❌ Request not found.")
            return
            
        pr.status = "APPROVED"
        
        # Create Node
        new_node = models.LocationNode(name=pr.name, level=pr.level, parent_id=pr.parent_id, created_by_id=pr.user_id)
        radius_map = {"CITY": 2000.0, "NEIGHBORHOOD": 800.0, "STREET": 250.0, "BUILDING": 50.0}
        if pr.level in radius_map:
            new_node.radius = radius_map[pr.level]
        db.add(new_node)
        db.commit()
        db.refresh(new_node)
        
        # Geocode coordinates live
        from backend.services.location import geocode_node_coordinates_live, get_city_name_for_node, get_country_flag
        lat, lon = await geocode_node_coordinates_live(db, new_node)
        if lat is not None and lon is not None:
            new_node.latitude = lat
            new_node.longitude = lon
            db.commit()
            
        # Format group title & description
        city_name = get_city_name_for_node(db, new_node)
        group_title = None
        description = None
        
        if new_node.level == "COUNTRY":
            group_title = f"{new_node.name} {get_country_flag(new_node.name)}"
            description = f"Welcome to the official community group for {new_node.name}."
        elif new_node.level == "CITY":
            group_title = f"🇮🇱 Localis | {new_node.name}"
            description = (
                f"ברוכים הבאים לקהילת העיר {new_node.name}.\n\n"
                f"הקבוצה מיועדת לכל תושבי העיר ומאפשרת לשתף מידע, המלצות, אירועים, עדכונים חשובים, דיונים קהילתיים ועזרה הדדית בין תושבי העיר.\n\n"
                f"📍 אזור: {new_node.name}\n"
                f"👥 קהל יעד: כלל תושבי העיר\n"
                f"🔗 לקבוצות שכונתיות ומקומיות השתמשו בבוט Localis."
            )
        elif new_node.level == "NEIGHBORHOOD":
            c_name = city_name or "העיר"
            group_title = f"🏘️ Localis | {c_name} | {new_node.name}"
            description = (
                f"ברוכים הבאים לקהילת שכונת {new_node.name}.\n\n"
                f"מקום לתושבי השכונה לשתף מידע מקומי, המלצות, אירועים, אבדות ומציאות, עדכוני תנועה, התארגנויות שכונתיות ועזרה הדדית.\n\n"
                f"📍 עיר: {c_name}\n"
                f"📍 שכונה: {new_node.name}\n"
                f"👥 קהל יעד: תושבי השכונה והסביבה"
            )
        elif new_node.level == "STREET":
            c_name = city_name or "העיר"
            neighborhood_name = ""
            curr = new_node.parent
            while curr:
                if curr.level == "NEIGHBORHOOD":
                    neighborhood_name = curr.name
                    break
                curr = curr.parent
            n_part = f" | {neighborhood_name}" if neighborhood_name else ""
            n_desc = f"📍 שכונה: {neighborhood_name}\n" if neighborhood_name else ""
            group_title = f"🏠 Localis | {c_name}{n_part} | רחוב {new_node.name}"
            description = (
                f"ברוכים הבאים לקהילת רחוב {new_node.name}.\n\n"
                f"הקבוצה מיועדת לתושבי הרחוב ומטרתה לשפר את התקשורת בין השכנים, לשתף מידע רלוונטי, לדווח על תקלות, לעזור אחד לשני ולחזק את הקהילה המקומית.\n\n"
                f"📍 עיר: {c_name}\n"
                f"{n_desc}"
                f"📍 רחוב: {new_node.name}\n"
                f"👥 קהל יעד: תושבי הרחוב"
            )
        elif new_node.level == "BUILDING":
            c_name = city_name or "העיר"
            neighborhood_name = ""
            curr = new_node.parent
            while curr:
                if curr.level == "NEIGHBORHOOD":
                    neighborhood_name = curr.name
                    break
                curr = curr.parent
            n_part = f" | {neighborhood_name}" if neighborhood_name else ""
            n_desc = f"📍 שכונה: {neighborhood_name}\n" if neighborhood_name else ""
            group_title = f"🔒 Localis | {c_name}{n_part} | רחוב {new_node.name}"
            description = (
                f"ברוכים הבאים לקהילת דיירי הבניין.\n\n"
                f"זוהי קבוצה פרטית המיועדת לדיירים המאומתים של הבניין בלבד.\n\n"
                f"בקבוצה ניתן לדון בנושאי ועד בית, תחזוקה, חניה, אבטחה, משלוחים, התראות חשובות וכל נושא הקשור לחיי היומיום בבניין.\n\n"
                f"📍 עיר: {c_name}\n"
                f"{n_desc}"
                f"📍 כתובת: רחוב {new_node.name}\n\n"
                f"🔒 הכניסה לקבוצה מחייבת אימות דייר.\n"
                f"🔒 רק דיירים מאומתים יכולים להישאר חברים בקבוצה.\n"
                f"🔒 אימות תקופתי עשוי להתבצע לצורך שמירה על פרטיות וביטחון הדיירים.\n\n"
                f"🤝 קהילה חזקה מתחילה מהבניין שבו אתם גרים."
            )
            
        coords_dict = {"latitude": new_node.latitude, "longitude": new_node.longitude, "radius": new_node.radius}
        
        # Get country name
        country_name = None
        curr = new_node
        while curr:
            if curr.level == "COUNTRY":
                country_name = curr.name
                break
            curr = curr.parent
            
        # Create brand new groups
        from backend.services.telegram_userbot import create_telegram_group
        tg_info = await create_telegram_group(new_node.name, new_node.level, node_id=new_node.id, group_title=group_title, description=description, coords=coords_dict, country_name=country_name)
        gtype = "PRIVATE" if new_node.level == "BUILDING" else "PUBLIC"
        tg_group = models.GroupChat(
            location_id=new_node.id, platform="TELEGRAM", chat_id=tg_info["chat_id"], type=gtype, invite_link=tg_info["invite_link"]
        )
        wa_chat_id = f"wa_chat_{new_node.name.lower().replace(' ', '_')}"
        wa_group = models.GroupChat(
            location_id=new_node.id, platform="WHATSAPP", chat_id=wa_chat_id, type=gtype, invite_link=f"https://chat.whatsapp.com/{wa_chat_id}"
        )
        db.add(tg_group)
        db.add(wa_group)
        db.commit()
        
        # Notify user
        msg = (
            f"🎉 *Good news!*\nYour request to create the community *{pr.name}* ({pr.level.title()}) has been approved!\n\n"
            f"You can join the new group here:\n"
            f"👉 [Telegram Chat]({tg_info['invite_link']})"
        )
        await send_message(pr.user.telegram_id, msg)
        
        keyboard = [[{"text": "⬅️ Back to Requests", "callback_data": "admin_req_list"}]]
        await edit_message(chat_id, message_id, f"✅ Created new group and approved *{pr.name}*.", reply_markup={"inline_keyboard": keyboard})
        return

    if data.startswith("admin_req_rej_"):
        req_id = int(data[14:])
        pr = db.query(models.CommunityRequest).filter(models.CommunityRequest.id == req_id).first()
        if not pr:
            await send_message(chat_id, "❌ Request not found.")
            return
            
        pr.status = "REJECTED"
        db.commit()
        
        # Notify user
        msg = f"❌ Your request to create *{pr.name}* ({pr.level.title()}) was rejected by the administrators."
        await send_message(pr.user.telegram_id, msg)
        
        keyboard = [[{"text": "⬅️ Back to Requests", "callback_data": "admin_req_list"}]]
        await edit_message(chat_id, message_id, f"❌ Rejected creation request for *{pr.name}*.", reply_markup={"inline_keyboard": keyboard})
        return

    # C. Emergency Feed
    if data == "admin_emg_list":
        emergencies = db.query(models.Emergency).filter(models.Emergency.status == "ACTIVE").all()
        if not emergencies:
            keyboard = [[{"text": "⬅️ Back", "callback_data": "admin_menu"}]]
            await edit_message(chat_id, message_id, "🚨 *Active Emergencies*:\nNo active emergency alerts at this time.", reply_markup={"inline_keyboard": keyboard})
            return
            
        keyboard = []
        for emg in emergencies[:10]:
            keyboard.append([{"text": f"🚨 {emg.message[:25]}...", "callback_data": f"admin_emg_v_{emg.id}"}])
        keyboard.append([{"text": "⬅️ Admin Menu", "callback_data": "admin_menu"}])
        await edit_message(chat_id, message_id, "🚨 *Select emergency alert to manage*:", reply_markup={"inline_keyboard": keyboard})
        return

    if data.startswith("admin_emg_v_"):
        emg_id = int(data[12:])
        emg = db.query(models.Emergency).filter(models.Emergency.id == emg_id).first()
        if not emg:
            await send_message(chat_id, "❌ Emergency alert not found.")
            return
            
        text = (
            f"🚨 *Crisis Alert Details*:\n\n"
            f"👤 *Reporter*: @{emg.user.username or emg.user.telegram_id}\n"
            f"📍 *Location*: {emg.location.name} ({emg.location.level.title()})\n"
            f"Message: *{emg.message}*\n"
            f"Reported: {emg.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Choose an action:"
        )
        keyboard = [
            [{"text": "✅ Mark Resolved", "callback_data": f"admin_emg_res_{emg.id}"}],
            [{"text": "⬅️ Back", "callback_data": "admin_emg_list"}]
        ]
        await edit_message(chat_id, message_id, text, reply_markup={"inline_keyboard": keyboard})
        return

    if data.startswith("admin_emg_res_"):
        emg_id = int(data[14:])
        emg = db.query(models.Emergency).filter(models.Emergency.id == emg_id).first()
        if not emg:
            await send_message(chat_id, "❌ Emergency alert not found.")
            return
            
        emg.status = "RESOLVED"
        db.commit()
        
        keyboard = [[{"text": "⬅️ Back to Emergencies", "callback_data": "admin_emg_list"}]]
        await edit_message(chat_id, message_id, f"✅ Marked emergency report by *@{emg.user.username}* as RESOLVED.", reply_markup={"inline_keyboard": keyboard})
        return

    # D. Moderation Feed / Spam Logs
    if data == "admin_mod_list":
        logs = db.query(models.ModerationLog).order_by(models.ModerationLog.flagged_at.desc()).limit(10).all()
        if not logs:
            keyboard = [[{"text": "⬅️ Back", "callback_data": "admin_menu"}]]
            await edit_message(chat_id, message_id, "🛡️ *Moderation logs*:\nNo AI moderation flags found.", reply_markup={"inline_keyboard": keyboard})
            return
            
        keyboard = []
        for ml in logs:
            keyboard.append([{"text": f"⚠️ {ml.user.username or ml.user_id}: {ml.message_text[:20]}...", "callback_data": f"admin_mod_v_{ml.id}"}])
        keyboard.append([{"text": "⬅️ Admin Menu", "callback_data": "admin_menu"}])
        await edit_message(chat_id, message_id, "🛡️ *Select moderation flag to view details*:", reply_markup={"inline_keyboard": keyboard})
        return

    if data.startswith("admin_mod_v_"):
        log_id = int(data[12:])
        ml = db.query(models.ModerationLog).filter(models.ModerationLog.id == log_id).first()
        if not ml:
            await send_message(chat_id, "❌ Moderation log not found.")
            return
            
        target_user = ml.user
        text = (
            f"🛡️ *AI Moderation Flag details*:\n\n"
            f"👤 *Flagged User*: @{target_user.username or target_user.telegram_id}\n"
            f"💬 *Message Text*: \"{ml.message_text}\"\n"
            f"Location Scope: {ml.location.name if ml.location else 'System'}\n"
            f"Status: "
        )
        if target_user.is_banned:
            text += "*BANNED*"
        elif target_user.is_muted:
            text += "*MUTED*"
        else:
            text += "Active"
            
        keyboard = [
            [
                {"text": "🔊 Unmute" if target_user.is_muted else "🔇 Mute User", "callback_data": f"admin_mod_mut_{target_user.id}_{ml.id}"},
                {"text": "🟢 Unban" if target_user.is_banned else "🚫 Ban User", "callback_data": f"admin_mod_ban_{target_user.id}_{ml.id}"}
            ],
            [{"text": "⬅️ Back", "callback_data": "admin_mod_list"}]
        ]
        await edit_message(chat_id, message_id, text, reply_markup={"inline_keyboard": keyboard})
        return

    if data.startswith("admin_mod_mut_"):
        parts = data.split("_")
        user_id = parts[3]
        log_id = int(parts[4])
        
        target = db.query(models.User).filter(models.User.id == user_id).first()
        if not target:
            await send_message(chat_id, "❌ User not found.")
            return
            
        # Toggle mute
        target.is_muted = not target.is_muted
        db.commit()
        
        action = "muted" if target.is_muted else "unmuted"
        # Notify user if possible
        try:
            await send_message(target.telegram_id, f"⚠️ You have been {action} by the administrator.")
        except Exception:
            pass
            
        keyboard = [[{"text": "⬅️ Back to Log", "callback_data": f"admin_mod_v_{log_id}"}]]
        await edit_message(chat_id, message_id, f"✅ User @{target.username} has been {action}.", reply_markup={"inline_keyboard": keyboard})
        return

    if data.startswith("admin_mod_ban_"):
        parts = data.split("_")
        user_id = parts[3]
        log_id = int(parts[4])
        
        target = db.query(models.User).filter(models.User.id == user_id).first()
        if not target:
            await send_message(chat_id, "❌ User not found.")
            return
            
        # Toggle ban
        target.is_banned = not target.is_banned
        db.commit()
        
        action = "banned" if target.is_banned else "unbanned"
        try:
            await send_message(target.telegram_id, f"🚫 Your account has been {action} by the administrator.")
        except Exception:
            pass
            
        keyboard = [[{"text": "⬅️ Back to Log", "callback_data": f"admin_mod_v_{log_id}"}]]
        await edit_message(chat_id, message_id, f"✅ User @{target.username} has been {action}.", reply_markup={"inline_keyboard": keyboard})
        return

async def create_community_requests_for_path(
    db: Session,
    user: models.User,
    telegram_id: str,
    chat_id: str,
    pending_path: list,
    limit_to_street: bool = False,
    proof_url: str = None,
    custom_city_group: dict = None
):
    parent_id = None
    
    from backend.main import check_user_hierarchy_permission
    
    created_count = 0
    requested_count = 0
    
    last_request_id = None
    last_level = "COUNTRY"
    last_name = ""
    
    for idx, name in enumerate(pending_path):
        name = name.strip()
        if not name:
            continue
            
        if idx == 0:
            level = "COUNTRY"
        else:
            from backend.services.location import get_child_level
            level = get_child_level(last_level, last_name)
            
        last_level = level
        last_name = name
        
        if limit_to_street and level == "BUILDING":
            break
            
        # Normalize name (e.g. Hebrew -> English)
        name = normalize_location_name(name, level)

        # Check if exists
        node = db.query(models.LocationNode).filter(
            models.LocationNode.name.ilike(name),
            models.LocationNode.level == level,
            models.LocationNode.parent_id == parent_id
        ).first()
        
        if node:
            parent_id = node.id
            last_request_id = None
        else:
            is_admin = check_user_hierarchy_permission(user, parent_id, ["MANAGER"], db)
            if is_admin:
                node = models.LocationNode(name=name, level=level, parent_id=parent_id, created_by_id=user.id)
                radius_map = {"CITY": 2000.0, "NEIGHBORHOOD": 800.0, "STREET": 250.0, "BUILDING": 50.0}
                if level in radius_map:
                    node.radius = radius_map[level]
                db.add(node)
                db.commit()
                db.refresh(node)
                
                # Geocode coordinates live
                from backend.services.location import geocode_node_coordinates_live, get_city_name_for_node, get_country_flag
                lat, lon = await geocode_node_coordinates_live(db, node)
                if lat is not None and lon is not None:
                    node.latitude = lat
                    node.longitude = lon
                    db.commit()
                    
                # Format group title & description
                city_name = get_city_name_for_node(db, node)
                group_title = None
                description = None
                
                if level == "COUNTRY":
                    group_title = f"{node.name} {get_country_flag(node.name)}"
                    description = f"Welcome to the official community group for {node.name}."
                elif level == "CITY":
                    group_title = f"🇮🇱 Localis | {node.name}"
                    description = (
                        f"ברוכים הבאים לקהילת העיר {node.name}.\n\n"
                        f"הקבוצה מיועדת לכל תושבי העיר ומאפשרת לשתף מידע, המלצות, אירועים, עדכונים חשובים, דיונים קהילתיים ועזרה הדדית בין תושבי העיר.\n\n"
                        f"📍 אזור: {node.name}\n"
                        f"👥 קהל יעד: כלל תושבי העיר\n"
                        f"🔗 לקבוצות שכונתיות ומקומיות השתמשו בבוט Localis."
                    )
                elif level == "NEIGHBORHOOD":
                    c_name = city_name or "העיר"
                    group_title = f"🏘️ Localis | {c_name} | {node.name}"
                    description = (
                        f"ברוכים הבאים לקהילת שכונת {node.name}.\n\n"
                        f"מקום לתושבי השכונה לשתף מידע מקומי, המלצות, אירועים, אבדות ומציאות, עדכוני תנועה, התארגנויות שכונתיות ועזרה הדדית.\n\n"
                        f"📍 עיר: {c_name}\n"
                        f"📍 שכונה: {node.name}\n"
                        f"👥 קהל יעד: תושבי השכונה והסביבה"
                    )
                elif level == "STREET":
                    c_name = city_name or "העיר"
                    neighborhood_name = ""
                    curr = node.parent
                    while curr:
                        if curr.level == "NEIGHBORHOOD":
                            neighborhood_name = curr.name
                            break
                        curr = curr.parent
                    n_part = f" | {neighborhood_name}" if neighborhood_name else ""
                    n_desc = f"📍 שכונה: {neighborhood_name}\n" if neighborhood_name else ""
                    group_title = f"🏠 Localis | {c_name}{n_part} | רחוב {node.name}"
                    description = (
                        f"ברוכים הבאים לקהילת רחוב {node.name}.\n\n"
                        f"הקבוצה מיועדת לתושבי הרחוב ומטרתה לשפר את התקשורת בין השכנים, לשתף מידע רלוונטי, לדווח על תקלות, לעזור אחד לשני ולחזק את הקהילה המקומית.\n\n"
                        f"📍 עיר: {c_name}\n"
                        f"{n_desc}"
                        f"📍 רחוב: {node.name}\n"
                        f"👥 קהל יעד: תושבי הרחוב"
                    )
                elif level == "BUILDING":
                    c_name = city_name or "העיר"
                    neighborhood_name = ""
                    curr = node.parent
                    while curr:
                        if curr.level == "NEIGHBORHOOD":
                            neighborhood_name = curr.name
                            break
                        curr = curr.parent
                    n_part = f" | {neighborhood_name}" if neighborhood_name else ""
                    n_desc = f"📍 שכונה: {neighborhood_name}\n" if neighborhood_name else ""
                    group_title = f"🔒 Localis | {c_name}{n_part} | רחוב {node.name}"
                    description = (
                        f"ברוכים הבאים לקהילת דיירי הבניין.\n\n"
                        f"זוהי קבוצה פרטית המיועדת לדיירים המאומתים של הבניין בלבד.\n\n"
                        f"בקבוצה ניתן לדון בנושאי ועד בית, תחזוקה, חניה, אבטחה, משלוחים, התראות חשובות וכל נושא הקשור לחיי היומיום בבניין.\n\n"
                        f"📍 עיר: {c_name}\n"
                        f"{n_desc}"
                        f"📍 כתובת: רחוב {node.name}\n\n"
                        f"🔒 הכניסה לקבוצה מחייבת אימות דייר.\n"
                        f"🔒 רק דיירים מאומתים יכולים להישאר חברים בקבוצה.\n"
                        f"🔒 אימות תקופתי עשוי להתבצע לצורך שמירה על פרטיות וביטחון הדיירים.\n\n"
                        f"🤝 קהילה חזקה מתחילה מהבניין שבו אתם גרים."
                    )
                
                coords_dict = {"latitude": node.latitude, "longitude": node.longitude, "radius": node.radius}
                
                if level == "CITY" and custom_city_group:
                    tg_info = custom_city_group
                else:
                    from backend.services.telegram_userbot import create_telegram_group
                    tg_info = await create_telegram_group(node.name, node.level, node_id=node.id, group_title=group_title, description=description, coords=coords_dict, country_name=pending_path[0] if pending_path else None)
                gtype = "PRIVATE" if level == "BUILDING" else "PUBLIC"
                tg_group = models.GroupChat(
                    location_id=node.id,
                    platform="TELEGRAM",
                    chat_id=tg_info["chat_id"],
                    type=gtype,
                    invite_link=tg_info["invite_link"]
                )
                db.add(tg_group)
                
                wa_chat_id = f"wa_chat_{node.name.lower().replace(' ', '_')}"
                wa_group = models.GroupChat(
                    location_id=node.id,
                    platform="WHATSAPP",
                    chat_id=wa_chat_id,
                    type=gtype,
                    invite_link=f"https://chat.whatsapp.com/{wa_chat_id}"
                )
                db.add(wa_group)
                db.commit()
                
                parent_id = node.id
                last_request_id = None
                created_count += 1
            else:
                comm_req = models.CommunityRequest(
                    user_id=user.id,
                    parent_id=parent_id,
                    parent_request_id=last_request_id,
                    name=name,
                    level=level,
                    status="PENDING",
                    proof_url=proof_url if level == "BUILDING" else None
                )
                db.add(comm_req)
                db.commit()
                db.refresh(comm_req)
                
                last_request_id = comm_req.id
                parent_id = None
                requested_count += 1
                
    USER_STATES[telegram_id] = {}
    
    msg = "✅ Done!\n"
    if created_count > 0:
        msg += f"- Created {created_count} groups directly.\n"
    if requested_count > 0:
        msg += f"- Submitted {requested_count} creation requests for admin review.\n"
    
    await send_message(chat_id, msg)

async def process_location_search(chat_id: str, db: Session, user: models.User, lat: float = None, lon: float = None, address_text: str = None):
    from backend.services.geocoding import reverse_geocode, geocode_text
    
    if lat is not None and lon is not None:
        await send_message(chat_id, "🔍 *Reverse geocoding your coordinates...*")
        addr_info = await reverse_geocode(lat, lon)
    elif address_text:
        await send_message(chat_id, f"🔍 *Searching address:* {address_text}...")
        addr_info = await geocode_text(address_text)
    else:
        return

    if not addr_info or not addr_info.get("country"):
        await send_message(
            chat_id, 
            "❌ Could not resolve the location. Please make sure the address is correct and try again."
        )
        return

    country = addr_info["country"]
    city = addr_info["city"]
    neighborhood = addr_info["neighborhood"]
    
    def names_match(n1: str, n2: str) -> bool:
        if not n1 or not n2:
            return False
        def clean(s):
            return "".join(c for c in s.lower() if c.isalnum() or (u"\u0590" <= c <= u"\u05fe"))
        c1, c2 = clean(n1), clean(n2)
        if c1 == c2:
            return True
        english_batyam = {"batyam", "bat-yam", "bat yam"}
        hebrew_batyam = {"בתים", "בת-ים", "בת ים"}
        if (c1 in english_batyam or n1.lower() in english_batyam) and (c2 in hebrew_batyam or n2.lower() in hebrew_batyam):
            return True
        if (c2 in english_batyam or n2.lower() in english_batyam) and (c1 in hebrew_batyam or n1.lower() in hebrew_batyam):
            return True
        return False

    if neighborhood and city and names_match(neighborhood, city):
        neighborhood = None
    street = addr_info["street"]
    building = addr_info["building"]

    from backend.services.location import get_israel_district_for_city
    path_items = [("COUNTRY", country)]
    if country.lower().strip() == "israel" and city:
        district = get_israel_district_for_city(city)
        if district:
            path_items.append(("DISTRICT", district))
    path_items.extend([
        ("CITY", city),
        ("NEIGHBORHOOD", neighborhood),
        ("STREET", street),
        ("BUILDING", building)
    ])

    await send_message(
        chat_id,
        f"🗺️ *Resolved Location:*\n"
        f"📍 Country: {country or '-'}\n"
        f"🏙️ City: {city or '-'}\n"
        f"🏘️ Neighborhood: {neighborhood or '-'}\n"
        f"🛣️ Street: {street or '-'}\n"
        f"🏢 Building: {building or '-'}"
    )

    matched_nodes = []
    parent_id = None
    missing_items = []

    for level, name in path_items:
        if not name:
            continue
        
        node = db.query(models.LocationNode).filter(
            models.LocationNode.name.ilike(name),
            models.LocationNode.level == level,
            models.LocationNode.parent_id == parent_id
        ).first()

        if node:
            matched_nodes.append(node)
            parent_id = node.id
        else:
            missing_items.append((level, name, parent_id))

    if matched_nodes:
        response_text = "✨ *Matched Groups Found:*\n\n"
        for node in matched_nodes:
            groups = db.query(models.GroupChat).filter(models.GroupChat.location_id == node.id).all()
            response_text += f"📍 *{node.name}* ({node.level.title()}):\n"
            if groups:
                for g in groups:
                    response_text += f"- [{g.platform.title()} {g.type.title()} Chat]({g.invite_link})\n"
            else:
                response_text += "- No group links configured.\n"
            response_text += "\n"
        await send_message(chat_id, response_text)

    if missing_items:
        USER_STATES[str(user.telegram_id)] = {
            "pending_path": [item[1] for item in path_items if item[1]],
            "missing_levels": [item[0] for item in missing_items],
            "path_items": [(item[0], item[1]) for item in path_items if item[1]]
        }
        
        missing_desc = " > ".join([item[1] for item in missing_items])
        await send_message(
            chat_id,
            f"❓ Some groups do not exist yet:\n* {missing_desc} *\n\nWould you like to request to create these community groups?",
            reply_markup={
                "inline_keyboard": [[
                    {"text": "➕ Yes, request creation", "callback_data": "req_missing_path"}
                ]]
            }
        )

