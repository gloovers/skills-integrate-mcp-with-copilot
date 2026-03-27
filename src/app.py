"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import sqlite3
from contextlib import closing
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from pathlib import Path

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# Seed data used only when the database is first initialized.
SEED_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


def get_db_path() -> Path:
    return Path(os.getenv("DATABASE_PATH", str(current_dir / "activities.sqlite")))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_db() -> None:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(get_connection()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL CHECK (max_participants > 0)
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE,
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE(activity_id, student_id)
            );
            """
        )

        existing = conn.execute("SELECT COUNT(*) AS count FROM activities").fetchone()["count"]
        if existing == 0:
            for name, details in SEED_ACTIVITIES.items():
                cursor = conn.execute(
                    """
                    INSERT INTO activities(name, description, schedule, max_participants)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        name,
                        details["description"],
                        details["schedule"],
                        details["max_participants"],
                    ),
                )
                activity_id = cursor.lastrowid

                for email in details["participants"]:
                    conn.execute(
                        "INSERT OR IGNORE INTO students(email) VALUES (?)",
                        (email,),
                    )
                    student_id = conn.execute(
                        "SELECT id FROM students WHERE email = ?",
                        (email,),
                    ).fetchone()["id"]
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO registrations(activity_id, student_id)
                        VALUES (?, ?)
                        """,
                        (activity_id, student_id),
                    )

        conn.commit()


def load_activities() -> dict:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT
                a.name,
                a.description,
                a.schedule,
                a.max_participants,
                s.email
            FROM activities a
            LEFT JOIN registrations r ON r.activity_id = a.id
            LEFT JOIN students s ON s.id = r.student_id
            ORDER BY a.name, s.email
            """
        ).fetchall()

    activities = {}
    for row in rows:
        name = row["name"]
        if name not in activities:
            activities[name] = {
                "description": row["description"],
                "schedule": row["schedule"],
                "max_participants": row["max_participants"],
                "participants": [],
            }

        if row["email"]:
            activities[name]["participants"].append(row["email"])

    return activities


@app.on_event("startup")
def on_startup() -> None:
    initialize_db()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return load_activities()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    with closing(get_connection()) as conn:
        activity = conn.execute(
            "SELECT id FROM activities WHERE name = ?",
            (activity_name,),
        ).fetchone()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        activity_id = activity["id"]

        current_count = conn.execute(
            "SELECT COUNT(*) AS count FROM registrations WHERE activity_id = ?",
            (activity_id,),
        ).fetchone()["count"]
        max_participants = conn.execute(
            "SELECT max_participants FROM activities WHERE id = ?",
            (activity_id,),
        ).fetchone()["max_participants"]
        if current_count >= max_participants:
            raise HTTPException(status_code=400, detail="Activity is full")

        conn.execute("INSERT OR IGNORE INTO students(email) VALUES (?)", (email,))
        student_id = conn.execute(
            "SELECT id FROM students WHERE email = ?",
            (email,),
        ).fetchone()["id"]

        try:
            conn.execute(
                "INSERT INTO registrations(activity_id, student_id) VALUES (?, ?)",
                (activity_id, student_id),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=400,
                detail="Student is already signed up"
            ) from exc

        conn.commit()

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    with closing(get_connection()) as conn:
        activity = conn.execute(
            "SELECT id FROM activities WHERE name = ?",
            (activity_name,),
        ).fetchone()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        student = conn.execute(
            "SELECT id FROM students WHERE email = ?",
            (email,),
        ).fetchone()
        if not student:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity"
            )

        result = conn.execute(
            "DELETE FROM registrations WHERE activity_id = ? AND student_id = ?",
            (activity["id"], student["id"]),
        )
        if result.rowcount == 0:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity"
            )

        conn.commit()

    return {"message": f"Unregistered {email} from {activity_name}"}
