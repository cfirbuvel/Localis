from sqlalchemy.orm import Session
from backend.models import LocationNode, GroupChat
from typing import List, Set, Optional

COUNTRY_TRANSLATIONS = {
    "ישראל": "Israel",
    "israel": "Israel",
    "russia": "Russia",
    "россия": "Russia",
    "usa": "United States",
    "united states": "United States",
    "ארצות הברית": "United States",
    "ארהב": "United States",
    "france": "France",
    "צרפת": "France",
    "germany": "Germany",
    "גרמניה": "Germany",
    "italy": "Italy",
    "איטליה": "Italy",
    "spain": "Spain",
    "ספרד": "Spain",
    "canada": "Canada",
    "קנדה": "Canada",
    "ukraine": "Ukraine",
    "אוקראינה": "Ukraine",
    "united kingdom": "United Kingdom",
    "בריטניה": "United Kingdom",
    "אנגליה": "United Kingdom",
    "england": "United Kingdom",
}

CITY_TRANSLATIONS = {
    "תל אביב": "Tel Aviv",
    "תל אביב יפו": "Tel Aviv",
    "תל אביב - יפו": "Tel Aviv",
    "תל-אביב": "Tel Aviv",
    "tel aviv": "Tel Aviv",
    "tel aviv-yafo": "Tel Aviv",
    "jerusalem": "Jerusalem",
    "ירושלים": "Jerusalem",
    "haifa": "Haifa",
    "חיפה": "Haifa",
    "rishon lezion": "Rishon LeZion",
    "ראשון לציון": "Rishon LeZion",
    "ראשלצ": "Rishon LeZion",
    "petah tikva": "Petah Tikva",
    "פתח תקווה": "Petah Tikva",
    "פתח-תקווה": "Petah Tikva",
    "netanya": "Netanya",
    "נתניה": "Netanya",
    "beersheba": "Beersheba",
    "beer sheva": "Beersheba",
    "באר שבע": "Beersheba",
    "באר-שבע": "Beersheba",
    "holon": "Holon",
    "חולון": "Holon",
    "bat yam": "Bat Yam",
    "bat-yam": "Bat Yam",
    "בת ים": "Bat Yam",
    "בת-ים": "Bat Yam",
    "בתים": "Bat Yam",
    "rehovot": "Rehovot",
    "רחובות": "Rehovot",
    "ashdod": "Ashdod",
    "אשדוד": "Ashdod",
    "ashkelon": "Ashkelon",
    "אשקלון": "Ashkelon",
    "herzliya": "Herzliya",
    "הרצליה": "Herzliya",
    "givatayim": "Givatayim",
    "גבעתיים": "Givatayim",
    "ramat gan": "Ramat Gan",
    "רמת גן": "Ramat Gan",
    "רמת-גן": "Ramat Gan",
    "ra'anana": "Ra'anana",
    "רעננה": "Ra'anana",
    "kfar saba": "Kfar Saba",
    "כפר סבא": "Kfar Saba",
    "כפר-סבא": "Kfar Saba",
    "hadera": "Hadera",
    "חדרה": "Hadera",
    "modi'in": "Modi'in",
    "מודיעין": "Modi'in",
}

def normalize_location_name(name: str, level: str) -> str:
    if not name:
        return name
    name_clean = name.lower().strip()
    name_clean = " ".join(name_clean.split())
    
    if level == "COUNTRY":
        for k, v in COUNTRY_TRANSLATIONS.items():
            if k.lower() == name_clean:
                return v
    elif level == "CITY":
        for k, v in CITY_TRANSLATIONS.items():
            if k.lower() == name_clean:
                return v
    return name

def get_location_ancestors(db: Session, location_id: int) -> List[int]:
    """
    Returns list of ancestor location IDs from nearest parent to root.
    E.g. Building -> Street -> Neighborhood -> City -> Country
    """
    ancestors = []
    current_id = location_id
    while current_id:
        node = db.query(LocationNode).filter(LocationNode.id == current_id).first()
        if not node or not node.parent_id:
            break
        ancestors.append(node.parent_id)
        current_id = node.parent_id
    return ancestors

def get_location_descendants(db: Session, location_id: int) -> Set[int]:
    descendants = {c.id for c in db.query(LocationNode).filter(LocationNode.parent_id == location_id).all()}
    return descendants.union(*(get_location_descendants(db, d_id) for d_id in list(descendants)))

