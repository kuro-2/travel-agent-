import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger(__name__)

_url         = os.getenv("SUPABASE_URL", "")
_service_key = os.getenv("SUPABASE_SERVICE_KEY", "")

# Service-role client — bypasses RLS; used only on the trusted server side
supabase: Client = create_client(_url, _service_key) if _url and _service_key else None


def _check_client() -> None:
    if supabase is None:
        raise RuntimeError(
            "Supabase client not initialised. "
            "Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"
        )


# ─── Profiles ─────────────────────────────────────────────────────────────────

def upsert_profile(user_id: str, full_name: str, avatar_url: str, provider: str = "email") -> None:
    """Create or update the user's profile row (called after login/OAuth)."""
    _check_client()
    try:
        supabase.table("profiles").upsert({
            "id":         user_id,
            "full_name":  full_name or "",
            "avatar_url": avatar_url or "",
            "provider":   provider,
        }, on_conflict="id").execute()
    except Exception as e:
        logger.error(f"upsert_profile failed: {e}")


def get_profile(user_id: str) -> dict:
    """Return the profile row for a user, or {} if not found."""
    _check_client()
    try:
        res = (
            supabase.table("profiles")
            .select("id, full_name, avatar_url, provider, created_at")
            .eq("id", user_id)
            .single()
            .execute()
        )
        return res.data or {}
    except Exception as e:
        logger.error(f"get_profile failed: {e}")
        return {}


# ─── Chat Sessions ────────────────────────────────────────────────────────────

def create_chat_session(user_id: str) -> str | None:
    """Insert a new chat session row and return its UUID."""
    _check_client()
    try:
        res = supabase.table("chat_sessions").insert({"user_id": user_id}).execute()
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        logger.error(f"create_chat_session failed: {e}")
        return None



# ─── Chat Exchanges (paired user + assistant per row) ─────────────────────────

def save_exchange(session_id: str, user_id: str, user_message: str, assistant_reply: str) -> None:
    """Persist one full exchange (user prompt + assistant reply) as a single row."""
    if not session_id:
        return
    _check_client()
    try:
        supabase.table("chat_exchanges").insert({
            "session_id":      session_id,
            "user_id":         user_id,
            "user_message":    user_message,
            "assistant_reply": assistant_reply,
        }).execute()
    except Exception as e:
        logger.error(f"save_exchange failed: {e}")


def get_chat_history(session_id: str, limit: int = 50) -> list:
    """Return ordered exchanges for a session as a flat [user, assistant, ...] list."""
    if not session_id:
        return []
    _check_client()
    try:
        res = (
            supabase.table("chat_exchanges")
            .select("user_message, assistant_reply, created_at")
            .eq("session_id", session_id)
            .order("created_at")
            .limit(limit)
            .execute()
        )
        messages = []
        for row in (res.data or []):
            messages.append({"role": "user",      "content": row["user_message"],    "created_at": row["created_at"]})
            messages.append({"role": "assistant",  "content": row["assistant_reply"], "created_at": row["created_at"]})
        return messages
    except Exception as e:
        logger.error(f"get_chat_history failed: {e}")
        return []
