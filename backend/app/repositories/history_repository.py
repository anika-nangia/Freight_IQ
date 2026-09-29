"""SQLite persistence for Analysis History (Chrome-style log of user analyses).

SQLite is used because no Supabase/Postgres config exists in this backend.
Swap this module for a Supabase client later without touching routes.
"""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.data.loaders import BACKEND_ROOT
from app.errors import DatasetError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_history (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    port TEXT NOT NULL,
    vessel TEXT,
    inputs TEXT NOT NULL,
    recommendation TEXT
)
"""


def _db_path() -> Path:
    p = Path(get_settings().history_db_path)
    return p if p.is_absolute() or str(p) == ":memory:" else BACKEND_ROOT / p


@contextmanager
def _conn():
    path = _db_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        con.execute(_SCHEMA)
        yield con
        con.commit()
    except sqlite3.Error as exc:
        raise DatasetError("Analysis history storage is unavailable.") from exc
    finally:
        try:
            con.close()
        except UnboundLocalError:
            pass


def _row(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"], "created_at": r["created_at"], "port": r["port"],
        "vessel": r["vessel"], "inputs": json.loads(r["inputs"]),
        "recommendation": json.loads(r["recommendation"]) if r["recommendation"] else None,
    }


def create(port: str, vessel: str | None, inputs: dict, recommendation: dict | None) -> dict:
    rec_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _conn() as con:
        con.execute(
            "INSERT INTO analysis_history VALUES (?,?,?,?,?,?)",
            (rec_id, now, port, vessel, json.dumps(inputs),
             json.dumps(recommendation) if recommendation is not None else None),
        )
    return {"id": rec_id, "created_at": now, "port": port, "vessel": vessel,
            "inputs": inputs, "recommendation": recommendation}


def list_all(limit: int, port: str | None = None) -> list[dict]:
    q, args = "SELECT * FROM analysis_history", []
    if port:
        q += " WHERE lower(port)=lower(?)"; args.append(port)
    q += " ORDER BY created_at DESC, rowid DESC LIMIT ?"; args.append(limit)
    with _conn() as con:
        return [_row(r) for r in con.execute(q, args)]


def get(rec_id: str) -> dict | None:
    with _conn() as con:
        r = con.execute("SELECT * FROM analysis_history WHERE id=?", (rec_id,)).fetchone()
    return _row(r) if r else None


def delete(rec_id: str) -> bool:
    with _conn() as con:
        return con.execute("DELETE FROM analysis_history WHERE id=?", (rec_id,)).rowcount > 0


def clear() -> int:
    with _conn() as con:
        return con.execute("DELETE FROM analysis_history").rowcount
