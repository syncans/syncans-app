from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import secrets
import sqlite3
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "syncans.db")))

CATEGORIES = [
    "Trek",
    "Gym",
    "Study",
    "Startup",
    "Cafe",
    "Sports",
    "Culture",
    "Music",
]

SESSION_TTL_DAYS = 30


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def error_response(handler: BaseHTTPRequestHandler, status: int, message: str) -> None:
    json_response(handler, status, {"error": message})


def to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    if not table_exists(connection, table_name):
        return False
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def reset_legacy_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP TABLE IF EXISTS activity_members;
        DROP TABLE IF EXISTS sessions;
        DROP TABLE IF EXISTS notifications;
        DROP TABLE IF EXISTS join_requests;
        DROP TABLE IF EXISTS profile;
        DROP TABLE IF EXISTS activities;
        DROP TABLE IF EXISTS users;
        """
    )


def init_db() -> None:
    with get_connection() as connection:
        if table_exists(connection, "users") and not column_exists(connection, "users", "email"):
            reset_legacy_schema(connection)

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              city TEXT NOT NULL,
              bio TEXT NOT NULL DEFAULT '',
              phone_verified INTEGER NOT NULL DEFAULT 0,
              id_verified INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              token TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS activities (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              title TEXT NOT NULL,
              category TEXT NOT NULL,
              location TEXT NOT NULL,
              city TEXT NOT NULL,
              start_time TEXT NOT NULL,
              slots INTEGER NOT NULL,
              notes TEXT NOT NULL DEFAULT '',
              radius_km INTEGER NOT NULL DEFAULT 10,
              status TEXT NOT NULL DEFAULT 'active',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS activity_members (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(activity_id, user_id)
            );
            """
        )


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 150000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 150000)
    return secrets.compare_digest(digest.hex(), expected)


