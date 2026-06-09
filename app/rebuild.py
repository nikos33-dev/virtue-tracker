#!/usr/bin/env python3
"""Rebuild virtues.db (the sqlite query index) from log.jsonl (the truth).

Safe to run anytime. The db is disposable; the JSONL log is the record.
    python3 app/rebuild.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
import core  # noqa: E402

if __name__ == "__main__":
    core.init_db()
    core.rebuild_db_from_log()
    n = len(core.read_log())
    print(f"Rebuilt {core.DB_PATH} from {n} logged day(s).")