def is_descendant_of(db: Session, child_id: int, parent_id: int) -> bool:
    """
    Checks if a node is a descendant of another node.
    """
    if not child_id or not parent_id:
        return False
    if child_id == parent_id:
        return True
    ancestors = get_location_ancestors(db, child_id)
    return parent_id in ancestors

def get_country_flag(country_name: str) -> str:
    mapping = {
        "israel": "🇮🇱",
        "united states": "🇺🇸",
        "united kingdom": "🇬🇧",
        "france": "🇫🇷",
        "germany": "🇩🇪",
        "italy": "🇮🇹",
        "spain": "🇪🇸",
        "canada": "🇨🇦",
        "australia": "🇦🇺"
    }
    return mapping.get(country_name.lower().strip(), "🏳️")

def get_israel_district_for_city(city_name: str) -> Optional[str]:
    if not city_name:
        return None
    city = city_name.lower().strip()
    
    def clean(s):
        return "".join(c for c in s.lower() if c.isalnum() or (u"\u0590" <= c <= u"\u05fe"))
    
    c = clean(city)
    
    tel_aviv_cities = {clean(x) for x in ["Tel Aviv", "Tel Aviv-Yafo", "תל אביב", "תל אביב - יפו", "תל-אביב", "Givatayim", "גבעתיים", "Ramat Gan", "רמת גן", "רמת-גן", "Holon", "חולון", "Bat Yam", "בת ים", "בת-ים", "Herzliya", "הרצליה", "Or Yehuda", "אור יהודה", "Kiryat Ono", "קרית אונו", "Bnei Brak", "בני ברק"]}
    jerusalem_cities = {clean(x) for x in ["Jerusalem", "ירושלים", "Beit Shemesh", "בית שמש", "Mevaseret Zion", "מבשרת ציון"]}
    haifa_cities = {clean(x) for x in ["Haifa", "חיפה", "Hadera", "חדרה", "Nesher", "נשר", "Tirat Carmel", "טירת כרמל", "Umm al-Fahm", "אום אל-פחם", "Kiryat Ata", "קרית אתא", "Kiryat Motzkin", "קרית מוצקין", "Kiryat Yam", "קרית ים", "Kiryat Bialik", "קרית ביאליק"]}
    north_cities = {clean(x) for x in ["Nazareth", "נצרת", "Tiberias", "טבריה", "Acre", "Akko", "עכו", "Afula", "עפולה", "Bet She'an", "בית שאן", "Karmiel", "כרמיאל", "Ma'alot-Tarshiha", "מעלות תרשיחא", "Migdal HaEmek", "מגדל העמק", "Nahariya", "נהריה", "Kiryat Shmona", "קרית שמונה", "Sakhnin", "סחנין", "Shefa-Amr", "שפרעם", "Safed", "Tzfat", "צפת", "Tamra", "טמרה"]}
    center_cities = {clean(x) for x in ["Rishon LeZion", "ראשון לציון", "Petah Tikva", "פתח תקווה", "Netanya", "נתניה", "Rehovot", "רחובות", "Hod HaSharon", "הוד השרון", "Kfar Saba", "כפר סבא", "Lod", "לוד", "Modi'in", "מודיעין", "Ness Ziona", "נס ציונה", "Ra'anana", "רעננה", "Ramla", "רמלה", "Rosh HaAyin", "ראש העין", "Tayibe", "טייבה", "Tira", "טירה", "Yavne", "יבנה", "Yehud", "יהוד"]}
    south_cities = {clean(x) for x in ["Beersheba", "Beer Sheva", "באר שבע", "Ashdod", "אשדוד", "Ashkelon", "אשקלון", "Eilat", "אילת", "Dimona", "דימונה", "Arad", "ערד", "Kiryat Gat", "קרית גת", "Kiryat Malakhi", "קרית מלאכי", "Netivot", "נתיבות", "Ofakim", "אופקים", "Rahat", "רהט", "Sderot", "שדרות"]}

    if c in tel_aviv_cities or "telaviv" in c or "גבעתיים" in city or "חולון" in city or "בתים" in c:
        return "מחוז תל אביב"
    if c in jerusalem_cities or "ירושלים" in city:
        return "מחוז ירושלים"
    if c in haifa_cities or "חיפה" in city:
        return "מחוז חיפה"
    if c in north_cities or "נצרת" in city or "טבריה" in city or "עכו" in city:
        return "מחוז צפון"
    if c in center_cities or "פתח" in city or "נתניה" in city or "ראשון" in city or "רחובות" in city:
        return "מחוז מרכז"
    if c in south_cities or "שבע" in city or "אשדוד" in city or "אשקלון" in city or "אילת" in city:
        return "מחוז דרום"
        
    return "מחוז מרכז"

