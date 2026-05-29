import secrets
import sqlite3
import string
from datetime import datetime

import pandas as pd


DB_PATH = "division.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            room_code TEXT PRIMARY KEY,
            project_name TEXT,
            host_name TEXT NOT NULL,
            member_count INTEGER DEFAULT 1,
            phase INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            nickname TEXT NOT NULL,
            is_host INTEGER DEFAULT 0,
            joined_at TEXT NOT NULL,
            UNIQUE(room_code, nickname)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            task_code TEXT NOT NULL,
            task_name TEXT NOT NULL,
            task_type TEXT NOT NULL,
            required_count INTEGER NOT NULL,
            display_order INTEGER NOT NULL,
            UNIQUE(room_code, task_code)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS task_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            task_code TEXT NOT NULL,
            question_code TEXT NOT NULL,
            question_text TEXT NOT NULL,
            display_order INTEGER NOT NULL,
            UNIQUE(room_code, question_code)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS motivation_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            nickname TEXT NOT NULL,
            task_code TEXT NOT NULL,
            question_code TEXT NOT NULL,
            score REAL NOT NULL,
            UNIQUE(room_code, nickname, question_code)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS task_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            nickname TEXT NOT NULL,
            task_code TEXT NOT NULL,
            avg_score REAL NOT NULL,
            UNIQUE(room_code, nickname, task_code)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS preference_ranks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            nickname TEXT NOT NULL,
            task_code TEXT NOT NULL,
            task_type TEXT NOT NULL,
            rank INTEGER NOT NULL,
            UNIQUE(room_code, nickname, task_code)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            nickname TEXT NOT NULL,
            task_code TEXT NOT NULL,
            task_type TEXT NOT NULL,
            slot_name TEXT NOT NULL,
            motivation_score REAL NOT NULL,
            preference_rank INTEGER NOT NULL,
            cost REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def _make_room_code():
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def create_room(nickname):
    init_db()
    nickname = nickname.strip()
    if not nickname:
        raise ValueError("請輸入 nickname")

    conn = get_connection()
    cur = conn.cursor()
    while True:
        room_code = _make_room_code()
        exists = cur.execute(
            "SELECT room_code FROM rooms WHERE room_code = ?", (room_code,)
        ).fetchone()
        if not exists:
            break

    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        """
        INSERT INTO rooms (room_code, project_name, host_name, member_count, phase, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (room_code, "未命名專案", nickname, 1, 0, now),
    )
    cur.execute(
        """
        INSERT INTO members (room_code, nickname, is_host, joined_at)
        VALUES (?, ?, ?, ?)
        """,
        (room_code, nickname, 1, now),
    )
    conn.commit()
    conn.close()
    return room_code


def join_room(room_code, nickname, is_host=False):
    init_db()
    room_code = room_code.strip().upper()
    nickname = nickname.strip()
    if not nickname:
        raise ValueError("請輸入 nickname")
    if get_room(room_code) is None:
        raise ValueError("room_code 不存在")

    conn = get_connection()
    existing = conn.execute(
        """
        SELECT nickname, is_host
        FROM members
        WHERE room_code = ? AND nickname = ?
        """,
        (room_code, nickname),
    ).fetchone()
    if existing:
        conn.close()
        return {
            "room_code": room_code,
            "nickname": existing["nickname"],
            "is_host": bool(existing["is_host"]),
            "is_existing": True,
        }

    conn.execute(
        """
        INSERT INTO members (room_code, nickname, is_host, joined_at)
        VALUES (?, ?, ?, ?)
        """,
        (room_code, nickname, int(is_host), datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()
    return {
        "room_code": room_code,
        "nickname": nickname,
        "is_host": bool(is_host),
        "is_existing": False,
    }


def get_room(room_code):
    conn = get_connection()
    row = conn.execute("SELECT * FROM rooms WHERE room_code = ?", (room_code,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_members(room_code):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT nickname, is_host, joined_at FROM members WHERE room_code = ? ORDER BY joined_at",
        conn,
        params=(room_code,),
    )
    conn.close()
    return df


def save_project_settings(room_code, project_name, member_count):
    conn = get_connection()
    conn.execute(
        """
        UPDATE rooms
        SET project_name = ?, member_count = ?
        WHERE room_code = ?
        """,
        (project_name.strip(), int(member_count), room_code),
    )
    conn.commit()
    conn.close()


def get_project_settings(room_code):
    room = get_room(room_code)
    if not room:
        return {}
    return {
        "project_name": room["project_name"],
        "member_count": room["member_count"],
        "phase": room["phase"],
    }


def save_tasks(room_code, tasks_df):
    conn = get_connection()
    conn.execute("DELETE FROM tasks WHERE room_code = ?", (room_code,))
    for index, row in tasks_df.reset_index(drop=True).iterrows():
        conn.execute(
            """
            INSERT INTO tasks (room_code, task_code, task_name, task_type, required_count, display_order)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                room_code,
                str(row["task_code"]).strip().upper(),
                str(row["task_name"]).strip(),
                str(row["task_type"]).strip(),
                int(row["required_count"]),
                index + 1,
            ),
        )
    conn.commit()
    conn.close()


