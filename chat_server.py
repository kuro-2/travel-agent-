import os
import logging
from flask import (
    Flask, request, jsonify, session,
    redirect, url_for, render_template,
)
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

from promptflow_router import parse_and_respond
from rail_api import rail_api
from road_api import road_api
from weather_api import weather_api
from auth import (
    require_auth,
    register_user, login_user, logout_supabase,
    build_google_oauth_url, exchange_google_code,
)
from db import save_exchange, get_chat_history, create_chat_session, upsert_profile

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")
# Trust Render's (and any other reverse proxy's) X-Forwarded-Proto/Host headers
# so url_for(_external=True) generates https:// URLs in production.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
_secret = os.getenv("FLASK_SECRET_KEY")
if not _secret:
    import warnings
    warnings.warn("FLASK_SECRET_KEY not set — using random key. Sessions will not survive restarts.", stacklevel=2)
    _secret = os.urandom(32)
app.secret_key = _secret

app.register_blueprint(rail_api)
app.register_blueprint(road_api)
app.register_blueprint(weather_api)


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    return render_template(
        "index.html",
        user_email=session.get("user_email", ""),
        user_name=session.get("user_name", ""),
        user_avatar=session.get("user_avatar", ""),
    )


@app.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    error = request.args.get("error", "")
    return render_template("login.html", error=error)


@app.route("/register")
def register_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("register.html")


# ─── Email / Password Auth ────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json(silent=True) or {}
    email     = (data.get("email") or "").strip().lower()
    password  = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    result = register_user(email, password, full_name)
    if not result["success"]:
        return jsonify({"error": result["error"]}), 400

    if not result.get("confirmed"):
        # Email confirmation is ON in Supabase — user must verify before logging in
        return jsonify({
            "success": True,
            "confirm_email": True,
            "message": "Account created! Please check your email to confirm it before signing in.",
        })

    _set_session(result["user_id"], result["email"], full_name, "")
    return jsonify({"success": True, "confirm_email": False})


@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    result = login_user(email, password)
    if not result["success"]:
        return jsonify({"error": result["error"]}), 401

    _set_session(
        result["user_id"],
        result["email"],
        result.get("full_name", ""),
        result.get("avatar_url", ""),
    )
    return jsonify({"success": True})


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    logout_supabase()
    session.clear()
    return jsonify({"success": True})


@app.route("/auth/me", methods=["GET"])
@require_auth
def auth_me():
    return jsonify({
        "user_id":    session["user_id"],
        "email":      session["user_email"],
        "name":       session.get("user_name", ""),
        "avatar_url": session.get("user_avatar", ""),
    })


# ─── Google OAuth ─────────────────────────────────────────────────────────────

@app.route("/auth/google")
def auth_google():
    """Start the Google OAuth PKCE flow — redirect user to Google."""
    if "user_id" in session:
        return redirect(url_for("index"))

    callback_url = url_for("auth_callback", _external=True)
    try:
        oauth_url, code_verifier = build_google_oauth_url(callback_url)
    except Exception as e:
        logger.error(f"Failed to build Google OAuth URL: {e}")
        return redirect(url_for("login_page", error="google_unavailable"))

    # Store verifier — needed in the callback to complete PKCE exchange
    session["pkce_verifier"] = code_verifier
    return redirect(oauth_url)


@app.route("/auth/callback")
def auth_callback():
    """Supabase redirects here after Google auth with ?code=<auth_code>."""
    error = request.args.get("error")
    if error:
        desc = request.args.get("error_description", "Google sign-in was cancelled.")
        logger.warning(f"OAuth callback error: {error} — {desc}")
        return redirect(url_for("login_page", error=desc))

    auth_code    = request.args.get("code", "")
    code_verifier = session.pop("pkce_verifier", None)

    if not auth_code or not code_verifier:
        return redirect(url_for("login_page", error="Invalid OAuth state. Please try again."))

    result = exchange_google_code(auth_code, code_verifier)
    if not result["success"]:
        return redirect(url_for("login_page", error=result.get("error", "Google sign-in failed.")))

    user_id    = result["user_id"]
    email      = result["email"]
    full_name  = result.get("full_name", "")
    avatar_url = result.get("avatar_url", "")

    # Keep the profile table in sync (name/avatar may change on Google side)
    try:
        upsert_profile(user_id, full_name, avatar_url, "google")
    except Exception as e:
        logger.warning(f"Profile upsert after Google OAuth failed: {e}")

    _set_session(user_id, email, full_name, avatar_url)
    return redirect(url_for("index"))


# ─── Chat API ─────────────────────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
@require_auth
def chat():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "Message cannot be empty."}), 400

    user_id    = session["user_id"]
    session_id = session.get("db_session_id")

    try:
        bot_reply = parse_and_respond(user_msg)
    except Exception as e:
        logger.error(f"parse_and_respond error: {e}")
        bot_reply = "Sorry, something went wrong. Please try again."

    if session_id:
        try:
            save_exchange(session_id, user_id, user_msg, bot_reply)
        except Exception as e:
            logger.warning(f"Failed to save exchange to DB: {e}")

    return jsonify({"response": bot_reply})


@app.route("/history", methods=["GET"])
@require_auth
def history():
    session_id = session.get("db_session_id")
    if not session_id:
        return jsonify({"messages": []})
    try:
        msgs = get_chat_history(session_id)
        return jsonify({"messages": msgs})
    except Exception as e:
        logger.warning(f"Failed to load history: {e}")
        return jsonify({"messages": []})


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _set_session(user_id: str, email: str, full_name: str, avatar_url: str) -> None:
    session["user_id"]    = user_id
    session["user_email"] = email
    session["user_name"]  = full_name
    session["user_avatar"] = avatar_url
    db_session_id = create_chat_session(user_id)
    session["db_session_id"] = db_session_id


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
