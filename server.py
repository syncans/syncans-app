from __future__ import annotations

import json
import mimetypes
import os
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
    {"name": "Trek", "icon": "Altitude"},
    {"name": "Gym", "icon": "Strength"},
    {"name": "Study", "icon": "Focus"},
    {"name": "Startup", "icon": "Build"},
    {"name": "Cafe", "icon": "Brew"},
    {"name": "Sports", "icon": "Play"},
    {"name": "Culture", "icon": "Explore"},
    {"name": "Music", "icon": "Jam"},
]

SEED_USERS = [
    {
        "name": "Riya S.",
        "gender": "woman",
        "category": "Trek",
        "distance_km": 7,
        "vibe": "Weekend hiker",
        "reputation": 4.9,
        "phone_verified": 1,
        "id_verified": 1,
        "availability": "Free now",
        "bio": "Early riser, carries first-aid and knows the route.",
        "city": "Pune",
    },
    {
        "name": "Arjun K.",
        "gender": "man",
        "category": "Startup",
        "distance_km": 5,
        "vibe": "Product builder",
        "reputation": 4.8,
        "phone_verified": 1,
        "id_verified": 1,
        "availability": "Next 45 mins",
        "bio": "Interested in quick founder coffee and GTM brainstorming.",
        "city": "Mumbai",
    },
    {
        "name": "Megha P.",
        "gender": "woman",
        "category": "Study",
        "distance_km": 4,
        "vibe": "Deep work partner",
        "reputation": 4.7,
        "phone_verified": 1,
        "id_verified": 0,
        "availability": "Until 9 PM",
        "bio": "Pomodoro fan, prefers library sessions and quiet cafes.",
        "city": "Pune",
    },
    {
        "name": "Kabir J.",
        "gender": "man",
        "category": "Gym",
        "distance_km": 8,
        "vibe": "Consistency buddy",
        "reputation": 4.6,
        "phone_verified": 1,
        "id_verified": 0,
        "availability": "Starts in 20 mins",
        "bio": "Push-pull-legs regular, good for accountability sessions.",
        "city": "Pune",
    },
    {
        "name": "Sana M.",
        "gender": "woman",
        "category": "Trek",
        "distance_km": 11,
        "vibe": "Trail regular",
        "reputation": 4.95,
        "phone_verified": 1,
        "id_verified": 1,
        "availability": "Ready by 5:30 AM",
        "bio": "Prefers verified groups and small batches for sunrise climbs.",
        "city": "Pune",
    },
    {
        "name": "Vikram N.",
        "gender": "man",
        "category": "Sports",
        "distance_km": 13,
        "vibe": "Pickup organizer",
        "reputation": 4.5,
        "phone_verified": 1,
        "id_verified": 0,
        "availability": "After work",
        "bio": "Usually pulls together football and badminton groups quickly.",
        "city": "Bangalore",
    },
    {
        "name": "Aisha T.",
        "gender": "woman",
        "category": "Cafe",
        "distance_km": 6,
        "vibe": "City explorer",
        "reputation": 4.8,
        "phone_verified": 1,
        "id_verified": 1,
        "availability": "Free now",
        "bio": "Always down for a quick coffee run and conversation.",
        "city": "Mumbai",
    },
    {
        "name": "Neil D.",
        "gender": "man",
        "category": "Culture",
        "distance_km": 9,
        "vibe": "Event scout",
        "reputation": 4.4,
        "phone_verified": 0,
        "id_verified": 0,
        "availability": "Tonight",
        "bio": "Likes exhibitions, community events, and local performances.",
        "city": "Pune",
    },
]

