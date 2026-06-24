# Read .env to get bot token
if (Test-Path "backend/.env") {
    $envFile = Get-Content -Path "backend/.env"
} else {
    Write-Error "backend/.env file not found."
    exit 1
}

$botToken = ""
foreach ($line in $envFile) {
    if ($line -match "^TELEGRAM_BOT_TOKEN=(.+)$") {
        $botToken = $Matches[1].Trim()
    }
}

if (-not $botToken) {
    Write-Error "TELEGRAM_BOT_TOKEN not found in backend/.env"
    exit 1
}

Write-Host "Starting cloudflared tunnel..." -ForegroundColor Cyan
$logFile = "cloudflared.log"
Remove-Item $logFile -ErrorAction SilentlyContinue

# Launch cloudflared in the background redirecting error logs (where tunnel info is written)
Start-Process -FilePath ".\cloudflared.exe" -ArgumentList "tunnel --protocol http2 --url http://127.0.0.1:8000" -RedirectStandardError $logFile -NoNewWindow


Write-Host "Waiting for Cloudflare public URL..." -ForegroundColor Cyan
$tunnelUrl = ""
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $logFile) {
        $content = Get-Content $logFile
        foreach ($line in $content) {
            if ($line -match "https://[a-zA-Z0-9-]+\.trycloudflare\.com") {
                $tunnelUrl = $Matches[0]
                break
            }
        }
    }
    if ($tunnelUrl) { break }
}

if ($tunnelUrl) {
    Write-Host "Tunnel established at: $tunnelUrl" -ForegroundColor Green
    Write-Host "Waiting 4 seconds for Cloudflare DNS propagation..." -ForegroundColor Cyan
    Start-Sleep -Seconds 4
    $webhookUrl = "$tunnelUrl/webhooks/telegram"
    Write-Host "Setting Telegram webhook to: $webhookUrl" -ForegroundColor Cyan

    
    try {
        $apiResult = Invoke-RestMethod -Uri "https://api.telegram.org/bot$botToken/setWebhook?url=$webhookUrl" -Method Get
        Write-Host "Telegram Response: $($apiResult | ConvertTo-Json -Compress)" -ForegroundColor Green
    } catch {
        Write-Error "Failed to reach Telegram API: $_"
    }
} else {
    Write-Error "Could not retrieve tunnel URL from cloudflared logs. Please check cloudflared.log"
}
