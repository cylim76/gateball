from __future__ import annotations

import json
import shutil
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Iterator


class ResultsStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.backup_dir = db_path.parent / "backups"
        self.lock = RLock()
        self.initialize()

    def initialize(self) -> None:
        with self.lock:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            if self.db_path.exists() and not self.is_healthy(self.db_path):
                self.quarantine_broken_database()
                self.restore_latest_healthy_backup()
            self.create_schema()
            self.backup_once_per_day()

    def connect(self, path: Path | None = None) -> sqlite3.Connection:
        conn = sqlite3.connect(path or self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def connection(self, path: Path | None = None) -> Iterator[sqlite3.Connection]:
        conn = self.connect(path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def create_schema(self) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    match_date TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT NOT NULL,
                    red_team TEXT NOT NULL,
                    red_score INTEGER NOT NULL,
                    white_score INTEGER NOT NULL,
                    white_team TEXT NOT NULL,
                    balls_json TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_matches_ended ON matches(ended_at)")

    def is_healthy(self, path: Path) -> bool:
        try:
            with self.connection(path) as conn:
                row = conn.execute("PRAGMA integrity_check").fetchone()
            return bool(row and row[0] == "ok")
        except sqlite3.Error:
            return False

    def quarantine_broken_database(self) -> None:
        if not self.db_path.exists():
            return
        stamp = time.strftime("%Y%m%d_%H%M%S")
        target = self.backup_dir / f"gateball_broken_{stamp}.sqlite3"
        shutil.copy2(self.db_path, target)
        try:
            self.db_path.unlink()
        except OSError:
            pass

    def restore_latest_healthy_backup(self) -> bool:
        backups = sorted(
            self.backup_dir.glob("gateball_*.sqlite3"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for backup in backups:
            if self.is_healthy(backup):
                shutil.copy2(backup, self.db_path)
                return True
        return False

    def backup_once_per_day(self) -> None:
        if not self.db_path.exists() or not self.is_healthy(self.db_path):
            return
        today = time.strftime("%Y%m%d")
        if any(self.backup_dir.glob(f"gateball_{today}_*.sqlite3")):
            return
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.backup_database(self.backup_dir / f"gateball_{stamp}.sqlite3")

    def backup_database(self, target: Path) -> None:
        source = sqlite3.connect(self.db_path, timeout=5)
        try:
            destination = sqlite3.connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()

    def save_match(self, snapshot: dict[str, Any]) -> int:
        with self.lock:
            ended_at = time.strftime("%Y-%m-%d %H:%M:%S")
            balls = snapshot.get("balls", [])
            row = {
                "match_number": int(snapshot.get("matchNumber", 0)),
                "title": str(snapshot.get("title", "")),
                "match_date": ended_at[:10],
                "started_at": snapshot.get("matchStartedAt"),
                "ended_at": ended_at,
                "red_team": str(snapshot.get("redTeam", "")),
                "red_score": int(snapshot.get("redTotal", 0)),
                "white_score": int(snapshot.get("whiteTotal", 0)),
                "white_team": str(snapshot.get("whiteTeam", "")),
                "balls_json": json.dumps(balls, ensure_ascii=False),
                "snapshot_json": json.dumps(snapshot, ensure_ascii=False),
                "created_at": ended_at,
            }
            with self.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO matches (
                        match_number, title, match_date, started_at, ended_at,
                        red_team, red_score, white_score, white_team,
                        balls_json, snapshot_json, created_at
                    ) VALUES (
                        :match_number, :title, :match_date, :started_at, :ended_at,
                        :red_team, :red_score, :white_score, :white_team,
                        :balls_json, :snapshot_json, :created_at
                    )
                    """,
                    row,
                )
                return int(cursor.lastrowid)

    def month_summary(self, year: int, month: int) -> dict[str, Any]:
        start = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end = f"{year + 1:04d}-01-01"
        else:
            end = f"{year:04d}-{month + 1:02d}-01"
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT match_date, COUNT(*) AS count
                FROM matches
                WHERE match_date >= ? AND match_date < ?
                GROUP BY match_date
                ORDER BY match_date
                """,
                (start, end),
            ).fetchall()
        return {
            "ok": True,
            "year": year,
            "month": month,
            "days": [{"date": row["match_date"], "count": int(row["count"])} for row in rows],
        }

    def matches_for_day(self, date: str) -> dict[str, Any]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, match_number, title, ended_at, red_team, red_score, white_score, white_team
                FROM matches
                WHERE match_date = ?
                ORDER BY ended_at DESC, id DESC
                """,
                (date,),
            ).fetchall()
        return {"ok": True, "date": date, "matches": [dict(row) for row in rows]}

    def match_detail(self, match_id: int) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if not row:
            return {"ok": False, "message": "not found"}
        data = dict(row)
        data["balls"] = json.loads(data.pop("balls_json"))
        data["snapshot"] = json.loads(data.pop("snapshot_json"))
        return {"ok": True, "match": data}