def get_child_level(parent_level: str, parent_name: str = None) -> Optional[str]:
    if parent_level == "COUNTRY":
        if parent_name and "israel" in parent_name.lower():
            return "DISTRICT"
        return "CITY"
    if parent_level == "DISTRICT":
        return "CITY"
    if parent_level == "CITY":
        return "NEIGHBORHOOD"
    if parent_level == "NEIGHBORHOOD":
        return "STREET"
    if parent_level == "STREET":
        return "BUILDING"
    return None

def get_city_name_for_node(db: Session, node: LocationNode) -> Optional[str]:
    if node.level == "CITY":
        return node.name
    curr = node.parent
    while curr:
        if curr.level == "CITY":
            return curr.name
        curr = curr.parent
    return None

async def geocode_node_coordinates_live(db: Session, node: LocationNode) -> tuple[Optional[float], Optional[float]]:
    parts = []
    curr = node
    while curr:
        if curr.level != "DISTRICT":
            name = curr.name
            # Avoid duplicating parent names that are already part of child names (e.g. "Street, Street 5")
            if not any(name in p for p in parts):
                parts.append(name)
        curr = curr.parent
    parts.reverse()
    address = ", ".join(parts)
    from backend.services.geocoding import geocode_text
    try:
        res = await geocode_text(address)
        if res and res.get("latitude") is not None and res.get("longitude") is not None:
            return res["latitude"], res["longitude"]
    except Exception as e:
        print(f"Error geocoding node {node.name}: {e}")
        
    # Fallback to parent coordinates
    curr = node.parent
    while curr:
        if curr.latitude is not None and curr.longitude is not None:
            return curr.latitude, curr.longitude
        curr = curr.parent
        
    return None, None

def auto_create_node_path(db: Session, path: List[str]) -> Optional[LocationNode]:
    """
    Auto-creates location tree nodes if missing.
    path: List of names in hierarchy order: [Country, City, Neighborhood, Street, Building]
    """
    if not path:
        return None

    # Preprocess Israel to insert District level automatically
    if path[0].lower().strip() == "israel" and len(path) > 1:
        # Check if the district level is already explicitly present in the path
        districts = {"מחוז ירושלים", "מחוז תל אביב", "מחוז חיפה", "מחוז צפון", "מחוז מרכז", "מחוז דרום"}
        city_candidate = path[1]
        if city_candidate not in districts:
            district = get_israel_district_for_city(city_candidate)
            if district:
                path.insert(1, district)

    parent_id = None
    last_node = None

    for idx, name in enumerate(path):
        name = name.strip()
        if not name:
            continue
            
        if idx == 0:
            level = "COUNTRY"
        else:
            level = get_child_level(last_node.level, last_node.name)

        # Normalize name (e.g. Hebrew -> English)
        name = normalize_location_name(name, level)

        # Check if node already exists at this level with this parent (case-insensitive)
        node = db.query(LocationNode).filter(
            LocationNode.name.ilike(name),
            LocationNode.level == level,
            LocationNode.parent_id == parent_id
        ).first()

        if not node:
            print(f"Auto-creating node: {name} ({level}) under parent_id {parent_id}")
            node = LocationNode(name=name, level=level, parent_id=parent_id)
            
            # Set radius default values based on level
            radius_map = {
                "CITY": 2000.0,
                "NEIGHBORHOOD": 800.0,
                "STREET": 250.0,
                "BUILDING": 50.0
            }
            if level in radius_map:
                node.radius = radius_map[level]

            db.add(node)
            db.commit()
            db.refresh(node)

            # Auto-create mock groups for the newly created node
            gtype = "PRIVATE" if level == "BUILDING" else "PUBLIC"
            tg_chat_id = f"tg_chat_{name.lower().replace(' ', '_')}"
            
            existing_tg = db.query(GroupChat).filter(
                GroupChat.location_id == node.id,
                GroupChat.platform == "TELEGRAM"
            ).first()
            if not existing_tg:
                tg_group = GroupChat(
                    location_id=node.id,
                    platform="TELEGRAM",
                    chat_id=tg_chat_id,
                    type=gtype,
                    invite_link=f"https://t.me/joinchat/{tg_chat_id}"
                )
                db.add(tg_group)

            wa_chat_id = f"wa_chat_{name.lower().replace(' ', '_')}"
            existing_wa = db.query(GroupChat).filter(
                GroupChat.location_id == node.id,
                GroupChat.platform == "WHATSAPP"
            ).first()
            if not existing_wa:
                wa_group = GroupChat(
                    location_id=node.id,
                    platform="WHATSAPP",
                    chat_id=wa_chat_id,
                    type=gtype,
                    invite_link=f"https://chat.whatsapp.com/{wa_chat_id}"
                )
                db.add(wa_group)
            db.commit()

        parent_id = node.id
        last_node = node

    return last_node


