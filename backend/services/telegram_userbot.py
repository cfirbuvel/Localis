import os
import logging
from backend import config

logger = logging.getLogger("telegram_userbot")

# Try importing Telethon; if not installed, fail silently or fallback to mock
try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.channels import CreateChannelRequest
    from telethon.tl.functions.messages import ExportChatInviteRequest
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

async def create_telegram_group(node_name: str, level: str, node_id: int = None, group_title: str = None, description: str = None, coords: dict = None, country_name: str = None) -> dict:
    """
    Creates a Telegram Supergroup using Telethon Userbot if configured.
    Falls back to generating mock invite links and credentials if credentials are not fully present.
    Returns: {"chat_id": str, "invite_link": str}
    """
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_string = os.getenv("TELEGRAM_SESSION_STRING")

    # If telethon or env vars are missing, run in mock mode
    if not TELETHON_AVAILABLE or not api_id or not api_hash or not session_string:
        logger.warning(
            "Telethon is not fully configured (missing TELEGRAM_SESSION_STRING in .env). "
            "Using mock Telegram group creation."
        )
        mock_id = f"tg_chat_{node_name.lower().replace(' ', '_')}"
        username = f"localis_{level.lower()}_{node_id}" if node_id and level != "BUILDING" else None
        if username:
            return {
                "chat_id": f"@{username}",
                "invite_link": f"https://t.me/{username}"
            }
        return {
            "chat_id": mock_id,
            "invite_link": f"https://t.me/joinchat/{mock_id}"
        }

    import asyncio
    logger.info("Sleeping 3 seconds before Telegram group creation to prevent rate limits...")
    await asyncio.sleep(3.0)

    try:
        # Initialize client with StringSession
        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        await client.connect()
        
        # Verify authorized
        if not await client.is_user_authorized():
            logger.error("Telegram Userbot is not authorized. Please check your session string.")
            await client.disconnect()
            mock_id = f"tg_chat_{node_name.lower().replace(' ', '_')}"
            return {
                "chat_id": mock_id,
                "invite_link": f"https://t.me/joinchat/{mock_id}"
            }

        # Create Channel (megagroup=True makes it a Supergroup)
        chat_desc = description or f"Official Localis group chat for the {level.lower()}: {node_name}."
        title = group_title or f"Localis: {node_name}"
        result = await client(CreateChannelRequest(
            title=title,
            about=chat_desc,
            megagroup=True
        ))

        # Get channel details
        channel = result.chats[0]
        channel_id = channel.id

        # Edit Photo if coords provided
        if coords and coords.get("latitude") is not None and coords.get("longitude") is not None:
            lat = coords["latitude"]
            lon = coords["longitude"]
            radius = coords.get("radius", 500)
            
            zoom = 14
            if level == "CITY":
                zoom = 12
            elif level == "NEIGHBORHOOD":
                zoom = 14
            elif level == "STREET":
                zoom = 16
            elif level == "BUILDING":
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
            
            # Get map locale
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
            
            import httpx
            import tempfile
            try:
                async with httpx.AsyncClient() as http_client:
                    img_res = await http_client.get(map_url, timeout=10.0)
                    if img_res.status_code == 200:
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                            tmp.write(img_res.content)
                            tmp_path = tmp.name
                        
                        from telethon.tl.functions.channels import EditPhotoRequest
                        from telethon.tl.types import InputChatUploadedPhoto
                        uploaded_file = await client.upload_file(tmp_path)
                        await client(EditPhotoRequest(channel=channel, photo=InputChatUploadedPhoto(uploaded_file)))
                        os.unlink(tmp_path)
            except Exception as ex:
                logger.error(f"Failed to set static map chat photo: {ex}")

        # Update username to make it public if not BUILDING and node_id is provided
        username = f"localis_{level.lower()}_{node_id}" if node_id and level != "BUILDING" else None
        invite_link = None
        chat_id = f"-100{channel_id}"

        if username:
            try:
                from telethon.tl.functions.channels import UpdateUsernameRequest
                await client(UpdateUsernameRequest(channel=channel, username=username))
                invite_link = f"https://t.me/{username}"
            except Exception as ue:
                logger.error(f"Failed to assign public username @{username} to channel: {ue}")

        if not invite_link:
            # Fallback to private invite link if not public or username assignment failed
            request_needed = True if level == "BUILDING" else None
            invite = await client(ExportChatInviteRequest(peer=channel, request_needed=request_needed))
            invite_link = invite.link

        # Add the Telegram Bot to the group and promote to admin
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if bot_token and ":" in bot_token:
            try:
                bot_id = int(bot_token.split(":")[0])
                from telethon.tl.functions.channels import InviteToChannelRequest, EditAdminRequest
                from telethon.tl.types import ChatAdminRights
                
                # Invite the bot
                await client(InviteToChannelRequest(channel=channel, users=[bot_id]))
                logger.info(f"Invited bot {bot_id} to group {channel_id}")
                
                # Promote the bot to admin so it can read messages bypassing privacy mode
                await client(EditAdminRequest(
                    channel=channel,
                    user_id=bot_id,
                    admin_rights=ChatAdminRights(
                        change_info=True,
                        post_messages=True,
                        edit_messages=True,
                        delete_messages=True,
                        ban_users=True,
                        invite_users=True,
                        pin_messages=True,
                        add_admins=False,
                        manage_call=True
                    ),
                    rank="Bot Admin"
                ))
                logger.info(f"Promoted bot {bot_id} to admin in group {channel_id}")
            except Exception as e:
                logger.error(f"Failed to add/promote Telegram Bot in group: {e}")

        await client.disconnect()
        return {
            "chat_id": chat_id,
            "invite_link": invite_link
        }

    except Exception as e:
        logger.exception(f"Error creating Telegram group via userbot: {e}")
        mock_id = f"tg_chat_{node_name.lower().replace(' ', '_')}"
        return {
            "chat_id": mock_id,
            "invite_link": f"https://t.me/joinchat/{mock_id}"
        }

