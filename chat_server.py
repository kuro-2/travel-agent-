import os
import uuid
import logging
from flask import (
    Flask, request, jsonify, session,
    redirect, url_for, render_template,
)
from dotenv import load_dotenv

from promptflow_router import parse_and_respond
from rail_api import rail_api
from road_api import road_api
from weather_api import weather_api
from auth import require_auth, register_user, login_user, logout_supabase
from db import save_message, get_chat_history, create_chat_session

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(32))

app.register_blueprint(rail_api)
app.register_blueprint(road_api)
app.register_blueprint(weather_api)


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    return render_template("index.html",
                           user_email=session.get("user_email", ""),
                           user_name=session.get("user_name", ""))


@app.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/register")
def register_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("register.html")


# ─── Auth API ─────────────────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    result = register_user(email, password, full_name)
    if not result["success"]:
        return jsonify({"error": result["error"]}), 400

    if not result.get("confirmed"):
        return jsonify({
            "success": True,
            "confirm_email": True,
            "message": "Account created! Please check your email to confirm before signing in.",
        })

    _set_session(result["user_id"], result["email"], full_name)
    return jsonify({"success": True, "confirm_email": False})


@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    result = login_user(email, password)
    if not result["success"]:
        return jsonify({"error": result["error"]}), 401

    _set_session(result["user_id"], result["email"], result.get("full_name", ""))
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
        "user_id": session["user_id"],
        "email": session["user_email"],
        "name": session.get("user_name", ""),
    })


# ─── Chat API ─────────────────────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
@require_auth
def chat():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "Message cannot be empty."}), 400

    user_id = session["user_id"]
    session_id = session.get("db_session_id")

    try:
        bot_reply = parse_and_respond(user_msg)
    except Exception as e:
        logger.error(f"parse_and_respond error: {e}")
        bot_reply = "Sorry, something went wrong. Please try again."

    if session_id:
        try:
            save_message(session_id, user_id, "user", user_msg)
            save_message(session_id, user_id, "assistant", bot_reply)
        except Exception as e:
            logger.warning(f"Failed to save message to DB: {e}")

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

def _set_session(user_id: str, email: str, full_name: str):
    session["user_id"] = user_id
    session["user_email"] = email
    session["user_name"] = full_name
    db_session_id = create_chat_session(user_id)
    session["db_session_id"] = db_session_id


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
