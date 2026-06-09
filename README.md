
# Virtue Tracker

A daily moral-inventory web app modeled on Benjamin Franklin's method of the
thirteen virtues — adapted here to 23 (Franklin's 13 plus 10 custom). One focal
virtue per week on a 23-week cycle. Each day you mark a "black dot" against any
virtue you failed, and leave a note on what went wrong — or what went right.

Zero dependencies. It's pure Python standard library plus a charting script
loaded from a CDN. No `pip install`, no accounts, no server in the cloud. Your
data is a plain text file on your own machine.

## Run it

```bash
python3 app/server.py
```

It opens `http://localhost:8765` in your browser.

- **Review tab** — the week's focal virtue sits up top with its precept, then all
  23 virtues. Hover the `?` on any virtue to read its precept. Tick **fault** to
  log a black dot. Every virtue has a note field — record a fault's cause or a win
  worth keeping. The date picker reviews any day; a review opened before 4am
  defaults to the day that just ended.
  <img width="1054" height="739" alt="Screenshot 2026-06-09 at 2 02 16 PM" src="https://github.com/user-attachments/assets/9670fee2-608d-4648-b36b-063257983c5d" />

- **Charts tab** — a weekly Franklin grid (with prev/next navigation), daily faults
  over time, faults by virtue, pass-over-pass (Franklin's claim that faults
  diminish each cycle), and focal-week lift.
<img width="1054" height="739" alt="Screenshot 2026-06-09 at 2 03 17 PM" src="https://github.com/user-attachments/assets/aaf45658-e0d5-49ad-8f4e-04ae7977ff53" />

## How it stores data

- **`log.jsonl`** — the source of truth. One JSON line per reviewed day, plain text
  and diffable. Everything else is rebuilt from it. **Gitignored** — your entries
  never get committed.
- **`virtues.db`** — a SQLite query index, rebuilt from the log on every launch.
  Disposable and gitignored. Rebuild it manually anytime with
  `python3 app/rebuild.py`.
- **`config.json`** — the 23 virtues: name, tier, cycle order, precept, the "dot"
  test (when to mark a fault), and a "bite" note for the pride-prone virtues. Edit
  this to make the system your own.

The app ships with no entries. Your first saved review becomes day 1 of the cycle
(week 1 focal = Temperance), advancing one virtue every 7 days.

## The coaching skill (optional)

`.claude/skills/virtue-review/` is a [Claude Code](https://claude.com/claude-code)
skill that reads your log and writes a coaching report — where you're failing,
improving, and stalling, with patterns mined from your notes. It is read-only; it
never edits your data. Its "lens" reads the data through your named primary struggle
and watches the virtues your `config.json` marks with a `bite` (the way a virtue can
curdle into its opposite) — edit the lens to fit you. You don't need it to use the
app; the web app stands alone.

## Make it yours

The 23 virtues and their precepts in `config.json` are one person's set. Franklin
ran 13; you might run 10 or 16. Change the names, rewrite the precepts so each one
passes the "at 10pm, can I cleanly say I failed it today?" test, and reorder them —
the cycle and charts follow whatever you put there.

## Credit

The method is Benjamin Franklin's, from Part Two of his *Autobiography*. This is an
adaptation, not his original list.

Built by Nikos.

## License

MIT — see [LICENSE](LICENSE).