async def get_telegram_link_metadata(invite_link: str) -> dict:
    """
    Fetches the public preview page of a Telegram channel/group to extract its title.
    """
    import httpx
    import re
    import html

    default_title = invite_link.replace("https://", "").replace("http://", "")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        async with httpx.AsyncClient() as client:
            res = await client.get(invite_link, headers=headers, timeout=3.0)
            if res.status_code == 200:
                title_match = re.search(r'<meta property="og:title" content="([^"]+)"', res.text)
                if title_match:
                    return {"title": html.unescape(title_match.group(1)), "invite_link": invite_link}
                    
                title_div = re.search(r'<div class="tgme_page_title"[^>]*>(.*?)</div>', res.text, re.DOTALL)
                if title_div:
                    title = re.sub(r'<[^>]+>', '', title_div.group(1)).strip()
                    return {"title": html.unescape(title), "invite_link": invite_link}
    except Exception as e:
        logger.warning(f"Error fetching metadata for {invite_link}: {e}")
        
    return {"title": default_title, "invite_link": invite_link}

async def scrape_web_telegram_links(query: str) -> list:
    """
    Searches Bing for site:t.me with query and returns unique invite links.
    """
    import httpx
    import re
    import urllib.parse

    links = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    search_queries = [
        f"site:t.me עיריית {query}",
        f"site:t.me {query}"
    ]
    
    async with httpx.AsyncClient() as client:
        for sq in search_queries:
            try:
                res = await client.get('https://www.bing.com/search', params={'q': sq}, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    found = re.findall(r'(https?://(?:t\.me|telegram\.me)/[a-zA-Z0-9_\+\-/]+)', res.text)
                    for link in found:
                        cleaned = link.split('&')[0].split('"')[0].split("'")[0].split('<')[0].split('>')[0].rstrip('.,;)')
                        parts = cleaned.replace("http://", "").replace("https://", "").split("/")
                        if len(parts) >= 2:
                            handle = parts[1]
                            if handle in ("", "s", "c", "share", "addstickers", "setlanguage", "contact"):
                                continue
                            if cleaned not in links:
                                links.append(cleaned)
            except Exception as e:
                logger.error(f"Error scraping web groups for '{sq}': {e}")
                
    return links

def slugify_to_ascii(text: str) -> str:
    mapping = {
        "בת ים": "bat_yam",
        "בת-ים": "bat_yam",
        "חולון": "holon",
        "תל אביב": "tel_aviv",
        "תל-אביב": "tel_aviv",
        "ירושלים": "jerusalem",
        "חיפה": "haifa",
        "ראשון לציון": "rishon_lezion",
        "פתח תקווה": "petah_tikva",
        "אשדוד": "ashdod",
        "נתניה": "netanya"
    }
    cleaned = text.strip()
    if cleaned in mapping:
        return mapping[cleaned]
        
    translit = []
    heb_map = {
        'א': 'a', 'ב': 'b', 'ג': 'g', 'ד': 'd', 'ה': 'h', 'ו': 'v', 'ז': 'z', 'ח': 'ch', 'ט': 't', 'י': 'y',
        'כ': 'k', 'ך': 'k', 'ל': 'l', 'מ': 'm', 'ם': 'm', 'נ': 'n', 'ן': 'n', 'ס': 's', 'ע': 'a', 'פ': 'p',
        'ף': 'p', 'צ': 'ts', 'ץ': 'ts', 'ק': 'q', 'ר': 'r', 'ש': 'sh', 'ת': 't'
    }
    for char in cleaned.lower():
        if 'a' <= char <= 'z' or '0' <= char <= '9' or char == '_':
            translit.append(char)
        elif char in (' ', '-', '_'):
            translit.append('_')
        elif char in heb_map:
            translit.append(heb_map[char])
            
    res = "".join(translit)
    return res if res else "city"

async def search_public_groups(query: str) -> list:
    """
    Searches globally for Telegram public groups/channels matching query.
    Performs global search with Telethon (if available) and web scrapes Bing for city/municipal groups.
    """
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_string = os.getenv("TELEGRAM_SESSION_STRING")

    # Generate ASCII username compatible with Telegram limits using our helper
    slug = slugify_to_ascii(query)
    
    # Mock suggestions fallback
    mock_suggestions = [
        {
            "title": f"Localis: {query} (Official)",
            "chat_id": f"tg_chat_{slug}_official",
            "invite_link": f"https://t.me/{slug}_official"
        },
        {
            "title": f"{query} Citizens Hub",
            "chat_id": f"tg_chat_{slug}_citizens",
            "invite_link": f"https://t.me/{slug}_citizens"
        }
    ]

    suggestions = []
    seen_links = set()

async def resolve_telegram_link_via_userbot(client, invite_link: str) -> dict:
    """
    Checks if a Telegram link/username is active and retrieves its live title and chat ID.
    Returns: {"title": str, "chat_id": str, "invite_link": str} or None if invalid.
    """
    cleaned = invite_link.replace("http://", "").replace("https://", "")
    parts = cleaned.split("/")
    if len(parts) < 2:
        return None
        
    identifier = parts[1]
    
    # Check if it's an invite link hash
    if identifier.startswith("+") or identifier == "joinchat":
        invite_hash = parts[2] if identifier == "joinchat" and len(parts) >= 3 else identifier[1:]
        try:
            from telethon.tl.functions.messages import CheckChatInviteRequest
            from telethon.tl.types import ChatInviteAlready, ChatInvite
            res = await client(CheckChatInviteRequest(hash=invite_hash))
            
            if isinstance(res, ChatInviteAlready):
                chat = res.chat
                return {
                    "title": getattr(chat, "title", "Telegram Group"),
                    "chat_id": f"-100{chat.id}",
                    "invite_link": invite_link
                }
            elif isinstance(res, ChatInvite):
                return {
                    "title": res.title,
                    "chat_id": invite_link,
                    "invite_link": invite_link
                }
        except Exception:
            return None
    else:
        try:
            from telethon.tl.functions.contacts import ResolveUsernameRequest
            res = await client(ResolveUsernameRequest(username=identifier))
            if res.chats:
                chat = res.chats[0]
                return {
                    "title": chat.title,
                    "chat_id": f"-100{chat.id}",
                    "invite_link": invite_link
                }
        except Exception:
            return None
            
    return None

async def search_public_groups(query: str) -> list:
    """
    Searches globally for Telegram public groups/channels matching query.
    Performs global search with Telethon (if available) and web scrapes Bing for city/municipal groups.
    Validates all candidate links via the active Telethon client.
    """
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_string = os.getenv("TELEGRAM_SESSION_STRING")

    slug = slugify_to_ascii(query)
    
    mock_suggestions = [
        {
            "title": f"Localis: {query} (Official)",
            "chat_id": f"tg_chat_{slug}_official",
            "invite_link": f"https://t.me/{slug}_official"
        },
        {
            "title": f"{query} Citizens Hub",
            "chat_id": f"tg_chat_{slug}_citizens",
            "invite_link": f"https://t.me/{slug}_citizens"
        }
    ]

    # If Telethon is not available or configured, return mock suggestions immediately
    if not TELETHON_AVAILABLE or not api_id or not api_hash or not session_string:
        return mock_suggestions

    suggestions = []
    seen_links = set()
    candidate_links = []

    try:
        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        await client.connect()
        
        if await client.is_user_authorized():
            # 1. Search via Telegram global database
            try:
                from telethon.tl.functions.contacts import SearchRequest
                res1 = await client(SearchRequest(q=query, limit=5))
                res2 = await client(SearchRequest(q=f"עיריית {query}", limit=5))
                
                for result in [res1, res2]:
                    for chat in result.chats:
                        if getattr(chat, "username", None):
                            link = f"https://t.me/{chat.username}"
                            if link not in seen_links:
                                seen_links.add(link)
                                candidate_links.append(link)
            except Exception as se:
                logger.error(f"Error querying Telegram global search: {se}")

            # 2. Search via web scraping
            try:
                web_links = await scrape_web_telegram_links(query)
                for wl in web_links:
                    if wl not in seen_links:
                        seen_links.add(wl)
                        candidate_links.append(wl)
            except Exception as we:
                logger.error(f"Error web scraping search: {we}")

            # 3. Validate candidates and resolve live metadata (limited to first 10 candidates to prevent timeouts)
            for link in candidate_links[:10]:
                resolved = await resolve_telegram_link_via_userbot(client, link)
                if resolved:
                    suggestions.append(resolved)

        await client.disconnect()

    except Exception as e:
        logger.exception(f"Error searching Telegram groups: {e}")

    # Return validated suggestions if userbot is active, otherwise fallback to mock suggestions
    is_userbot_configured = TELETHON_AVAILABLE and api_id and api_hash and session_string
    if is_userbot_configured:
        return suggestions
    return mock_suggestions

async def approve_telegram_group_join(chat_id: str, user_telegram_id: str) -> bool:
    """
    Approves a pending join request for a user in a Telegram group/channel.
    """
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_string = os.getenv("TELEGRAM_SESSION_STRING")

    if not TELETHON_AVAILABLE or not api_id or not api_hash or not session_string:
        logger.warning("Telethon userbot is not configured, skipping live approval.")
        return False

    try:
        # Initialize client
        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error("Telegram Userbot is not authorized.")
            await client.disconnect()
            return False

        # Resolve peer and user
        peer_id = chat_id
        if isinstance(chat_id, str):
            if chat_id.startswith("-") or chat_id.isdigit():
                peer_id = int(chat_id)
        channel = await client.get_entity(peer_id)
        user = await client.get_entity(int(user_telegram_id))

        # Approve join request
        from telethon.tl.functions.messages import HideChatJoinRequestRequest
        await client(HideChatJoinRequestRequest(
            peer=channel,
            user_id=user,
            approved=True
        ))
        await client.disconnect()
        logger.info(f"Successfully approved Telegram group join request for user {user_telegram_id} in {chat_id}")
        return True
    except Exception as e:
        logger.exception(f"Error approving chat join request for user {user_telegram_id} in {chat_id}: {e}")
        return False


async def fetch_group_messages_via_userbot(chat_id: str, limit: int = 50) -> list:
    """
    Fetches the latest messages from a Telegram group using the Userbot client.
    """
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_string = os.getenv("TELEGRAM_SESSION_STRING")

    if not TELETHON_AVAILABLE or not api_id or not api_hash or not session_string:
        logger.warning("Telethon userbot is not configured, skipping live messages fetch.")
        return []

    try:
        peer_id = chat_id
        if isinstance(chat_id, str):
            if chat_id.startswith("-") or chat_id.isdigit():
                peer_id = int(chat_id)
                
        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error("Telegram Userbot is not authorized.")
            await client.disconnect()
            return []

        # Fetch messages
        messages = await client.get_messages(peer_id, limit=limit)
        results = []
        for m in messages:
            if m.text:  # Only text messages
                sender = m.sender
                sender_id = str(m.sender_id) if m.sender_id else ""
                username = getattr(sender, "username", None)
                if not username and sender:
                    first_name = getattr(sender, "first_name", "")
                    last_name = getattr(sender, "last_name", "")
                    username = f"{first_name} {last_name}".strip() or f"User_{sender_id}"
                
                results.append({
                    "platform": "TELEGRAM",
                    "chat_id": chat_id,
                    "user_id": sender_id,
                    "username": username or f"TG_{sender_id}",
                    "message_text": m.text,
                    "timestamp": m.date
                })
        await client.disconnect()
        return results
    except Exception as e:
        logger.exception(f"Error fetching messages via userbot for {chat_id}: {e}")
        return []


