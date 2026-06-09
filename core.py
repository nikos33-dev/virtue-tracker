#!/usr/bin/env python3
"""Virtue Tracker domain logic — storage, cycle math, analytics. Stdlib only.

No HTTP here — just functions over the JSONL truth file and the sqlite query index.
Both the web server (app/server.py) and the coaching skill import this one module.

- Truth of record: log.jsonl   (append/upsert, one line per reviewed day, plain text)
- Query index:     virtues.db   (sqlite, rebuilt from the log, git-ignored)
"""
import json
import os
import sqlite3
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))   # virtues/
CONFIG_PATH = os.path.join(HERE, "config.json")
LOG_PATH = os.path.join(HERE, "log.jsonl")
DB_PATH = os.path.join(HERE, "virtues.db")
INDEX_HTML = os.path.join(HERE, "app", "index.html")

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
    daily_totals = []
    for d in reviewed:
        faults = sum(1 for e in days[d].get("entries", {}).values() if e.get("fault"))
        daily_totals.append({"day": d, "faults": faults})

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

    passes = {}
    for d in reviewed:
        wk = week_for(date.fromisoformat(d), start)
        p = (wk - 1) // N
        for slug, e in days[d].get("entries", {}).items():
            if e.get("fault"):
                passes.setdefault(slug, {}).setdefault(p, 0)
                passes[slug][p] += 1
    max_pass = max((p for s in passes.values() for p in s), default=-1)

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
                row.append(None)
            else:
                e = rec.get("entries", {}).get(v["slug"], {})
                row.append({
                    "fault": bool(e.get("fault")),
                    "note": (e.get("note") or "").strip(),
                })
        matrix.append({"slug": v["slug"], "name": v["name"], "cells": row})
    return {
        "week": week, "focal": focal_for(week)["slug"],
        "cols": cols, "matrix": matrix,
    }

# --------------------------------------------------------------- request glue

def config_payload(day=None):
    day = day or suggested_day()
    days = read_log()
    start = cycle_start(days)
    week = week_for(date.fromisoformat(day), start)
    return {
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
    }


def day_payload(day=None):
    day = day or suggested_day()
    return read_log().get(day, {"day": day, "entries": {}})


def save_day(body):
    """Validate + persist one day's review. Returns (status, payload)."""
    day = body.get("day")
    if not day:
        return 400, {"error": "missing day"}
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return 400, {"error": "bad date"}

    clean = {}
    for slug in SLUGS:
        e = body.get("entries", {}).get(slug, {})
        clean[slug] = {"fault": bool(e.get("fault")), "note": (e.get("note") or "").strip()}

    days = read_log()
    start = cycle_start({**days, day: True})
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
    return 200, {"ok": True, "day": day, "week": week, "focal": rec["focal"]}