def create_session(connection: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    connection.execute(
        "INSERT INTO sessions (user_id, token, created_at) VALUES (?, ?, ?)",
        (user_id, token, now_iso()),
    )
    return token


def get_token_from_headers(handler: BaseHTTPRequestHandler) -> str | None:
    header = handler.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header.removeprefix("Bearer ").strip()
    return token or None


def get_current_user(connection: sqlite3.Connection, handler: BaseHTTPRequestHandler) -> sqlite3.Row | None:
    token = get_token_from_headers(handler)
    if not token:
        return None
    return connection.execute(
        """
        SELECT u.*
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ?
        """,
        (token,),
    ).fetchone()


def require_user(connection: sqlite3.Connection, handler: BaseHTTPRequestHandler) -> sqlite3.Row | None:
    user = get_current_user(connection, handler)
    if user is None:
        error_response(handler, HTTPStatus.UNAUTHORIZED, "Authentication required.")
    return user


def calculate_trust_score(connection: sqlite3.Connection, user_id: int) -> float:
    hosted = connection.execute(
        "SELECT COUNT(*) FROM activities WHERE owner_id = ?",
        (user_id,),
    ).fetchone()[0]
    approved = connection.execute(
        "SELECT COUNT(*) FROM activity_members WHERE user_id = ? AND status = 'approved'",
        (user_id,),
    ).fetchone()[0]
    incoming = connection.execute(
        """
        SELECT COUNT(*)
        FROM activity_members am
        JOIN activities a ON a.id = am.activity_id
        WHERE a.owner_id = ? AND am.status = 'approved'
        """,
        (user_id,),
    ).fetchone()[0]
    raw = 3.8 + (hosted * 0.12) + (approved * 0.08) + (incoming * 0.04)
    return round(min(raw, 5.0), 1)


def activity_approved_count(connection: sqlite3.Connection, activity_id: int) -> int:
    return connection.execute(
        "SELECT COUNT(*) FROM activity_members WHERE activity_id = ? AND status = 'approved'",
        (activity_id,),
    ).fetchone()[0]


def relation_status(connection: sqlite3.Connection, activity_id: int, user_id: int) -> str | None:
    row = connection.execute(
        "SELECT status FROM activity_members WHERE activity_id = ? AND user_id = ?",
        (activity_id, user_id),
    ).fetchone()
    return row["status"] if row else None


def serialize_activity(connection: sqlite3.Connection, row: sqlite3.Row, viewer_id: int | None = None) -> dict[str, Any]:
    approved_count = activity_approved_count(connection, row["id"])
    owner_score = calculate_trust_score(connection, row["owner_id"])
    return {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "location": row["location"],
        "city": row["city"],
        "time": row["start_time"],
        "slots": row["slots"],
        "availableSlots": max(row["slots"] - approved_count, 0),
        "notes": row["notes"],
        "radiusKm": row["radius_km"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "owner": {
            "id": row["owner_id"],
            "name": row["owner_name"],
            "city": row["owner_city"],
            "trustScore": owner_score,
        },
        "relationStatus": relation_status(connection, row["id"], viewer_id) if viewer_id else None,
        "mine": bool(viewer_id and viewer_id == row["owner_id"]),
        "approvedCount": approved_count,
    }


def serialize_user(connection: sqlite3.Connection, user: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "city": user["city"],
        "bio": user["bio"],
        "phoneVerified": bool(user["phone_verified"]),
        "idVerified": bool(user["id_verified"]),
        "trustScore": calculate_trust_score(connection, user["id"]),
    }


def query_activities(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    category: str | None = None,
    radius_km: int | None = None,
    city: str | None = None,
    include_mine: bool = True,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    clauses = ["a.status = 'active'"]
    params: list[Any] = []

    if category:
        clauses.append("a.category = ?")
        params.append(category)
    if city:
        clauses.append("lower(a.city) = lower(?)")
        params.append(city)
    if radius_km is not None:
        clauses.append("a.radius_km <= ?")
        params.append(radius_km)
    if not include_mine:
        clauses.append("a.owner_id != ?")
        params.append(user_id)

    sql = f"""
        SELECT a.*, u.name AS owner_name, u.city AS owner_city
        FROM activities a
        JOIN users u ON u.id = a.owner_id
        WHERE {' AND '.join(clauses)}
        ORDER BY a.created_at DESC, a.id DESC
    """
    if limit is not None:
        sql += f" LIMIT {limit}"

    rows = connection.execute(sql, params).fetchall()
    return [serialize_activity(connection, row, user_id) for row in rows]


def build_home(connection: sqlite3.Connection, user: sqlite3.Row) -> dict[str, Any]:
    active_row = connection.execute(
        """
        SELECT a.*, u.name AS owner_name, u.city AS owner_city
        FROM activities a
        JOIN users u ON u.id = a.owner_id
        WHERE a.status = 'active' AND (
          a.owner_id = ? OR EXISTS (
            SELECT 1 FROM activity_members am
            WHERE am.activity_id = a.id AND am.user_id = ? AND am.status = 'approved'
          )
        )
        ORDER BY a.created_at DESC, a.id DESC
        LIMIT 1
        """,
        (user["id"], user["id"]),
    ).fetchone()

    nearby = query_activities(
        connection,
        user_id=user["id"],
        city=user["city"],
        include_mine=False,
        limit=4,
    )

    pending_requests = connection.execute(
        """
        SELECT COUNT(*)
        FROM activity_members am
        JOIN activities a ON a.id = am.activity_id
        WHERE a.owner_id = ? AND am.status = 'requested'
        """,
        (user["id"],),
    ).fetchone()[0]
    joined = connection.execute(
        "SELECT COUNT(*) FROM activity_members WHERE user_id = ? AND status = 'approved'",
        (user["id"],),
    ).fetchone()[0]
    active_hosted = connection.execute(
        "SELECT COUNT(*) FROM activities WHERE owner_id = ? AND status = 'active'",
        (user["id"],),
    ).fetchone()[0]

    return {
        "user": serialize_user(connection, user),
        "activeActivity": serialize_activity(connection, active_row, user["id"]) if active_row else None,
        "nearbyActivities": nearby,
        "stats": {
            "activeHosted": active_hosted,
            "joinedPlans": joined,
            "pendingRequests": pending_requests,
        },
    }


def build_matches(connection: sqlite3.Connection, user: sqlite3.Row) -> dict[str, Any]:
    request_rows = connection.execute(
        """
        SELECT
          am.id,
          am.status,
          am.created_at,
          a.id AS activity_id,
          a.title,
          a.category,
          a.location,
          a.city,
          a.start_time,
          a.slots,
          a.notes,
          a.radius_km,
          requester.id AS requester_id,
          requester.name AS requester_name,
          requester.city AS requester_city,
          requester.bio AS requester_bio
        FROM activity_members am
        JOIN activities a ON a.id = am.activity_id
        JOIN users requester ON requester.id = am.user_id
        WHERE a.owner_id = ? AND am.status = 'requested'
        ORDER BY am.created_at DESC, am.id DESC
        """,
        (user["id"],),
    ).fetchall()

    my_rows = connection.execute(
        """
        SELECT a.*, u.name AS owner_name, u.city AS owner_city
        FROM activities a
        JOIN users u ON u.id = a.owner_id
        WHERE a.owner_id = ?
           OR EXISTS (
             SELECT 1 FROM activity_members am
             WHERE am.activity_id = a.id AND am.user_id = ? AND am.status IN ('requested', 'approved')
           )
        ORDER BY a.created_at DESC, a.id DESC
        LIMIT 10
        """,
        (user["id"], user["id"]),
    ).fetchall()

    return {
        "incomingRequests": [
            {
                "id": row["id"],
                "status": row["status"],
                "createdAt": row["created_at"],
                "activity": {
                    "id": row["activity_id"],
                    "title": row["title"],
                    "category": row["category"],
                    "location": row["location"],
                    "city": row["city"],
                    "time": row["start_time"],
                    "slots": row["slots"],
                    "notes": row["notes"],
                    "radiusKm": row["radius_km"],
                },
                "requester": {
                    "id": row["requester_id"],
                    "name": row["requester_name"],
                    "city": row["requester_city"],
                    "bio": row["requester_bio"],
                    "trustScore": calculate_trust_score(connection, row["requester_id"]),
                },
            }
            for row in request_rows
        ],
        "myActivities": [serialize_activity(connection, row, user["id"]) for row in my_rows],
    }


def build_user_profile(connection: sqlite3.Connection, user: sqlite3.Row) -> dict[str, Any]:
    hosted_rows = connection.execute(
        """
        SELECT a.*, u.name AS owner_name, u.city AS owner_city
        FROM activities a
        JOIN users u ON u.id = a.owner_id
        WHERE a.owner_id = ?
        ORDER BY a.created_at DESC, a.id DESC
        LIMIT 8
        """,
        (user["id"],),
    ).fetchall()

    joined_rows = connection.execute(
        """
        SELECT a.*, owner.name AS owner_name, owner.city AS owner_city
        FROM activities a
        JOIN users owner ON owner.id = a.owner_id
        JOIN activity_members am ON am.activity_id = a.id
        WHERE am.user_id = ? AND am.status = 'approved'
        ORDER BY a.created_at DESC, a.id DESC
        LIMIT 8
        """,
        (user["id"],),
    ).fetchall()

    past_rows = [row for row in hosted_rows if row["status"] != "active"]

    return {
        "user": serialize_user(connection, user),
        "hostedActivities": [serialize_activity(connection, row, user["id"]) for row in hosted_rows if row["status"] == "active"],
        "joinedActivities": [serialize_activity(connection, row, user["id"]) for row in joined_rows],
        "pastActivities": [serialize_activity(connection, row, user["id"]) for row in past_rows],
        "stats": {
            "hostedCount": len(hosted_rows),
            "joinedCount": len(joined_rows),
            "requestCount": connection.execute(
                """
                SELECT COUNT(*)
                FROM activity_members am
                JOIN activities a ON a.id = am.activity_id
                WHERE a.owner_id = ? AND am.status = 'requested'
                """,
                (user["id"],),
            ).fetchone()[0],
        },
    }


def signup_user(connection: sqlite3.Connection, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    city = str(payload.get("city", "")).strip()
    bio = str(payload.get("bio", "")).strip()

    if not name or not email or not password or not city:
        return HTTPStatus.BAD_REQUEST, {"error": "Name, email, password, and city are required."}
    if len(password) < 6:
        return HTTPStatus.BAD_REQUEST, {"error": "Password must be at least 6 characters."}

    existing = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing is not None:
        return HTTPStatus.CONFLICT, {"error": "An account with that email already exists."}

    user_id = connection.execute(
        """
        INSERT INTO users (name, email, password_hash, city, bio, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, email, hash_password(password), city, bio[:160], now_iso()),
    ).lastrowid
    token = create_session(connection, user_id)
    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return HTTPStatus.CREATED, {"token": token, "user": serialize_user(connection, user)}


def login_user(connection: sqlite3.Connection, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        return HTTPStatus.UNAUTHORIZED, {"error": "Invalid email or password."}

    token = create_session(connection, row["id"])
    return HTTPStatus.OK, {"token": token, "user": serialize_user(connection, row)}


def create_activity(connection: sqlite3.Connection, user: sqlite3.Row, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    title = str(payload.get("title", "")).strip()
    category = str(payload.get("category", "")).strip()
    location = str(payload.get("location", "")).strip()
    city = str(payload.get("city", user["city"])) .strip() or user["city"]
    start_time = str(payload.get("time", "")).strip()
    notes = str(payload.get("notes", "")).strip()
    slots = to_int(payload.get("slots"), 4)
    radius_km = to_int(payload.get("radiusKm"), 10)

    if not title or not category or not location or not start_time:
        return HTTPStatus.BAD_REQUEST, {"error": "Title, category, location, and time are required."}
    if category not in CATEGORIES:
        return HTTPStatus.BAD_REQUEST, {"error": "Unsupported category."}
    if slots < 2 or slots > 20:
        return HTTPStatus.BAD_REQUEST, {"error": "Slots must be between 2 and 20."}

    connection.execute(
        "UPDATE activities SET status = 'completed' WHERE owner_id = ? AND status = 'active'",
        (user["id"],),
    )
    activity_id = connection.execute(
        """
        INSERT INTO activities (
          owner_id, title, category, location, city, start_time, slots, notes, radius_km, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
        """,
        (user["id"], title[:80], category, location[:80], city[:40], start_time[:20], slots, notes[:160], radius_km, now_iso()),
    ).lastrowid
    row = connection.execute(
        """
        SELECT a.*, u.name AS owner_name, u.city AS owner_city
        FROM activities a
        JOIN users u ON u.id = a.owner_id
        WHERE a.id = ?
        """,
        (activity_id,),
    ).fetchone()
    return HTTPStatus.CREATED, {"activity": serialize_activity(connection, row, user["id"])}


def join_activity(connection: sqlite3.Connection, user: sqlite3.Row, activity_id: int) -> tuple[int, dict[str, Any]]:
    row = connection.execute(
        "SELECT * FROM activities WHERE id = ? AND status = 'active'",
        (activity_id,),
    ).fetchone()
    if row is None:
        return HTTPStatus.NOT_FOUND, {"error": "Activity not found."}
    if row["owner_id"] == user["id"]:
        return HTTPStatus.CONFLICT, {"error": "You already own this activity."}

    existing = connection.execute(
        "SELECT status FROM activity_members WHERE activity_id = ? AND user_id = ?",
        (activity_id, user["id"]),
    ).fetchone()
    if existing is not None and existing["status"] in {"requested", "approved"}:
        return HTTPStatus.CONFLICT, {"error": "You have already joined or requested this activity."}

    if activity_approved_count(connection, activity_id) >= row["slots"]:
        return HTTPStatus.CONFLICT, {"error": "This activity is already full."}

    if existing is None:
        connection.execute(
            "INSERT INTO activity_members (activity_id, user_id, status, created_at) VALUES (?, ?, 'requested', ?)",
            (activity_id, user["id"], now_iso()),
        )
    else:
        connection.execute(
            "UPDATE activity_members SET status = 'requested', created_at = ? WHERE activity_id = ? AND user_id = ?",
            (now_iso(), activity_id, user["id"]),
        )
    return HTTPStatus.OK, {"message": "Join request sent."}


def decide_request(connection: sqlite3.Connection, user: sqlite3.Row, request_id: int, action: str) -> tuple[int, dict[str, Any]]:
    row = connection.execute(
        """
        SELECT am.id, am.activity_id, am.user_id, am.status, a.owner_id, a.slots
        FROM activity_members am
        JOIN activities a ON a.id = am.activity_id
        WHERE am.id = ?
        """,
        (request_id,),
    ).fetchone()
    if row is None:
        return HTTPStatus.NOT_FOUND, {"error": "Request not found."}
    if row["owner_id"] != user["id"]:
        return HTTPStatus.FORBIDDEN, {"error": "You cannot manage this request."}
    if row["status"] != "requested":
        return HTTPStatus.CONFLICT, {"error": "This request has already been handled."}

    if action == "approve":
        approved_count = activity_approved_count(connection, row["activity_id"])
        if approved_count >= row["slots"]:
            return HTTPStatus.CONFLICT, {"error": "This activity is already full."}
        connection.execute("UPDATE activity_members SET status = 'approved' WHERE id = ?", (request_id,))
        return HTTPStatus.OK, {"message": "Request approved."}

    if action == "decline":
        connection.execute("UPDATE activity_members SET status = 'declined' WHERE id = ?", (request_id,))
        return HTTPStatus.OK, {"message": "Request declined."}

    return HTTPStatus.BAD_REQUEST, {"error": "Unsupported action."}


class SyncansHandler(BaseHTTPRequestHandler):
    server_version = "SYNCANS/2.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            error_response(self, HTTPStatus.NOT_FOUND, "Unknown endpoint.")
            return
        self.handle_api_post(parsed)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def handle_api_get(self, parsed) -> None:
        if parsed.path == "/api/health":
            json_response(self, HTTPStatus.OK, {"status": "ok"})
            return

        with get_connection() as connection:
            if parsed.path == "/api/categories":
                json_response(self, HTTPStatus.OK, {"categories": CATEGORIES})
                return

            user = require_user(connection, self)
            if user is None:
                return

            if parsed.path == "/api/home":
                json_response(self, HTTPStatus.OK, build_home(connection, user))
                return

            if parsed.path == "/api/activities":
                query = parse_qs(parsed.query)
                category = query.get("category", [None])[0]
                radius = query.get("radius", [None])[0]
                city = query.get("city", [user["city"]])[0]
                activities = query_activities(
                    connection,
                    user_id=user["id"],
                    category=category,
                    radius_km=to_int(radius, 0) or None,
                    city=city,
                    include_mine=True,
                )
                json_response(
                    self,
                    HTTPStatus.OK,
                    {
                        "activities": activities,
                        "filters": {
                            "category": category,
                            "radiusKm": to_int(radius, 0) or None,
                            "city": city,
                        },
                    },
                )
                return

            if parsed.path == "/api/matches":
                json_response(self, HTTPStatus.OK, build_matches(connection, user))
                return

            if parsed.path == "/api/user":
                json_response(self, HTTPStatus.OK, build_user_profile(connection, user))
                return

        error_response(self, HTTPStatus.NOT_FOUND, "Unknown endpoint.")

    def handle_api_post(self, parsed) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            error_response(self, HTTPStatus.BAD_REQUEST, "Invalid JSON body.")
            return

        with get_connection() as connection:
            if parsed.path == "/api/auth/signup":
                status, response = signup_user(connection, payload)
                json_response(self, status, response)
                return

            if parsed.path == "/api/auth/login":
                status, response = login_user(connection, payload)
                json_response(self, status, response)
                return

            user = require_user(connection, self)
            if user is None:
                return

            if parsed.path == "/api/auth/logout":
                token = get_token_from_headers(self)
                connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
                json_response(self, HTTPStatus.OK, {"message": "Logged out."})
                return

            if parsed.path == "/api/activities":
                status, response = create_activity(connection, user, payload)
                json_response(self, status, response)
                return

            if parsed.path.startswith("/api/activities/") and parsed.path.endswith("/join"):
                activity_id = to_int(parsed.path.split("/")[3], 0)
                status, response = join_activity(connection, user, activity_id)
                json_response(self, status, response)
                return

            if parsed.path.startswith("/api/requests/") and parsed.path.endswith("/decision"):
                request_id = to_int(parsed.path.split("/")[3], 0)
                status, response = decide_request(connection, user, request_id, str(payload.get("action", "")))
                json_response(self, status, response)
                return

        error_response(self, HTTPStatus.NOT_FOUND, "Unknown endpoint.")

    def serve_static(self, requested_path: str) -> None:
        relative = "index.html" if requested_path in {"", "/"} else requested_path.lstrip("/")
        file_path = (ROOT / relative).resolve()

        try:
            file_path.relative_to(ROOT)
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return

        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(file_path))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run() -> None:
    init_db()
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), SyncansHandler)
    print(f"SYNCANS server running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
