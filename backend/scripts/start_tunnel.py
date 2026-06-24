import os
import sys
import time
import subprocess
import re
import urllib.request
import json

def get_env_var(key, default=""):
    try:
        from dotenv import load_dotenv
        # Load backend/.env
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        load_dotenv(dotenv_path)
    except ImportError:
        pass
    return os.getenv(key, default)

def main():
    bot_token = get_env_var("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("TELEGRAM_BOT_TOKEN not found in environment. Tunnel script exiting.")
        return

    target_url = get_env_var("TUNNEL_TARGET_URL", "http://127.0.0.1:8000")
    print(f"Starting cloudflared tunnel pointing to {target_url}...")
    
    cmd = ["cloudflared", "tunnel", "--protocol", "http2", "--url", target_url]
    try:
        # cloudflared logs everything to stderr by default
        process = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    except Exception as e:
        print(f"Failed to start cloudflared process: {e}")
        return

    tunnel_url = None
    print("Waiting for Cloudflare public URL...")
    
    # Read stderr line by line to find the tunnel URL
    while True:
        line = process.stderr.readline()
        if not line:
            break
        # Print logs to docker output
        sys.stdout.write(line)
        sys.stdout.flush()
        
        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if match:
            tunnel_url = match.group(0)
            break
            
    if not tunnel_url:
        print("Could not retrieve tunnel URL from cloudflared logs.")
        return

    print(f"\n[Tunnel Service] Tunnel established at: {tunnel_url}")
    print("[Tunnel Service] Waiting 15 seconds for Cloudflare DNS propagation to avoid Telegram DNS NXDOMAIN caching...")
    time.sleep(15)

    webhook_url = f"{tunnel_url}/webhooks/telegram"
    
    # Retry webhook registration up to 10 times (with 10s sleep in between) to allow DNS propagation
    success = False
    attempt = 1
    while not success:
        print(f"[Tunnel Service] Setting Telegram webhook (Attempt {attempt}) to: {webhook_url}")
        try:
            api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook?url={webhook_url}"
            req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                res_data = response.read().decode("utf-8")
                res_json = json.loads(res_data)
                print(f"[Tunnel Service] Telegram Response: {res_data}")
                if res_json.get("ok"):
                    print("[Tunnel Service] Webhook set successfully!")
                    success = True
                    break
        except Exception as e:
            # Check if HTTPError contains detail on error response
            if hasattr(e, 'read'):
                try:
                    err_body = e.read().decode()
                    print(f"[Tunnel Service] Attempt {attempt} failed: {e} - {err_body}")
                except Exception:
                    print(f"[Tunnel Service] Attempt {attempt} failed: {e}")
            else:
                print(f"[Tunnel Service] Attempt {attempt} failed: {e}")
        
        attempt += 1
        print("[Tunnel Service] Waiting 15 seconds before retrying...")
        time.sleep(15)

    # Keep reading logs and printing them to keep container logs informed, or wait until process exits
    try:
        for line in process.stderr:
            sys.stdout.write(line)
            sys.stdout.flush()
    except Exception:
        pass

if __name__ == "__main__":
    main()
