---
name: virtue-review
description: Use to coach your Franklin virtue practice. Reads the virtue log (the daily black-dot record of your virtue cycle), computes where you're failing, improving, and stalling, mines your "what went wrong" notes for patterns, watches for a virtue curdling into its opposite, and writes a timestamped advice report. Trigger on "virtue review", "how's my virtue practice", "coach my virtues", "review my virtues", or weekly as a Sunday ritual. Reads only; writes a report to reports/.
allowed-tools: Bash, Read, Write
---

## What this skill does

Reads your virtue-practice data and gives you advice **customized to your actual
progress** — not generic habit-tracker platitudes. It is the coaching companion to the
Virtue Tracker web app: the app is where you log each day; this skill reads that log and
writes a timestamped markdown report to `reports/`, plus a short spoken summary.

The system: Franklin's method, adapted to whatever virtues live in `config.json` (the app
ships with a 23-virtue set — Franklin's 13 plus 10 more — but it's yours to edit), one
focal virtue per week on a full cycle. Each day you mark a "black dot" (fault) against any
virtue you failed, with a "what went wrong" note. Truth lives in `log.jsonl`; the
queryable index is `virtues.db`, rebuilt from the log.

**Read-only by design.** This skill READS the data and WRITES a coaching report. It never
edits the log, never changes a fault, never alters config. You read the report and decide.

## The lens — this is what makes the advice yours, not generic

Generic virtue tracking counts dots. Good coaching reads them through the practitioner's
**named primary struggle**. Two techniques do most of the work:

- **The "curdle" watch (stealth virtue).** Some virtues fail not by absence but by turning
  into their own counterfeit — rigor into being-right, humility into performed humility.
  `config.json` marks these with a **`bite`** field (a one-line note on how that virtue
  curdles). For any bite-marked virtue showing **few faults**, do not congratulate: ask in
  the report whether the low count means mastery, or means the practitioner is grading the
  *performance* of the virtue rather than the virtue. This is the single most important
  read. (Step 2 surfaces the bite-marked virtues automatically from the config.)
- **Weight the hard axis.** Improvement in a load-bearing virtue (the relational/spiritual
  or character core) matters more than improvement in, say, Cleanliness. Name the
  practitioner's stated core struggle if it's recorded in their notes, and weight the
  virtues nearest it.
- **Honest proportion.** Match language to the real size of things. A good week is a good
  week, not a transformation. Don't inflate.

> The shipped lens above is a starting point. Edit this section to fit your own struggle
> and your own virtue set.

## Execution

### Step 1 — Refresh the index (deterministic)

```bash
python3 app/rebuild.py
```

If `log.jsonl` is missing or empty, there's nothing to coach yet — tell the user to run a
few daily reviews first (`python3 app/server.py` → http://localhost:8765) and stop.

### Step 2 — Extract the aggregates (deterministic)

Run this from the repo root to dump everything the analysis needs as one JSON blob:

```bash
python3 - <<'PY'
import json, sys
sys.path.insert(0, ".")
import core
from datetime import date, timedelta
days = core.read_log()
if not days:
    print(json.dumps({"empty": True})); raise SystemExit
start = core.cycle_start(days)
ch = core.chart_payload()

# streak / missed days since first log
first = date.fromisoformat(min(days)); today = date.today()
span = [(first + timedelta(d)).isoformat() for d in range((today-first).days + 1)]
missed = [d for d in span if d not in days]

# recent notes, newest first. Notes attach to a virtue independent of the fault flag —
# fault notes are "what went wrong", non-fault notes are wins / observations on record.
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
    vt = next(x["tier"] for x in core.VIRTUES if x["slug"]==v["slug"])
    tier.setdefault(vt, 0); tier[vt] += v["faults"]

# the "curdle" watchlist comes straight from the config: any virtue with a bite
stealth = [v["slug"] for v in core.VIRTUES if (v.get("bite") or "").strip()]

out = {
  "cycle_start": start.isoformat(), "today": today.isoformat(),
  "reviewed_days": ch["reviewed_count"], "missed_days": missed,
  "current_week": core.week_for(today, start),
  "current_focal": core.focal_for(core.week_for(today, start))["slug"],
  "per_virtue": ch["per_virtue"], "by_tier": tier,
  "daily_totals": ch["daily_totals"], "max_pass": ch["max_pass"],
  "passes": ch["passes"], "focal_lift": [f for f in ch["focal_lift"] if f["focal_days"]>0],
  "notes": notes[:40], "focal_notes": focal_notes[:15],
  "stealth_watch": stealth,
}
print(json.dumps(out, ensure_ascii=False, indent=2))
PY
```

### Step 3 — Analyze (AI)

Read the JSON and reason. Don't just restate numbers — interpret them through the lens
above. Cover:

1. **Adherence first.** How many days reviewed vs. missed? A practice with holes can't be
   coached on content — if adherence is poor, that's the headline and the only advice that
   matters until it's fixed.
2. **Where the faults cluster** — worst virtues and worst tier. Is the failure in the
   substrate (body/order) or the relational/character core? Substrate failures undermine
   everything above them in the cycle order.
3. **Trajectory** — is the daily-faults line trending down? Use `daily_totals`. With
   `max_pass >= 1`, compare passes per virtue (Franklin's claim: faults diminish each pass).
4. **Does the focal week work?** Use `focal_lift`. If the fault rate while a virtue is focal
   is *not* lower than the rest of the time, the spotlight isn't landing — say so, and
   suggest why (precept too vague? virtue not actually trackable?).
5. **Theme-mine the notes.** Read `notes` (each tagged `fault: true/false`) and
   `focal_notes`. Mine **both**: fault notes for recurring failure patterns ("skipped gym,
   mood" three times = mood is the lever), and non-fault notes for **wins** — reflect those
   back too. A review that only names failures is half a review.
6. **The curdle read** (see lens). Apply it explicitly to the `stealth_watch` virtues.
7. **One thing to change this week.** Tied to the current focal virtue if possible.
   Concrete, not "try harder."

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

## The curdle read
{The stealth-virtue analysis — honest, not flattering.}

## This week, change one thing
{One concrete adjustment, tied to the focal virtue.}
```

### Step 5 — Close

Give a 3-line spoken summary: the headline, the one pattern worth seeing, and the one
change for this week. Then stop.

## Out of scope

- Editing the log, faults, or config (read-only by design)
- Generating images or charts (the app owns charts; this skill reasons over the same data
  in prose)
