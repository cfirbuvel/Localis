#!/bin/sh

# Initialize database tables
python backend/scripts/init_db.py

# Seed initial admin and location data
python backend/scripts/seed_db.py

# Start Fastapi app gateway
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
