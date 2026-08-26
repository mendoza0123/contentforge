# ContentForge — Claude Code Context

**Read `PROMPT.md` first if you are starting a fresh session.**
`CLAUDE-CODE-BRIEF.md` has the full UI/UX design brief.

## The objective
This is a **client pitch demo**, not a product build. It exists to show AIS Technolabs
a working SEO/AEO/GEO content engine on a phone. **Polish and demo reliability beat
feature depth** — a pitch that stalls on a slow API is worse than one that shows less.

Every decision follows from that:
- The dashboard is mobile-first and installable to a home screen.
- htmx is vendored, not on a CDN, so it works with no network.
- Every run can be a seeded demo run, with a live n8n toggle next to it.

## Quick start (Windows)
```powershell
.\run.ps1                  # http://localhost:8000, autoreload
.\run.ps1 -Lan             # also reachable from your phone on the same Wi-Fi
.\run.ps1 -Seed            # reset the demo catalogue first
.\venv\Scripts\python.exe scripts\seed_demo.py          # reset on its own
```
VS Code: F5 runs "ContentForge (uvicorn)". Login `admin@ais-tech.com` / `admin123`.

Reset the demo catalogue before any pitch — it rebuilds five finished runs so the
dashboard opens with real numbers instead of an empty state.

## Where this stands
Working and verified end to end: login guard, dashboard counters, a demo run walking
0→100% into the finished piece with all three format tabs, a simulated n8n callback
including compliance flags, and both live failure paths.

Not done: the in-process GPT-4o engine in `app/engine/` is unused by the dashboard;
the calendar has no way to add entries; there are no automated tests. Nothing has
been pushed to GitHub (github.com/mendoza0123 is the intended remote).

## What this project is
Multi-tenant SEO/AEO/GEO content generation engine (SaaS). Brands configure their
profile, submit a topic, and the platform generates blog posts, LinkedIn carousels
and email newsletters grounded in the brand's voice and compliance rules.

## Tech stack
- FastAPI + Jinja2 + HTMX + SQLite (SQLAlchemy), Python 3.14
- Plain CSS, mobile-first (dark theme, CSS variables in `static/style.css`)
- htmx vendored to `static/htmx.min.js` — the demo must work with no network
- OpenAI GPT-4o for generation (in-process engine in `app/engine/`, unused by the dashboard)
- Serper.dev for keyword research

## The two run modes
`app/demo.py` owns both. Picked per run on the New Content form.

- **demo** — a seeded run walks the pipeline in ~11s on a background thread and writes
  stored content. Works offline; a pitch never stalls on an API.
- **live** — POSTs to `Brand.n8n_webhook_url` and waits for n8n's
  `Publish → Webhook` node to call `POST /api/v1/webhook/n8n-result`, which flips the
  request to `done`. Falls back to demo when no webhook is configured.

Live gotchas, all handled in code:
- n8n routes on `publish_target`, and only its **Webhook** branch calls back — so our
  "Draft only" is sent as `Webhook` (see `demo.PUBLISH_TARGETS`). WordPress and
  Shopify publish at n8n's end and never report back.
- A live run with no callback after 15 minutes is failed by `demo.settle_if_stale`
  rather than spinning forever.
- n8n emits `PENDING_REVIEW` / `NEEDS_FIX`; `api._normalize_status` maps those onto
  the `draft` / `needs_fix` lifecycle the models and templates use.
- `demo.build_payload` matches the webhook's *Normalize Inputs* node field for field
  — note `word_count` goes as a `"1200-1800"` **string**.

## Key files
- `PROMPT.md` — session kickoff brief
- `CLAUDE-CODE-BRIEF.md` — complete design brief
- `PLAN.md` — full architecture
- `app/routes/web.py` — routes, view models, the `from_json` filter
- `app/routes/api.py` — REST + the n8n result receiver
- `app/demo.py` — run dispatch, progress model, n8n payload, seeded output
- `app/models.py` — ORM models (Brand, ContentRequest, GeneratedContent, etc.)
- `scripts/seed_demo.py` — rebuild (or `--wipe`) the demo catalogue
- `n8n/ais-technolabs-blog-engine-webhook.json` — the 23-node workflow

## Template contracts
Routes must pass these or the templates raise `UndefinedError`:
- `dashboard.html` — `stats{total,published,formats,in_progress}`, `engine{mode,label,webhook_url}`
- `content_new.html` — `engine`
- `content_view.html` — `request_obj` (**not** `request`, which is the Starlette Request),
  `items` carrying computed `.faqs` / `.slides` / `.keyword_list`, `progress`
- `_run_status.html` — `request_obj`, `progress{pct,note,mode,steps[{name,state}]}`
- `_recent_list.html` — `recent_requests`, `stats` (it polls only while `stats.in_progress`)

## Important constraints
- Jinja2 server-rendered, HTMX for interactivity, no React/Vue
- Template render pattern: `render("template.html", request, user={...}, brand=brand, ...)`
- Mobile is the primary target: bottom tab bar under 860px, 16px inputs so iOS
  doesn't zoom on focus, safe-area insets
- `.env` holds real OpenAI and Serper keys and is gitignored — keep it that way
- Build automations multi-tenant / brand-agnostic, never cloned per client
