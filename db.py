import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger(__name__)

_url = os.getenv("SUPABASE_URL", "")
_service_key = os.getenv("SUPABASE_SERVICE_KEY", "")

# Service-role client — bypasses RLS; used only on the server
supabase: Client = create_client(_url, _service_key) if _url and _service_key else None


def _check_client():
    if supabase is None:
        raise RuntimeError("Supabase client not initialised. Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")


def create_chat_session(user_id: str) -> str | None:
    _check_client()
    try:
        res = supabase.table("chat_sessions").insert({"user_id": user_id}).execute()
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        logger.error(f"create_chat_session failed: {e}")
        return None


def save_message(session_id: str, user_id: str, role: str, content: str) -> None:
    if not session_id:
        return
    _check_client()
    try:
        supabase.table("chat_messages").insert({
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
        }).execute()
    except Exception as e:
        logger.error(f"save_message failed: {e}")


def get_chat_history(session_id: str, limit: int = 50) -> list:
    if not session_id:
        return []
    _check_client()
    try:
        res = (
            supabase.table("chat_messages")
            .select("role, content, created_at")
            .eq("session_id", session_id)
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"get_chat_history failed: {e}")
        return []


def get_user_sessions(user_id: str, limit: int = 20) -> list:
    _check_client()
    try:
        res = (
            supabase.table("chat_sessions")
            .select("id, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"get_user_sessions failed: {e}")
        return []
