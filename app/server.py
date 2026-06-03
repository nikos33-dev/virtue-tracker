#!/usr/bin/env python3
"""
Virtues dashboard — Benjamin Franklin's method, adapted to Nikos (23 virtues).

Zero dependencies: Python standard library only (http.server, sqlite3, json).
- Truth of record: virtues/log.jsonl  (append/upsert, one line per day, git-committed, diffable)
- Query index:     virtues/virtues.db  (sqlite, rebuilt from the log, git-ignored)

Run:   python3 virtues/app/server.py
Then:  http://localhost:8765  (opens automatically)

The daily review marks a fault ("black dot") against any of the 23 virtues, with an
optional "what went wrong" note. One virtue per week is the focal virtue; it carries a
required focal note. Cycle anchor = the earliest logged review. Week 1 focal = Temperance.
"""

import json
import os
import sqlite3
import threading
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # virtues/
CONFIG_PATH = os.path.join(ROOT, "config.json")
LOG_PATH = os.path.join(ROOT, "log.jsonl")
DB_PATH = os.path.join(ROOT, "virtues.db")
INDEX_HTML = os.path.join(HERE, "index.html")
PORT = 8765

with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)
VIRTUES = sorted(CONFIG["virtues"], key=lambda v: v["order"])
SLUGS = [v["slug"] for v in VIRTUES]
SLUG_SET = set(SLUGS)
FOCAL_DAYS = CONFIG["cycle"].get("focal_days", 7)
CUTOFF_HOUR = CONFIG["cycle"].get("day_cutoff_hour", 4)
N = len(VIRTUES)

