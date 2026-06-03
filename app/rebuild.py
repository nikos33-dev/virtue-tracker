#!/usr/bin/env python3
"""Rebuild virtues.db (the sqlite query index) from log.jsonl (the truth).

Safe to run anytime. The db is disposable; the JSONL log is the record.
    python3 virtues/app/rebuild.py
"""
import server  # same directory

if __name__ == "__main__":
    server.init_db()
    server.rebuild_db_from_log()
    n = len(server.read_log())
    print(f"Rebuilt {server.DB_PATH} from {n} logged day(s).")
