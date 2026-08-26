# ContentForge — Claude Code Context

**Read CLAUDE-CODE-BRIEF.md for the full UI/UX design brief.**

## Quick start
```
cd /home/aditya/workspace/contentforge
../marketing-agent/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
./scripts/seed_demo.py          # reset the dashboard to a pitch-ready state
```

## What this project is
Multi-tenant SEO/AEO/GEO content generation engine (SaaS). Brands sign up, configure their profile, submit a topic, and the platform generates blog posts, LinkedIn carousels, email newsletters grounded in the brand's voice and compliance rules.

## Tech stack
- FastAPI + Jinja2 + HTMX + SQLite (SQLAlchemy)
- Plain CSS, mobile-first (dark theme, CSS variables in `static/style.css`)
- htmx is vendored to `static/htmx.min.js` — the demo must work with no network
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

## Login
`admin@ais-tech.com` / `admin123`

## Important constraints
- Jinja2 server-rendered, HTMX for interactivity, no React/Vue
- Template render pattern: `render("template.html", request, user={...}, brand=brand, ...)`
- `.env` holds real API keys and is gitignored — keep it that way