SEED_ACTIVITY = {
    "title": "Sunrise trek to Sinhgad",
    "category": "Trek",
    "start_time": "06:00",
    "location": "Pune",
    "skill_level": "Intermediate",
    "slots": 5,
    "radius_km": 12,
    "notes": "Carry water, torch, and light jacket",
    "verified_only": 1,
    "women_only": 0,
    "approved_count": 2,
    "status": "active",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              gender TEXT NOT NULL,
              category TEXT NOT NULL,
              distance_km REAL NOT NULL,
              vibe TEXT NOT NULL,
              reputation REAL NOT NULL,
              phone_verified INTEGER NOT NULL DEFAULT 1,
              id_verified INTEGER NOT NULL DEFAULT 0,
              availability TEXT NOT NULL,
              bio TEXT NOT NULL,
              city TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS activities (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              category TEXT NOT NULL,
              start_time TEXT NOT NULL,
              location TEXT NOT NULL,
              skill_level TEXT NOT NULL,
              slots INTEGER NOT NULL,
              radius_km INTEGER NOT NULL,
              notes TEXT NOT NULL,
              verified_only INTEGER NOT NULL DEFAULT 1,
              women_only INTEGER NOT NULL DEFAULT 0,
              approved_count INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS join_requests (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              message TEXT NOT NULL,
              status TEXT NOT NULL,
              source TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notifications (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              body TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )

        user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            connection.executemany(
                """
                INSERT INTO users (
                  name, gender, category, distance_km, vibe, reputation,
                  phone_verified, id_verified, availability, bio, city
                )
                VALUES (
                  :name, :gender, :category, :distance_km, :vibe, :reputation,
                  :phone_verified, :id_verified, :availability, :bio, :city
                )
                """,
                SEED_USERS,
            )

        activity_count = connection.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        if activity_count == 0:
            activity_id = connection.execute(
                """
                INSERT INTO activities (
                  title, category, start_time, location, skill_level, slots,
                  radius_km, notes, verified_only, women_only, approved_count,
                  status, created_at
                )
                VALUES (
                  :title, :category, :start_time, :location, :skill_level, :slots,
                  :radius_km, :notes, :verified_only, :women_only, :approved_count,
                  :status, :created_at
                )
                """,
                {**SEED_ACTIVITY, "created_at": now_iso()},
            ).lastrowid

            create_seed_requests(connection, activity_id)
            push_notification(
                connection,
                "Verified cluster found",
                "3 trekkers within 12 km match your preferred skill level.",
            )
            push_notification(
                connection,
                "Safety mode active",
                "Controlled messaging and approval-only joins are enabled.",
            )


def create_seed_requests(connection: sqlite3.Connection, activity_id: int) -> None:
    connection.executemany(
        """
        INSERT INTO join_requests (activity_id, user_id, message, status, source, created_at)
        VALUES (?, ?, ?, 'pending', 'matched', ?)
        """,
        [
            (
                activity_id,
                1,
                "I have done this trail twice and can bring a spare torch.",
                now_iso(),
            ),
            (
                activity_id,
                5,
                "Happy to join if the group stays small and verified.",
                now_iso(),
            ),
        ],
    )


def push_notification(connection: sqlite3.Connection, title: str, body: str) -> None:
    connection.execute(
        "INSERT INTO notifications (title, body, created_at) VALUES (?, ?, ?)",
        (title, body, now_iso()),
    )


def get_current_activity(connection: sqlite3.Connection) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM activities ORDER BY created_at DESC, id DESC LIMIT 1"
    ).fetchone()


def serialize_activity(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "time": row["start_time"],
        "location": row["location"],
        "skillLevel": row["skill_level"],
        "slots": row["slots"],
        "radiusKm": row["radius_km"],
        "notes": row["notes"],
        "verifiedOnly": bool(row["verified_only"]),
        "womenOnly": bool(row["women_only"]),
        "approvedCount": row["approved_count"],
        "status": row["status"],
        "createdAt": row["created_at"],
    }


def fetch_matching_users(
    connection: sqlite3.Connection,
    *,
    category: str,
    radius_km: int,
    verified_only: bool,
    women_only: bool,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT *
        FROM users
        WHERE category = ?
          AND distance_km <= ?
          AND (? = 0 OR phone_verified = 1)
          AND (? = 0 OR gender = 'woman')
        ORDER BY id_verified DESC, reputation DESC, distance_km ASC, id ASC
        """,
        (category, radius_km, int(verified_only), int(women_only)),
    ).fetchall()


def build_dashboard(
    connection: sqlite3.Connection,
    *,
    category: str | None = None,
    radius_km: int | None = None,
    verified_only: bool | None = None,
    women_only: bool | None = None,
) -> dict[str, Any]:
    activity = get_current_activity(connection)
    if activity is None:
        return {
            "categories": CATEGORIES,
            "currentActivity": None,
            "metrics": {"matchCount": 0, "requestCount": 0, "trustScore": 4.8},
            "nearbyUsers": [],
            "requestQueue": [],
            "notifications": [],
            "filters": {},
        }

    active_category = category or activity["category"]
    active_radius = radius_km if radius_km is not None else activity["radius_km"]
    active_verified_only = (
        verified_only if verified_only is not None else bool(activity["verified_only"])
    )
    active_women_only = women_only if women_only is not None else bool(activity["women_only"])

    users = fetch_matching_users(
        connection,
        category=active_category,
        radius_km=active_radius,
        verified_only=active_verified_only,
        women_only=active_women_only,
    )

    request_rows = connection.execute(
        """
        SELECT
          jr.id,
          jr.message,
          jr.status,
          jr.source,
          u.id AS user_id,
          u.name,
          u.gender,
          u.category,
          u.distance_km,
          u.vibe,
          u.reputation,
          u.phone_verified,
          u.id_verified,
          u.availability,
          u.bio,
          u.city
        FROM join_requests jr
        JOIN users u ON u.id = jr.user_id
        WHERE jr.activity_id = ? AND jr.status = 'pending'
        ORDER BY u.id_verified DESC, u.reputation DESC, u.distance_km ASC, jr.id DESC
        """,
        (activity["id"],),
    ).fetchall()

    notifications = connection.execute(
        "SELECT * FROM notifications ORDER BY created_at DESC, id DESC LIMIT 5"
    ).fetchall()

    match_count = len(users)
    request_count = len(request_rows)
    trust_score = round(min(4.6 + (activity["approved_count"] * 0.1), 4.95), 1)

    return {
        "categories": CATEGORIES,
        "currentActivity": serialize_activity(activity),
        "metrics": {
            "matchCount": match_count,
            "requestCount": request_count,
            "trustScore": trust_score,
        },
        "nearbyUsers": [
            {
                "id": row["id"],
                "name": row["name"],
                "gender": row["gender"],
                "category": row["category"],
                "distanceKm": row["distance_km"],
                "vibe": row["vibe"],
                "reputation": row["reputation"],
                "phoneVerified": bool(row["phone_verified"]),
                "idVerified": bool(row["id_verified"]),
                "availability": row["availability"],
                "bio": row["bio"],
                "city": row["city"],
            }
            for row in users
        ],
        "requestQueue": [
            {
                "id": row["id"],
                "message": row["message"],
                "source": row["source"],
                "person": {
                    "id": row["user_id"],
                    "name": row["name"],
                    "gender": row["gender"],
                    "category": row["category"],
                    "distanceKm": row["distance_km"],
                    "vibe": row["vibe"],
                    "reputation": row["reputation"],
                    "phoneVerified": bool(row["phone_verified"]),
                    "idVerified": bool(row["id_verified"]),
                    "availability": row["availability"],
                    "bio": row["bio"],
                    "city": row["city"],
                },
            }
            for row in request_rows
        ],
        "notifications": [
            {
                "id": row["id"],
                "title": row["title"],
                "body": row["body"],
                "timestamp": row["created_at"],
            }
            for row in notifications
        ],
        "filters": {
            "category": active_category,
            "radiusKm": active_radius,
            "verifiedOnly": active_verified_only,
            "womenOnly": active_women_only,
        },
    }


def create_activity(connection: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    connection.execute("UPDATE activities SET status = 'closed' WHERE status = 'active'")

    activity = {
        "title": str(payload.get("title", "Untitled activity")).strip()[:70] or "Untitled activity",
        "category": str(payload.get("category", "Trek")),
        "start_time": str(payload.get("time", "06:00")),
        "location": str(payload.get("location", "Pune")).strip()[:40] or "Pune",
        "skill_level": str(payload.get("skillLevel", "Beginner friendly")).strip()[:40],
        "slots": max(2, min(int(payload.get("slots", 5)), 10)),
        "radius_km": max(5, min(int(payload.get("radius", 12)), 25)),
        "notes": str(payload.get("notes", "")).strip()[:120],
        "verified_only": int(to_bool(payload.get("verifiedOnly", True))),
        "women_only": int(to_bool(payload.get("womenOnly", False))),
        "approved_count": 0,
        "status": "active",
        "created_at": now_iso(),
    }

    activity_id = connection.execute(
        """
        INSERT INTO activities (
          title, category, start_time, location, skill_level, slots, radius_km,
          notes, verified_only, women_only, approved_count, status, created_at
        )
        VALUES (
          :title, :category, :start_time, :location, :skill_level, :slots, :radius_km,
          :notes, :verified_only, :women_only, :approved_count, :status, :created_at
        )
        """,
        activity,
    ).lastrowid

    matches = fetch_matching_users(
        connection,
        category=activity["category"],
        radius_km=activity["radius_km"],
        verified_only=bool(activity["verified_only"]),
        women_only=bool(activity["women_only"]),
    )[:3]

    seeded_requests = []
    for index, user in enumerate(matches):
        message = (
            f"I'm close by and can make it by {activity['start_time']}."
            if index == 0
            else f"Interested in joining. {user['vibe'].lower()} and available {user['availability'].lower()}."
        )
        seeded_requests.append(
            (activity_id, user["id"], message, "pending", "matched", now_iso())
        )

    if seeded_requests:
        connection.executemany(
            """
            INSERT INTO join_requests (activity_id, user_id, message, status, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            seeded_requests,
        )

    push_notification(
        connection,
        "Intent posted",
        f"{activity['title']} is live for {activity['category'].lower()} matches within {activity['radius_km']} km.",
    )

    if matches:
        push_notification(
            connection,
            "Live cluster found",
            f"{len(matches)} nearby people fit this activity's current filters.",
        )
    else:
        push_notification(
            connection,
            "No instant matches yet",
            "Try widening the radius or relaxing filters to pull in more people.",
        )

    return build_dashboard(
        connection,
        category=activity["category"],
        radius_km=activity["radius_km"],
        verified_only=bool(activity["verified_only"]),
        women_only=bool(activity["women_only"]),
    )


def decide_request(
    connection: sqlite3.Connection,
    request_id: int,
    action: str,
) -> tuple[int, dict[str, Any]]:
    row = connection.execute(
        """
        SELECT jr.id, jr.activity_id, jr.user_id, jr.status, u.name
        FROM join_requests jr
        JOIN users u ON u.id = jr.user_id
        WHERE jr.id = ?
        """,
        (request_id,),
    ).fetchone()

    if row is None:
        return HTTPStatus.NOT_FOUND, {"error": "Join request not found."}

    activity = connection.execute(
        "SELECT * FROM activities WHERE id = ?", (row["activity_id"],)
    ).fetchone()
    if activity is None:
        return HTTPStatus.NOT_FOUND, {"error": "Activity not found."}

    if action == "approve":
        if activity["approved_count"] >= activity["slots"]:
            return HTTPStatus.CONFLICT, {"error": "This activity is already full."}

        connection.execute(
            "UPDATE join_requests SET status = 'approved' WHERE id = ?",
            (request_id,),
        )
        connection.execute(
            "UPDATE activities SET approved_count = approved_count + 1 WHERE id = ?",
            (activity["id"],),
        )
        push_notification(
            connection,
            "Request approved",
            f"{row['name']} joined your activity group.",
        )
    elif action == "decline":
        connection.execute(
            "UPDATE join_requests SET status = 'declined' WHERE id = ?",
            (request_id,),
        )
        push_notification(
            connection,
            "Request updated",
            f"{row['name']} was not added to this activity.",
        )
    else:
        return HTTPStatus.BAD_REQUEST, {"error": "Unsupported action."}

    return HTTPStatus.OK, build_dashboard(connection)


def create_invitation(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    activity_id: int | None,
) -> tuple[int, dict[str, Any]]:
    activity = (
        connection.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
        if activity_id
        else get_current_activity(connection)
    )
    if activity is None:
        return HTTPStatus.NOT_FOUND, {"error": "No active activity to invite into."}

    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        return HTTPStatus.NOT_FOUND, {"error": "User not found."}

    existing = connection.execute(
        """
        SELECT id
        FROM join_requests
        WHERE activity_id = ? AND user_id = ? AND status IN ('pending', 'approved')
        """,
        (activity["id"], user_id),
    ).fetchone()
    if existing is not None:
        return HTTPStatus.CONFLICT, {"error": "That user is already invited to this activity."}

    connection.execute(
        """
        INSERT INTO join_requests (activity_id, user_id, message, status, source, created_at)
        VALUES (?, ?, ?, 'pending', 'invite', ?)
        """,
        (
            activity["id"],
            user_id,
            "This person was invited by the activity creator and is waiting for approval.",
            now_iso(),
        ),
    )
    push_notification(
        connection,
        "Invite sent",
        f"{user['name']} received your activity invite.",
    )
    return HTTPStatus.OK, build_dashboard(connection)


class SyncansHandler(BaseHTTPRequestHandler):
    server_version = "SYNCANS/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            json_response(self, HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint."})
            return
        self.handle_api_post(parsed)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def handle_api_get(self, parsed) -> None:
        if parsed.path == "/api/health":
            json_response(self, HTTPStatus.OK, {"status": "ok"})
            return

        if parsed.path == "/api/dashboard":
            query = parse_qs(parsed.query)
            category = query.get("category", [None])[0]
            radius = query.get("radius", [None])[0]
            verified_only = query.get("verifiedOnly", [None])[0]
            women_only = query.get("womenOnly", [None])[0]

            with get_connection() as connection:
                payload = build_dashboard(
                    connection,
                    category=category,
                    radius_km=int(radius) if radius else None,
                    verified_only=to_bool(verified_only) if verified_only is not None else None,
                    women_only=to_bool(women_only) if women_only is not None else None,
                )
            json_response(self, HTTPStatus.OK, payload)
            return

        json_response(self, HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint."})

    def handle_api_post(self, parsed) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body."})
            return

        with get_connection() as connection:
            if parsed.path == "/api/activities":
                response = create_activity(connection, payload)
                json_response(self, HTTPStatus.CREATED, response)
                return

            if parsed.path == "/api/invitations":
                status, response = create_invitation(
                    connection,
                    user_id=int(payload.get("userId", 0)),
                    activity_id=payload.get("activityId"),
                )
                json_response(self, status, response)
                return

            if parsed.path.startswith("/api/requests/") and parsed.path.endswith("/decision"):
                request_id = parsed.path.split("/")[3]
                status, response = decide_request(
                    connection,
                    request_id=int(request_id),
                    action=str(payload.get("action", "")),
                )
                json_response(self, status, response)
                return

        json_response(self, HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint."})

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
    address = (host, port)
    server = ThreadingHTTPServer(address, SyncansHandler)
    print(f"SYNCANS server running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
