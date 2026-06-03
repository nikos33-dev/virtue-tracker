---
name: virtue-review
description: Use to coach Nikos on his Franklin virtue practice. Reads the virtues database (the daily black-dot log of his 23-virtue cycle), computes where he's failing, improving, and stalling, mines his "what went wrong" notes for patterns, watches the stealth-pride trap, and writes a timestamped advice report. Trigger on "virtue review", "how's my virtue practice", "coach my virtues", "review my virtues", or weekly as a Sunday ritual. Reads only; writes a report to reports/.
allowed-tools: Bash, Read, Write   # Read-only on the virtue data; only writes under reports/. Pre-approved so the run doesn't stall.
bike-method-phase: 1  # Phase 1 — Training wheels. Run manually.
---

## What this skill does

Reads Nikos's virtue-practice database and gives him advice **customized to his actual progress** — not generic habit-tracker platitudes. It is the coaching half of the virtues system; the dashboard (`app/server.py`) is the input half. Output is a timestamped markdown report in `reports/`, plus a short spoken summary.

The system: Franklin's method adapted to 23 virtues (his 13 + Nikos's 10), one focal virtue per week on a 23-week cycle. Each day Nikos marks a "black dot" (fault) against any virtue he failed, with a "what went wrong" note. Truth lives in `log.jsonl`; the queryable index is `virtues.db`. Full design in `README.md`.

**Autonomy: L2 — Drafted.** This skill READS the virtue data and WRITES a coaching report. It never edits the log, never changes a fault, never alters config. Nikos reads the report and decides. Stay inside this posture.

## The lens — this is what makes the advice his, not generic

Nikos's named primary struggle is **pride** (and, downstream of it, self-reliance / forgetting God when things go well). Read the data through that lens:

- **Stealth-pride watch.** Rigor, Steelmanning, and Humility each carry a "bite" in `config.json` — the way the virtue can curdle into superiority. Rigor: "did I verify to be right, or to be seen as the one who's right?" Steelmanning: "to understand, or to perform a superior takedown?" Humility: Franklin never beat it, only its appearance. If these three show **few faults**, do not congratulate. Ask in the report whether low fault counts mean mastery or mean he's grading the performance of the virtue, not the virtue. This is the single most important read.
- **The pride-axis virtues** — Gratitude, Receptivity, Prayerfulness, Humility — are the real war (per the design conversation). Weight them. Improvement here matters more than improvement in Cleanliness.
- **Honest proportion.** Match language to the real size of things. A good week is a good week, not a transformation. Don't inflate.

## Execution

### Step 1 — Refresh the index (deterministic)

```bash
python3 "app/rebuild.py"
```

If `log.jsonl` is missing or empty, there's nothing to coach yet — tell Nikos to run a few daily reviews first (start the dashboard with `python3 "app/server.py"`) and stop.

### Step 2 — Extract the aggregates (deterministic)

Run this to dump everything the analysis needs as one JSON blob:

