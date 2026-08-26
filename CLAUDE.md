# ContentForge — Claude Code Context

**Read CLAUDE-CODE-BRIEF.md for the full UI/UX design brief.**

## Quick start
```
cd /home/aditya/workspace/contentforge
../marketing-agent/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## What this project is
Multi-tenant SEO/AEO/GEO content generation engine (SaaS). Brands sign up, configure their profile, submit a topic, and the platform generates blog posts, LinkedIn carousels, email newsletters grounded in the brand's voice and compliance rules.

## Tech stack
- FastAPI + Jinja2 + HTMX + SQLite (SQLAlchemy)
- Plain CSS (dark theme, CSS variables in style.css)
- OpenAI GPT-4o for generation (engine in app/engine/)
- Serper.dev for keyword research

## What needs building
All frontend templates need a full design overhaul. See CLAUDE-CODE-BRIEF.md §5 for page-by-page specs.

## Key files
- `CLAUDE-CODE-BRIEF.md` — complete design brief
- `PLAN.md` — full architecture
- `app/routes/web.py` — routes + data contracts
- `app/models.py` — ORM models (Brand, ContentRequest, GeneratedContent, etc.)
- `app/templates/` — Jinja2 templates (6 to rebuild/create)
- `static/style.css` — current CSS (replace entirely)
- `run.sh` — dev server launcher

## Login
`admin@ais-tech.com` / `admin123`

## Important constraints
- Don't change Python routes unless adding new ones for content_view or HTMX endpoints
- Jinja2 server-rendered, HTMX for interactivity, no React/Vue
- Template render pattern: `render("template.html", request, user={...}, brand=brand, ...)`