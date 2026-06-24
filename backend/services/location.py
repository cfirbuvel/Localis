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
            parts.append(curr.name)
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
            tg_group = GroupChat(
                location_id=node.id,
                platform="TELEGRAM",
                chat_id=tg_chat_id,
                type=gtype,
                invite_link=f"https://t.me/joinchat/{tg_chat_id}"
            )
            db.add(tg_group)

            wa_chat_id = f"wa_chat_{name.lower().replace(' ', '_')}"
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