```bash
python3 - <<'PY'
import json, sys, os
sys.path.insert(0, "app")
import server
from datetime import date, timedelta
days = server.read_log()
if not days:
    print(json.dumps({"empty": True})); raise SystemExit
start = server.cycle_start(days)
ch = server.chart_payload()

# streak / missed days since first log
first = date.fromisoformat(min(days)); today = date.today()
span = [(first + timedelta(d)).isoformat() for d in range((today-first).days + 1)]
missed = [d for d in span if d not in days]

# recent notes, newest first, with virtue + date. Notes attach to a virtue
# independent of the fault flag — fault notes are "what went wrong", non-fault
# notes are wins / observations Nikos wants on record for coaching.
notes = []
for d in sorted(days, reverse=True):
    for slug, e in days[d].get("entries", {}).items():
        nt = (e.get("note") or "").strip()
        if nt:
            notes.append({"day": d, "slug": slug, "fault": bool(e.get("fault")), "note": nt})
focal_notes = [{"day": d, "focal": days[d].get("focal"), "note": days[d].get("focal_note","").strip()}
               for d in sorted(days, reverse=True) if days[d].get("focal_note","").strip()]

# faults by tier
tier = {}
for v in ch["per_virtue"]:
    vt = next(x["tier"] for x in server.VIRTUES if x["slug"]==v["slug"])
    tier.setdefault(vt, 0); tier[vt] += v["faults"]

out = {
  "cycle_start": start.isoformat(), "today": today.isoformat(),
  "reviewed_days": ch["reviewed_count"], "missed_days": missed,
  "current_week": server.week_for(today, start),
  "current_focal": server.focal_for(server.week_for(today, start))["slug"],
  "per_virtue": ch["per_virtue"], "by_tier": tier,
  "daily_totals": ch["daily_totals"], "max_pass": ch["max_pass"],
  "passes": ch["passes"], "focal_lift": [f for f in ch["focal_lift"] if f["focal_days"]>0],
  "notes": notes[:40], "focal_notes": focal_notes[:15],
  "pride_axis": ["gratitude","receptivity","prayerfulness","humility"],
  "stealth_pride": ["rigor","steelmanning","humility"],
}
print(json.dumps(out, ensure_ascii=False, indent=2))
PY
```

### Step 3 — Analyze (AI)

Read the JSON and reason. Don't just restate numbers — interpret them through the lens above. Cover:

1. **Adherence first.** How many days reviewed vs. missed? A practice with holes can't be coached on content — if adherence is poor, that's the headline and the only advice that matters until it's fixed.
2. **Where the faults cluster** — worst virtues and worst tier. Is the failure in the substrate (body/order) or the relational/spiritual core? Substrate failures undermine everything above them (the dependency chain).
3. **Trajectory** — is the daily-faults line trending down? Use `daily_totals`. With `max_pass >= 1`, compare passes per virtue (Franklin's thesis: faults should diminish each pass).
4. **Does the focal week work for him?** Use `focal_lift`. If fault rate while focal is *not* lower than the rest of the time, the spotlight isn't landing — say so, and suggest why (precept too vague? virtue not actually trackable for him?).
5. **Theme-mine the notes.** Read `notes` (each tagged `fault: true/false`) and `focal_notes`. Mine **both** kinds: fault notes for recurring failure patterns ("skipped gym, mood" three times = mood is the lever, not discipline), and non-fault notes for **wins and what's working** — these are the positive results Nikos logs on purpose for his advisor. Reflect the wins back, not just the faults; a review that only names failures is half a review. Name the pattern he can't see from inside it, in either direction.
6. **The stealth-pride read** (see lens). Apply it explicitly to `stealth_pride` virtues.
7. **One thing to change this week.** Tied to the current focal virtue if possible. Concrete, not "try harder."

### Step 4 — Write the report (deterministic)

Write to `reports/virtue-review-{YYYY-MM-DD-HH-MM-SS}.md`. Suggested shape:

```markdown
# Virtue review — {date}
_Week {N} · pass {P} · focal: {Virtue} · {reviewed} days logged, {missed} missed since {start}_

## The headline
{One paragraph: the single most important thing the data says right now.}

## Where the work is
- {worst virtues / tier, with counts}

## Trajectory
- {trend down/flat/up; pass-over-pass if available; focal-week effectiveness}

## What's working
- {wins and positive patterns mined from the non-fault notes}

## Patterns in your notes
- {recurring failure themes mined from the fault notes}

## The pride read
{The stealth-pride analysis — honest, not flattering.}

## This week, change one thing
{One concrete adjustment, tied to the focal virtue.}
```

### Step 5 — Close

Give Nikos a 3-line spoken summary: the headline, the one pattern worth seeing, and the one change for this week. Then stop.

## Bike Method

Phase 1 — Training wheels. Run it manually (weekly is a good cadence — Sunday). Advance phases only by explicit edit to this frontmatter. Phase 3 would schedule it; not yet.

## Out of scope

- Editing the log, faults, or config (read-only by design)
- Generating images or charts (the dashboard owns charts; this skill reasons over the same data in prose)
