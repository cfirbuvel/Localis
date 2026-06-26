# Global Neighborhood & Emergency Platform (BotOS)

A global-scale system for **neighborhood communication, smart community coordination, emergency handling, and private building verification**, supporting dual integrations for **Telegram** and **WhatsApp** bots, alongside a **React Admin Web Dashboard**.

---

## 🚀 Key Features

* **Hierarchical Location Tree**: `Country > City > Neighborhood > Street > Building`.
* **Dynamic Auto-Creation**: Missing location nodes and their associated chats are automatically generated as users navigate.
* **Dual Bot Integrations**: Webhook handlers for official **Telegram Bot** and **WhatsApp Cloud (Business) API**.
* **Role-Based Security**:
  * *Super Admin* (global control, defined in `.env`).
  * *Managers* (assignable to any node; automatically inherits privileges for all subnodes).
  * *Moderators* (manage local chat moderation like muting/banning citizens).
* **Private Chat Verification**: Utility bills / lease documents uploaded via bots are queued on the React dashboard for manager approval. Approvals automatically trigger invite links.
* **Crisis Mode**: `/emergency <description>` alerts all regional administrators and pushes to dedicated active tickers.
* **AI Moderation Agent**: Intercepts citizen messages to flag spam, scams, and abuse (with an active Google Gemini API integration or rule-based fallback). Automatically mutes severe violations.

---

## 📁 Project Structure

```
BotOS/
├── backend/
│   ├── main.py                  # FastAPI Application Gateway
│   ├── database.py              # SQLite connection config
│   ├── models.py                # SQLAlchemy DB Tables
│   ├── schemas.py               # Pydantic request/response validation
│   ├── config.py                # Environment configurations loader
│   ├── .env                     # App credentials & local settings
│   ├── services/
│   │   ├── auth.py              # Direct bcrypt hashing & JWT tokens
│   │   ├── location.py          # Ancestor queries & auto-creation logic
│   │   ├── ai_moderator.py      # Gemini API connection / Mock audits
│   │   ├── bot_telegram.py      # Telegram bot inline buttons, document uploads
│   │   └── bot_whatsapp.py      # WhatsApp Graph API payload parser
│   └── scripts/
│       ├── init_db.py           # Table initialization script
│       ├── seed_db.py           # Seeding default hierarchy & Super Admin
│       ├── test_in_memory.py    # Integration test suite for APIs
│       └── simulate_bots.py     # End-to-end user bot interaction simulator
└── frontend/
    ├── src/
    │   ├── App.jsx              # Main panel dashboard layout
    │   ├── index.css            # Dark-mode glassmorphic theme styling
    │   └── components/
    │       ├── Login.jsx        # Credentials screen
    │       ├── HierarchyManager.jsx # Interactive location node tree explorer
    │       ├── RoleManager.jsx  # Manager/Moderator assignment form
    │       ├── VerificationQueue.jsx # Document queue for entry approvals
    │       ├── CrisisFeed.jsx   # Live emergency ticker
    │       └── ModeratorFeed.jsx # AI flagged logs with Mute/Ban buttons
    └── package.json
```

---

## 🐳 Quick Start: Running with Docker (Recommended)

To run the entire system (fastapi backend + sqlite database + react frontend + bot webhook updates) using Docker:

### 1. Build and Start Containers

```powershell
docker compose up --build -d
docker compose build --no-cache frontend
```

### 2. Expose Bot Webhook & Set Telegram URL Automatically

To run the tunnel and automatically configure the Telegram Bot webhook:

```powershell
.\start_tunnel.ps1
```

*Note: Make sure your `TELEGRAM_BOT_TOKEN` is configured in `backend/.env` first.*

### 3. Open Panel

- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173) (User: `admin` / Password: `adminpass`)
* **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🛠️ Backend Setup (Manual Run)

### 1. Prerequisites

Ensure you have **Python 3.12+** installed.

### 2. Create Virtual Environment & Install Dependencies

From the `BotOS` root directory:

```powershell
# Create venv
python -m venv venv

# Upgrade pip and install dependencies
.\venv\Scripts\pip.exe install -r backend\requirements.txt
```

### 3. Initialize & Seed Database

```powershell
# Create SQLite DB tables
.\venv\Scripts\python.exe backend\scripts\init_db.py

# Seed default admin & Florentin hierarchy
.\venv\Scripts\python.exe backend\scripts\seed_db.py
```

### 4. Run Automated Test & Simulation Suite

To run the automated API testing suite and the mock bot workflow simulation:

```powershell
# Run API integration tests
.\venv\Scripts\python.exe backend\scripts\test_in_memory.py

# Run bot workflow simulation (includes AI Moderation & Auto-mute checks)
$env:PYTHONIOENCODING='utf-8'
.\venv\Scripts\python.exe backend\scripts\simulate_bots.py
```

### 5. Start Development Server

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

The API documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 💻 Frontend Setup

### 1. Install Node Modules

From the `BotOS/frontend` directory:

```bash
npm install
```

### 2. Start Dev Server

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser. Log in using the seeded Super Admin credentials:

* **Username**: `admin`
* **Password**: `adminpass`

---

## 🤖 Configuring Real Bot APIs

To connect the code to live chat services, update `backend/.env` with your credentials:

### Telegram Setup

1. Message **@BotFather** on Telegram to create a bot and get a `TELEGRAM_BOT_TOKEN`.
2. Place the token in `.env`.
3. Set your webhook endpoint pointing to your public server (e.g. using ngrok):
   `https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<your-subdomain>.ngrok-free.app/webhooks/telegram`

### WhatsApp Cloud API Setup

1. Go to the [Meta for Developers Portal](https://developers.facebook.com/) and create a Business App.
2. Under WhatsApp Settings, configure a temporary or permanent **Access Token**, **Phone Number ID**, and **Business Account ID**.
3. Set your webhook callback URL to `https://<your-subdomain>.ngrok-free.app/webhooks/whatsapp` and configure a `WHATSAPP_VERIFY_TOKEN` of your choice matching the value in `.env`.
