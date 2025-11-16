import discord
import httpx
import asyncio
import os
from datetime import datetime, timezone
from config import get_settings

settings = get_settings()

BOT_TOKEN = settings.BOT_TOKEN
API_URL = settings.API_URL
ADMIN_USER_ID = settings.ADMIN_USER_ID
API_SHARED_SECRET = settings.API_SHARED_SECRET

POST_TIMEOUT = 5.0
MAX_RETRIES = 3
RETRY_BASE_DELAY = 0.5

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

_admin_user = None

def _mask(s: str) -> str:
    if not s or len(s) <= 8:
        return s or "<not set>"
    return s[:4] + "..." + s[-4:]

@client.event
async def on_ready():
    global _admin_user
    print(f"Bot online: {client.user} (ID: {client.user.id})")
    print("Config:", f"API: {_mask(API_URL)} | Secret: {_mask(API_SHARED_SECRET)} | Admin: {_mask(ADMIN_USER_ID)}")

    print("Guilds:")
    for guild in client.guilds:
        print(f"  - {guild.name} (ID: {guild.id}, Members: {guild.member_count})")

    if ADMIN_USER_ID:
        try:
            admin_id = int(ADMIN_USER_ID)
            if admin_id != client.user.id:
                _admin_user = await client.fetch_user(admin_id)
                print(f"Admin cached: {_admin_user}")
            else:
                print("Warning: ADMIN_ID is bot—fix it.")
        except Exception as e:
            print(f"Admin fetch failed: {e}")

def _build_payload(member: discord.Member) -> dict:
    return {
        "user_id": str(member.id),
        "username": str(member),
        "join_timestamp": member.joined_at.isoformat() if member.joined_at else datetime.now(timezone.utc).isoformat(),
        "server_id": str(member.guild.id),
        "server_name": member.guild.name,
        "account_created_at": member.created_at.isoformat()
    }

async def _post_with_retries(session, url, json_data, headers):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await session.post(url, json=json_data, headers=headers)
            resp.raise_for_status()
            try:
                return resp.status_code, resp.json(), resp.text
            except:
                return resp.status_code, {}, resp.text
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            print(f"HTTP {status} on attempt {attempt}")
            if 400 <= status < 500 and status != 429:
                return status, {}, exc.response.text
        except Exception as exc:
            print(f"Post error attempt {attempt}: {exc}")
        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)))
    return None, {}, "retries failed"

@client.event
async def on_member_join(member):
    print(f"Join: {member} in {member.guild.name} (ID: {member.guild.id})")
    payload = _build_payload(member)
    print(f"Payload: {payload}")
    headers = {"Content-Type": "application/json"}
    if API_SHARED_SECRET:
        headers["X-API-KEY"] = API_SHARED_SECRET

    if API_URL:
        async with httpx.AsyncClient(timeout=POST_TIMEOUT) as session:
            status, resp_json, resp_text = await _post_with_retries(session, API_URL, payload, headers)
            if status is None:
                print("POST failed after retries")
                return

            accepted = resp_json.get("status") == "success" or (status == 200 and resp_json.get("status") != "ignored")

            if accepted:
                # Real-time DM
                if _admin_user:
                    try:
                        await _admin_user.send(f"🚨 New join in **{member.guild.name}**: {member} (ID: {member.id}) at {payload['join_timestamp']}")
                    except Exception as e:
                        print(f"DM failed: {e}")
                else:
                    if ADMIN_USER_ID:
                        try:
                            admin = await client.fetch_user(int(ADMIN_USER_ID))
                            await admin.send(f"🚨 New join in **{member.guild.name}**: {member} (ID: {member.id}) at {payload['join_timestamp']}")
                        except Exception as e:
                            print(f"DM fallback failed: {e}")
            else:
                print(f"Event ignored: {status} | {resp_text} | {resp_json}")
    else:
        print("No API_URL—skipping log")

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("Missing BOT_TOKEN")
        exit(1)
    client.run(BOT_TOKEN)

   # === DUMMY WEB SERVER FOR RENDER FREE TIER ===
    from flask import Flask
    import threading
    import os

    app = Flask(__name__)

    @app.route("/")
    def health():
        return {
            "status": "alive",
            "bot": str(client.user) if client.user else "starting",
            "guilds": len(client.guilds) if client.is_ready() else 0,
            "uptime": datetime.now(timezone.utc).isoformat()
        }, 200

    # Run Discord bot in background
    def run_bot():
        client.run(BOT_TOKEN)

    threading.Thread(target=run_bot, daemon=True).start()

    # Run Flask on Render's PORT
    port = int(os.getenv("PORT", 8080))
    print(f"Starting Flask on port {port}...")
    app.run(host="0.0.0.0", port=port)