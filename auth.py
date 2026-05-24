import os
import logging
from functools import wraps
from flask import session, redirect, url_for, jsonify, request
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_url = os.getenv("SUPABASE_URL", "")
_anon_key = os.getenv("SUPABASE_ANON_KEY", "")

# Anon-key client — used for auth sign-up / sign-in only
_auth_client = create_client(_url, _anon_key) if _url and _anon_key else None


def require_auth(f):
    """Decorator that redirects unauthenticated users to login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json:
                return jsonify({"error": "Unauthorized", "redirect": "/login"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def register_user(email: str, password: str, full_name: str = "") -> dict:
    if _auth_client is None:
        return {"success": False, "error": "Auth service not configured"}
    try:
        result = _auth_client.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"full_name": full_name}},
        })
        if result.user:
            return {
                "success": True,
                "user_id": str(result.user.id),
                "email": result.user.email,
                "confirmed": result.session is not None,
            }
        return {"success": False, "error": "Registration failed. Please try again."}
    except Exception as e:
        msg = str(e)
        if "already registered" in msg.lower() or "already exists" in msg.lower():
            return {"success": False, "error": "An account with this email already exists."}
        logger.error(f"register_user error: {e}")
        return {"success": False, "error": "Registration failed. Please try again."}


def login_user(email: str, password: str) -> dict:
    if _auth_client is None:
        return {"success": False, "error": "Auth service not configured"}
    try:
        result = _auth_client.auth.sign_in_with_password({"email": email, "password": password})
        if result.user and result.session:
            return {
                "success": True,
                "user_id": str(result.user.id),
                "email": result.user.email,
                "full_name": result.user.user_metadata.get("full_name", ""),
            }
        return {"success": False, "error": "Invalid email or password."}
    except Exception as e:
        logger.warning(f"login_user failed: {e}")
        return {"success": False, "error": "Invalid email or password."}


def logout_supabase() -> None:
    if _auth_client is None:
        return
    try:
        _auth_client.auth.sign_out()
    except Exception:
        pass