# ---------------------------------------------------------------- storage layer

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS virtues (
            slug TEXT PRIMARY KEY, name TEXT, ord INTEGER, tier TEXT,
            custom INTEGER, precept TEXT, dot TEXT, bite TEXT
        );
        CREATE TABLE IF NOT EXISTS days (
            day TEXT PRIMARY KEY, week INTEGER, focal_slug TEXT,
            focal_note TEXT, reviewed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS entries (
            day TEXT, slug TEXT, fault INTEGER, note TEXT,
            PRIMARY KEY (day, slug)
        );
        """
    )
    for v in VIRTUES:
        con.execute(
            "INSERT OR REPLACE INTO virtues VALUES (?,?,?,?,?,?,?,?)",
            (v["slug"], v["name"], v["order"], v["tier"], int(v["custom"]),
             v["precept"], v.get("dot"), v.get("bite")),
        )
    con.commit()
    con.close()


def read_log():
    """Return {day: record} from the JSONL truth file."""
    days = {}
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                days[rec["day"]] = rec
    return days


def write_log(days):
    """Rewrite the JSONL truth file, one record per day, sorted by date."""
    tmp = LOG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for day in sorted(days):
            f.write(json.dumps(days[day], ensure_ascii=False) + "\n")
    os.replace(tmp, LOG_PATH)


def rebuild_db_from_log():
    """Regenerate sqlite day/entry rows from the JSONL truth."""
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM days")
    con.execute("DELETE FROM entries")
    for rec in read_log().values():
        con.execute(
            "INSERT OR REPLACE INTO days VALUES (?,?,?,?,?)",
            (rec["day"], rec.get("week"), rec.get("focal"),
             rec.get("focal_note"), rec.get("reviewed_at")),
        )
        for slug, e in rec.get("entries", {}).items():
            con.execute(
                "INSERT OR REPLACE INTO entries VALUES (?,?,?,?)",
                (rec["day"], slug, int(bool(e.get("fault"))), e.get("note") or ""),
            )
    con.commit()
    con.close()

# ----------------------------------------------------------------- cycle logic

def cycle_start(days=None):
    """Anchor = earliest logged day. If nothing logged yet, anchor = today."""
    days = read_log() if days is None else days
    if not days:
        return date.today()
    return date.fromisoformat(min(days))


def week_for(d, start):
    """1-based week index for date d relative to the cycle anchor."""
    if d < start:
        return 1
    return (d - start).days // FOCAL_DAYS + 1


def focal_for(week):
    return VIRTUES[(week - 1) % N]


def suggested_day():
    """A review opened before the cutoff hour defaults to the day that just ended."""
    now = datetime.now()
    d = now.date()
    if now.hour < CUTOFF_HOUR:
        d = d - timedelta(days=1)
    return d.isoformat()

# ------------------------------------------------------------------- analytics

def chart_payload():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    days = read_log()
    start = cycle_start(days)

    reviewed = sorted(days)
    # Daily total faults over time.
    daily_totals = []
    for d in reviewed:
        faults = sum(1 for e in days[d].get("entries", {}).values() if e.get("fault"))
        daily_totals.append({"day": d, "faults": faults})

    # Per-virtue: total faults and how many days it was reviewed.
    per_virtue = []
    for v in VIRTUES:
        rows = con.execute(
            "SELECT COUNT(*) reviewed, COALESCE(SUM(fault),0) faults "
            "FROM entries WHERE slug=?", (v["slug"],)
        ).fetchone()
        per_virtue.append({
            "slug": v["slug"], "name": v["name"], "tier": v["tier"],
            "faults": rows["faults"], "reviewed": rows["reviewed"],
        })

    # Pass-over-pass: faults per virtue grouped by cycle pass (Franklin's thesis).
    passes = {}
    for d in reviewed:
        wk = week_for(date.fromisoformat(d), start)
        p = (wk - 1) // N  # pass 0, 1, 2 ...
        for slug, e in days[d].get("entries", {}).items():
            if e.get("fault"):
                passes.setdefault(slug, {}).setdefault(p, 0)
                passes[slug][p] += 1
    max_pass = max((p for s in passes.values() for p in s), default=-1)

    # Focal-week lift: fault rate while a virtue was focal vs. while it was not.
    focal_lift = []
    for v in VIRTUES:
        on_f = on_r = off_f = off_r = 0
        for d in reviewed:
            e = days[d].get("entries", {}).get(v["slug"])
            if e is None:
                continue
            is_focal = days[d].get("focal") == v["slug"]
            if is_focal:
                on_r += 1
                on_f += 1 if e.get("fault") else 0
            else:
                off_r += 1
                off_f += 1 if e.get("fault") else 0
        focal_lift.append({
            "slug": v["slug"], "name": v["name"],
            "focal_rate": (on_f / on_r) if on_r else None,
            "other_rate": (off_f / off_r) if off_r else None,
            "focal_days": on_r,
        })

    con.close()
    return {
        "daily_totals": daily_totals,
        "per_virtue": per_virtue,
        "passes": passes,
        "max_pass": max_pass,
        "focal_lift": focal_lift,
        "reviewed_count": len(reviewed),
    }


def grid_payload(anchor_day):
    """7-day Franklin grid for the week containing anchor_day."""
    days = read_log()
    start = cycle_start(days)
    d = date.fromisoformat(anchor_day)
    week = week_for(d, start)
    week_start = start + timedelta(days=(week - 1) * FOCAL_DAYS)
    cols = [(week_start + timedelta(days=i)).isoformat() for i in range(FOCAL_DAYS)]
    matrix = []
    for v in VIRTUES:
        row = []
        for col in cols:
            rec = days.get(col)
            if rec is None:
                row.append(None)  # not reviewed
            else:
                e = rec.get("entries", {}).get(v["slug"], {})
                row.append(bool(e.get("fault")))
        matrix.append({"slug": v["slug"], "name": v["name"], "cells": row})
    return {
        "week": week, "focal": focal_for(week)["slug"],
        "cols": cols, "matrix": matrix,
    }

# ---------------------------------------------------------------- http handler

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # quiet

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            with open(INDEX_HTML, encoding="utf-8") as f:
                return self._send(200, f.read(), "text/html")
        if u.path == "/api/config":
            day = q.get("date", [suggested_day()])[0]
            days = read_log()
            start = cycle_start(days)
            week = week_for(date.fromisoformat(day), start)
            return self._send(200, {
                "virtues": VIRTUES,
                "suggested_day": suggested_day(),
                "today": date.today().isoformat(),
                "cutoff_hour": CUTOFF_HOUR,
                "cycle_start": start.isoformat(),
                "selected": {
                    "day": day, "week": week,
                    "focal": focal_for(week)["slug"],
                    "pass": (week - 1) // N + 1,
                },
                "logged_days": sorted(days),
            })
        if u.path == "/api/day":
            day = q.get("date", [suggested_day()])[0]
            days = read_log()
            return self._send(200, days.get(day, {"day": day, "entries": {}}))
        if u.path == "/api/charts":
            return self._send(200, chart_payload())
        if u.path == "/api/grid":
            day = q.get("date", [suggested_day()])[0]
            return self._send(200, grid_payload(day))
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            return self._send(400, {"error": "bad json"})

        if u.path == "/api/save":
            day = body.get("day")
            if not day:
                return self._send(400, {"error": "missing day"})
            try:
                d = date.fromisoformat(day)
            except ValueError:
                return self._send(400, {"error": "bad date"})

            # Sanitize entries against the known virtue slugs.
            clean = {}
            for slug in SLUGS:
                e = body.get("entries", {}).get(slug, {})
                clean[slug] = {
                    "fault": bool(e.get("fault")),
                    "note": (e.get("note") or "").strip(),
                }

            days = read_log()
            start = cycle_start({**days, day: True})  # include new day in anchor calc
            week = week_for(d, start)
            rec = {
                "day": day,
                "week": week,
                "focal": focal_for(week)["slug"],
                "focal_note": (body.get("focal_note") or "").strip(),
                "entries": clean,
                "reviewed_at": datetime.now().isoformat(timespec="seconds"),
            }
            days[day] = rec
            write_log(days)
            rebuild_db_from_log()
            return self._send(200, {"ok": True, "day": day, "week": week,
                                    "focal": rec["focal"]})
        return self._send(404, {"error": "not found"})


def main():
    init_db()
    rebuild_db_from_log()  # keep sqlite in sync with the truth on every boot
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Virtues dashboard running at {url}")
    print("Press Ctrl+C to stop.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