def get_tasks(room_code):
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT task_code, task_name, task_type, required_count, display_order
        FROM tasks
        WHERE room_code = ?
        ORDER BY display_order, task_code
        """,
        conn,
        params=(room_code,),
    )
    conn.close()
    return df


def save_questions(room_code, questions_df):
    conn = get_connection()
    conn.execute("DELETE FROM task_questions WHERE room_code = ?", (room_code,))
    for index, row in questions_df.reset_index(drop=True).iterrows():
        conn.execute(
            """
            INSERT INTO task_questions (room_code, task_code, question_code, question_text, display_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                room_code,
                str(row["task_code"]).strip().upper(),
                str(row["question_code"]).strip().upper(),
                str(row["question_text"]).strip(),
                index + 1,
            ),
        )
    conn.commit()
    conn.close()


def get_questions(room_code):
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT task_code, question_code, question_text, display_order
        FROM task_questions
        WHERE room_code = ?
        ORDER BY display_order, question_code
        """,
        conn,
        params=(room_code,),
    )
    conn.close()
    return df


def has_submitted(room_code, nickname):
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM task_scores WHERE room_code = ? AND nickname = ? LIMIT 1",
        (room_code, nickname),
    ).fetchone()
    conn.close()
    return row is not None


def save_member_response(room_code, nickname, raw_scores_df, avg_scores_df, ranks_df):
    if has_submitted(room_code, nickname):
        raise ValueError("同一成員在同一房間只能提交一次")

    conn = get_connection()
    try:
        for _, row in raw_scores_df.iterrows():
            conn.execute(
                """
                INSERT INTO motivation_responses
                (room_code, nickname, task_code, question_code, score)
                VALUES (?, ?, ?, ?, ?)
                """,
                (room_code, nickname, row["task_code"], row["question_code"], float(row["score"])),
            )
        for _, row in avg_scores_df.iterrows():
            conn.execute(
                """
                INSERT INTO task_scores (room_code, nickname, task_code, avg_score)
                VALUES (?, ?, ?, ?)
                """,
                (room_code, nickname, row["task_code"], float(row["avg_score"])),
            )
        for _, row in ranks_df.iterrows():
            conn.execute(
                """
                INSERT INTO preference_ranks
                (room_code, nickname, task_code, task_type, rank)
                VALUES (?, ?, ?, ?, ?)
                """,
                (room_code, nickname, row["task_code"], row["task_type"], int(row["rank"])),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_member_responses(room_code):
    conn = get_connection()
    scores = pd.read_sql_query(
        "SELECT nickname, task_code, avg_score FROM task_scores WHERE room_code = ?",
        conn,
        params=(room_code,),
    )
    ranks = pd.read_sql_query(
        "SELECT nickname, task_code, task_type, rank FROM preference_ranks WHERE room_code = ?",
        conn,
        params=(room_code,),
    )
    raw = pd.read_sql_query(
        """
        SELECT nickname, task_code, question_code, score
        FROM motivation_responses
        WHERE room_code = ?
        """,
        conn,
        params=(room_code,),
    )
    conn.close()
    return {"scores": scores, "ranks": ranks, "raw_scores": raw}


def get_submitted_members(room_code):
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT DISTINCT nickname
        FROM task_scores
        WHERE room_code = ?
        ORDER BY nickname
        """,
        conn,
        params=(room_code,),
    )
    conn.close()
    return df["nickname"].tolist()


def update_phase(room_code, phase):
    conn = get_connection()
    conn.execute("UPDATE rooms SET phase = ? WHERE room_code = ?", (int(phase), room_code))
    conn.commit()
    conn.close()


def get_phase(room_code):
    room = get_room(room_code)
    return int(room["phase"]) if room else None


def save_assignments(room_code, assignment_df):
    conn = get_connection()
    conn.execute("DELETE FROM assignments WHERE room_code = ?", (room_code,))
    for _, row in assignment_df.iterrows():
        conn.execute(
            """
            INSERT INTO assignments
            (room_code, nickname, task_code, task_type, slot_name, motivation_score, preference_rank, cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                room_code,
                row["nickname"],
                row["task_code"],
                row["task_type"],
                row["slot_name"],
                float(row["motivation_score"]),
                int(row["preference_rank"]),
                float(row["cost"]),
            ),
        )
    conn.commit()
    conn.close()
