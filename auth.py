import os
import hashlib
import base64
import secrets
import logging
import urllib.parse
from functools import wraps
from flask import session, redirect, url_for, jsonify, request
import requests as http_requests
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_url = os.getenv("SUPABASE_URL", "")
_anon_key = os.getenv("SUPABASE_ANON_KEY", "")

# Anon-key client — used for email/password auth only
_auth_client = create_client(_url, _anon_key) if _url and _anon_key else None


# ─── Decorator ────────────────────────────────────────────────────────────────

def require_auth(f):
    """Redirect unauthenticated users to /login; return 401 for JSON requests."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json:
                return jsonify({"error": "Unauthorized", "redirect": "/login"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


# ─── Email / Password ─────────────────────────────────────────────────────────

def register_user(email: str, password: str, full_name: str = "") -> dict:
    if _auth_client is None:
        return {"success": False, "error": "Auth service not configured. Check SUPABASE_URL and SUPABASE_ANON_KEY."}
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
                "full_name": full_name,
                # session is None when email confirmation is required
                "confirmed": result.session is not None,
            }
        return {"success": False, "error": "Registration failed. Please try again."}
    except Exception as e:
        msg = str(e).lower()
        if "already registered" in msg or "already exists" in msg or "duplicate" in msg:
            return {"success": False, "error": "An account with this email already exists."}
        if "database error" in msg:
            logger.error(f"register_user DB trigger error: {e}")
            return {"success": False, "error": "Database setup incomplete — please run migrations/002_profiles_table.sql in Supabase SQL Editor."}
        logger.error(f"register_user error: {e}")
        return {"success": False, "error": "Registration failed. Please try again."}


def login_user(email: str, password: str) -> dict:
    if _auth_client is None:
        return {"success": False, "error": "Auth service not configured."}
    try:
        result = _auth_client.auth.sign_in_with_password({"email": email, "password": password})
        if result.user and result.session:
            meta = result.user.user_metadata or {}
            return {
                "success": True,
                "user_id": str(result.user.id),
                "email": result.user.email,
                "full_name": meta.get("full_name") or meta.get("name") or "",
                "avatar_url": meta.get("avatar_url") or "",
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


# ─── Google OAuth (PKCE — server-side) ───────────────────────────────────────
#
# We implement PKCE manually so we don't depend on supabase-py internal
# storage, which is ephemeral and not safe across HTTP requests.
#
# Flow:
#  1. /auth/google  → generate verifier, store in session, redirect to Google
#  2. Google auths user → redirects to Supabase → Supabase redirects to
#     /auth/callback?code=<code>
#  3. /auth/callback → exchange (code + verifier) → set Flask session


def _pkce_verifier() -> str:
    """Generate a cryptographically random PKCE code verifier (43 chars)."""
    return secrets.token_urlsafe(43)


def _pkce_challenge(verifier: str) -> str:
    """SHA-256 of verifier, base64url-encoded without padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_google_oauth_url(callback_url: str) -> tuple[str, str]:
    """
    Returns (oauth_redirect_url, code_verifier).
    Store code_verifier in Flask session; redirect the user to oauth_redirect_url.
    """
    verifier = _pkce_verifier()
    challenge = _pkce_challenge(verifier)

    params = urllib.parse.urlencode({
        "provider": "google",
        "redirect_to": callback_url,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    url = f"{_url}/auth/v1/authorize?{params}"
    return url, verifier


def exchange_google_code(auth_code: str, code_verifier: str) -> dict:
    """
    Exchange the OAuth authorization code + PKCE verifier for a Supabase session.
    Returns a dict with success/user info on success, or error on failure.
    """
    endpoint = f"{_url}/auth/v1/token?grant_type=pkce"
    headers = {
        "apikey": _anon_key,
        "Content-Type": "application/json",
    }
    payload = {
        "auth_code": auth_code,
        "code_verifier": code_verifier,
    }

    try:
        res = http_requests.post(endpoint, json=payload, headers=headers, timeout=10)
        data = res.json()

        if res.status_code != 200:
            error_msg = data.get("error_description") or data.get("msg") or "OAuth exchange failed."
            logger.warning(f"Google code exchange failed ({res.status_code}): {error_msg}")
            return {"success": False, "error": error_msg}

        user = data.get("user") or {}
        meta = user.get("user_metadata") or {}
        return {
            "success": True,
            "user_id": user.get("id", ""),
            "email": user.get("email", ""),
            "full_name": meta.get("full_name") or meta.get("name") or "",
            "avatar_url": meta.get("avatar_url") or "",
        }

    except Exception as e:
        logger.error(f"exchange_google_code network error: {e}")
        return {"success": False, "error": "Could not connect to auth service. Try again."}