async def approve_request_and_hierarchy(
    db: Session,
    req,
    custom_group_chat_id: str = None,
    custom_group_invite_link: str = None,
    action_by: str = "Admin",
    telegram_chat_id: str = None,
    telegram_message_id: int = None
):
    from backend import models
    from backend.services.telegram_userbot import create_telegram_group
    from backend.services.bot_telegram import send_message, notify_admins_request_update

    # 1. Collect all pending parent requests upward
    ancestors = []
    curr = req
    while curr.parent_request_id is not None:
        parent_req = db.query(models.CommunityRequest).filter(
            models.CommunityRequest.id == curr.parent_request_id,
            models.CommunityRequest.status == "PENDING"
        ).first()
        if not parent_req:
            break
        ancestors.append(parent_req)
        curr = parent_req
    
    # Process from top to bottom (ancestors first)
    pending_chain = list(reversed(ancestors)) + [req]

    last_created_node = None

    for idx, r in enumerate(pending_chain):
        if telegram_chat_id and telegram_message_id:
            progress_text = "⚙️ *Processing Hierarchy Approval:*\n\n"
            for step_idx, item in enumerate(pending_chain):
                if step_idx < idx:
                    progress_text += f"🟢 {item.name} ({item.level.title()}) - Created\n"
                elif step_idx == idx:
                    progress_text += f"🟡 {item.name} ({item.level.title()}) - Creating...\n"
                else:
                    progress_text += f"⚪ {item.name} ({item.level.title()}) - Waiting\n"
            from backend.services.bot_telegram import edit_message
            await edit_message(telegram_chat_id, telegram_message_id, progress_text)
        # Check if already approved (in case of duplicate runs, though here we loop in a transaction)
        if r.status == "APPROVED":
            # If already approved, find its node to link the next one
            node = db.query(models.LocationNode).filter(
                models.LocationNode.name.ilike(r.name),
                models.LocationNode.level == r.level,
                models.LocationNode.parent_id == r.parent_id
            ).first()
            if node:
                last_created_node = node
            continue

        # If it's a child in the chain, its parent_id should point to the last created node
        if last_created_node:
            r.parent_id = last_created_node.id
            r.parent_request_id = None
            db.commit()

        # Approve this request
        r.status = "APPROVED"
        db.commit()

        # Create Location Node
        normalized_name = normalize_location_name(r.name, r.level)
        existing_node = db.query(models.LocationNode).filter(
            models.LocationNode.name.ilike(normalized_name),
            models.LocationNode.level == r.level,
            models.LocationNode.parent_id == r.parent_id
        ).first()

        if existing_node:
            new_node = existing_node
        else:
            new_node = models.LocationNode(
                name=normalized_name,
                level=r.level,
                parent_id=r.parent_id,
                created_by_id=r.user_id
            )
            db.add(new_node)
            db.commit()
            db.refresh(new_node)

        last_created_node = new_node

        # Update child requests waiting for this parent request (if any others exist outside the chain)
        child_reqs = db.query(models.CommunityRequest).filter(
            models.CommunityRequest.parent_request_id == r.id
        ).all()
        for child in child_reqs:
            child.parent_id = new_node.id
            child.parent_request_id = None
        db.commit()

        # Radius map
        radius_map = {"CITY": 2000.0, "NEIGHBORHOOD": 800.0, "STREET": 250.0, "BUILDING": 50.0}
        if new_node.level in radius_map and not new_node.radius:
            new_node.radius = radius_map[new_node.level]
            db.commit()

        # Geocode coordinates live
        if new_node.latitude is None or new_node.longitude is None:
            lat, lon = await geocode_node_coordinates_live(db, new_node)
            if lat is not None and lon is not None:
                new_node.latitude = lat
                new_node.longitude = lon
                db.commit()

        # Find country flag & name
        country_name = None
        curr_p = new_node
        while curr_p:
            if curr_p.level == "COUNTRY":
                country_name = curr_p.name
                break
            curr_p = curr_p.parent

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
            curr_p = new_node.parent
            while curr_p:
                if curr_p.level == "NEIGHBORHOOD":
                    neighborhood_name = curr_p.name
                    break
                curr_p = curr_p.parent
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
            curr_p = new_node.parent
            while curr_p:
                if curr_p.level == "NEIGHBORHOOD":
                    neighborhood_name = curr_p.name
                    break
                curr_p = curr_p.parent
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

        # Create Groups
        gtype = "PRIVATE" if new_node.level == "BUILDING" else "PUBLIC"

        # For the target request, if custom group credentials were provided, use them
        if r.id == req.id and custom_group_chat_id and custom_group_invite_link:
            tg_chat_id = custom_group_chat_id
            tg_invite_link = custom_group_invite_link
        else:
            tg_info = await create_telegram_group(
                new_node.name,
                new_node.level,
                node_id=new_node.id,
                group_title=group_title,
                description=description,
                coords=coords_dict,
                country_name=country_name
            )
            tg_chat_id = tg_info["chat_id"]
            tg_invite_link = tg_info["invite_link"]

        # Check if group already exists
        existing_tg = db.query(models.GroupChat).filter(
            models.GroupChat.location_id == new_node.id,
            models.GroupChat.platform == "TELEGRAM"
        ).first()
        if existing_tg:
            existing_tg.chat_id = tg_chat_id
            existing_tg.invite_link = tg_invite_link
            existing_tg.type = gtype
        else:
            tg_group = models.GroupChat(
                location_id=new_node.id,
                platform="TELEGRAM",
                chat_id=tg_chat_id,
                type=gtype,
                invite_link=tg_invite_link
            )
            db.add(tg_group)

        # WhatsApp Mock Group
        wa_chat_id = f"wa_chat_{new_node.name.lower().replace(' ', '_')}"
        existing_wa = db.query(models.GroupChat).filter(
            models.GroupChat.location_id == new_node.id,
            models.GroupChat.platform == "WHATSAPP"
        ).first()
        if existing_wa:
            existing_wa.chat_id = wa_chat_id
            existing_wa.invite_link = f"https://chat.whatsapp.com/{wa_chat_id}"
            existing_wa.type = gtype
        else:
            wa_group = models.GroupChat(
                location_id=new_node.id,
                platform="WHATSAPP",
                chat_id=wa_chat_id,
                type=gtype,
                invite_link=f"https://chat.whatsapp.com/{wa_chat_id}"
            )
            db.add(wa_group)
        db.commit()

        # Notify user
        if r.user.telegram_id:
            msg = (
                f"🎉 *Good news!*\nYour request to create the community *{r.name}* ({r.level.title()}) has been approved!\n\n"
                f"You can join the new group here:\n"
                f"👉 [Telegram Chat]({tg_invite_link})\n"
                f"👉 [WhatsApp Chat](https://chat.whatsapp.com/{wa_chat_id})"
            )
            await send_message(r.user.telegram_id, msg)

        # Notify admins of the status update for this node
        await notify_admins_request_update(db, r, action_by, r.status)

    if telegram_chat_id and telegram_message_id:
        final_text = "✅ *Hierarchy Approval Completed!*\n\n"
        for item in pending_chain:
            final_text += f"🟢 {item.name} ({item.level.title()}) - Success\n"
        from backend.services.bot_telegram import edit_message
        keyboard = [[{"text": "⬅️ Back to Requests", "callback_data": "admin_req_list"}]]
        await edit_message(telegram_chat_id, telegram_message_id, final_text, reply_markup={"inline_keyboard": keyboard})

    return last_created_node
