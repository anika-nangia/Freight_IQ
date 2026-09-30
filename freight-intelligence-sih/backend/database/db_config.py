"""
Database Configuration for FreightIQ SIH Backend
Initializes SQLite with Write-Ahead Logging (WAL) mode enabled for high concurrency.
"""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "freightiq.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Enable WAL mode for high concurrent read/write throughput
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Run schema.sql
    schema_file = os.path.join(os.path.dirname(__file__), "schema.sql")
    if os.path.exists(schema_file):
        with open(schema_file, "r") as f:
            cursor.executescript(f.read())
            
    conn.commit()
    conn.close()

@contextmanager
def get_db_cursor():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    finally:
        conn.close()
