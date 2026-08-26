# Session kickoff — ContentForge (AIS Technolabs pitch dashboard)

Paste the block below into a new Claude session in VS Code, then add what you want
done underneath it. `CLAUDE.md` is picked up automatically and carries the
architecture; this brief carries the *intent* — why the project exists and what
"good" means here.

---

```
You're picking up ContentForge, a pitch demo I'm showing to a client called AIS
Technolabs. Read CLAUDE.md first — it has the architecture, the two run modes, and
the template data contracts.

WHAT IT IS
A multi-tenant SEO/AEO/GEO content engine: pick a topic, and it generates a blog
post, a LinkedIn carousel and an email newsletter, all grounded in the brand's
voice, approved claims and compliance rules. FastAPI + Jinja2 + HTMX + SQLite,
Python 3.14, plain mobile-first CSS. No React, no build step.

WHAT IT'S FOR
Winning the client, not shipping a product. I demo it on my phone, in a room, on
whatever network is there. So:
  - Polish and reliability beat feature depth. A stalled screen loses the room.
  - Every run can be a seeded demo run (~11s, no network) with a live n8n toggle
    beside it. Never make the demo path depend on a third-party API.
  - Mobile is the primary target, desktop is secondary.
  - It should look like a product someone already paid for.

WHERE IT STANDS
Working end to end: login, dashboard, new-content form, the live run panel, and the
content viewer with format tabs, FAQ block, SEO metadata counters, keyword pills and
JSON-LD. The n8n webhook is wired both ways and its failure modes are handled.
Unfinished: the in-process GPT-4o engine in app/engine/ isn't used by the dashboard,
the calendar is read-only, and there are no tests. Nothing is pushed to GitHub yet.

HOW I WANT YOU TO WORK
  - Run it and look at the result before telling me something works:
    .\run.ps1   then http://localhost:8000  (admin@ais-tech.com / admin123)
  - Reset the demo data with `.\venv\Scripts\python.exe scripts\seed_demo.py`
    rather than hand-editing the database.
  - Match the existing code and CSS — same naming, same comment density, no new
    dependencies or frameworks unless I ask.
  - Never commit .env; it holds real OpenAI and Serper keys.
  - If a change touches a template's data contract, update the route in the same
    pass. That mismatch has already broken this app once.
  - Automations stay multi-tenant and brand-agnostic — never cloned per client.

Start by telling me what you see, then wait for my task.
```

---

## Handy follow-ups

Drop one of these under the block above depending on the session:

- **Polish pass** — "Go through the demo flow on a 390px viewport and list anything
  that looks unfinished, misaligned or slow. Fix the top five."
- **New format** — "Add an X output format end to end: the chip on the new-content
  form, the seeded generator in `app/demo.py`, and its panel in `content_view.html`."
- **Wire the calendar** — "Make the calendar writable: add entries, and generate a
  queued topic on its scheduled date."
- **Ship it** — "Set up the GitHub remote at github.com/mendoza0123, check nothing
  secret is staged, and push."
- **Live run** — "Fire a live n8n run end to end and tell me exactly where it fails."

## Facts a session usually needs

| | |
|---|---|
| Login | `admin@ais-tech.com` / `admin123` |
| Run | `.\run.ps1` (add `-Lan` to reach it from a phone) |
| Reset demo data | `.\venv\Scripts\python.exe scripts\seed_demo.py` |
| Brand | AIS Technolabs — iGaming / casino software, B2B |
| n8n webhook | set on the brand, editable in Settings |
| Git | local repo, `main`, no remote yet |
