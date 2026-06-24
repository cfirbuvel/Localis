import os
import sys

# Ensure backend folder is in path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("Error: Telethon is not installed in the virtual environment. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "telethon"])
    from telethon import TelegramClient
    from telethon.sessions import StringSession

# Load environment variables
from dotenv import load_dotenv
load_dotenv("backend/.env")

api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")

if not api_id or not api_hash:
    print("Error: TELEGRAM_API_ID or TELEGRAM_API_HASH is not configured in backend/.env")
    sys.exit(1)

print("Starting Telegram Userbot interactive login session...")
print("You will be asked to enter your phone number and the login code sent to your Telegram app.")

try:
    # Initialize client with a new in-memory StringSession
    with TelegramClient(StringSession(), int(api_id), api_hash) as client:
        session_str = client.session.save()
        print("\n" + "="*50)
        print("SUCCESS! Your TELEGRAM_SESSION_STRING has been generated:")
        print("="*50)
        print(session_str)
        print("="*50 + "\n")
        print("Copy the long string above and add it to your backend/.env file:")
        print("TELEGRAM_SESSION_STRING=your_copied_string_here")
except Exception as e:
    print(f"\nAn error occurred during session generation: {e}")
