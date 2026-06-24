# Powershell Script for Fresh Start
# Stops docker, removes neighborhoods.db, initializes tables, and starts docker with clean mounts.

Write-Host "Starting fresh database setup..." -ForegroundColor Cyan

# 1. Stop containers
Write-Host "Stopping Docker containers..." -ForegroundColor Yellow
docker compose down

# 2. Delete database file
Write-Host "Deleting old database file..." -ForegroundColor Yellow
if (Test-Path "neighborhoods.db") {
    Remove-Item -Path "neighborhoods.db" -Force -ErrorAction SilentlyContinue
    Write-Host "Database file deleted." -ForegroundColor Green
}
else {
    Write-Host "No existing database file found." -ForegroundColor Gray
}

# 3. Re-initialize database
Write-Host "Re-initializing SQLite database..." -ForegroundColor Yellow
if (Test-Path "venv/Scripts/python.exe") {
    & "venv/Scripts/python.exe" backend/scripts/init_db.py
}
else {
    python backend/scripts/init_db.py
}

# 4. Start containers
Write-Host "Starting Docker containers (force-recreate)..." -ForegroundColor Yellow
docker compose up -d --build --force-recreate

Write-Host "Fresh start completed successfully!" -ForegroundColor Green
