# ContentForge · Claude Code UI/UX Brief

> **For:** Claude Code  
> **Task:** Redesign and rebuild all frontend pages for ContentForge  
> **Starting point:** `/home/aditya/workspace/contentforge/`  
> **Read this first:** `/home/aditya/workspace/contentforge/PLAN.md` — full architecture doc

---

## 1. WHAT CONTENTFORGE IS

ContentForge is a **multi-tenant SEO/AEO/GEO content generation engine** — a SaaS platform where brands (companies) sign up, configure their brand profile (voice, products, compliance rules), submit a topic, and the platform auto-generates an entire content ecosystem — blog posts, LinkedIn carousels, email newsletters, and more — all grounded in the brand's unique facts, voice, and compliance constraints.

**Think:** Jasper.ai meets industry-specific compliance guardrails. A B2B SaaS content factory.

**First client:** AIS Technolabs — an iGaming/casino software B2B company (Ahmedabad, India). 16+ years, 600+ clients in 36 countries. Their content topics: casino platform tech, sportsbook software, gaming licenses, player retention, blockchain gaming.

---

## 2. TECH STACK (what you're working with)

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11 / FastAPI |
| **Database** | SQLite (via SQLAlchemy 2.0 ORM) |
| **Templating** | Jinja2 (server-rendered, NOT a SPA) |
| **Interactivity** | HTMX (no React/Vue — use HTMX for AJAX, inline edits, polling) |
| **CSS** | Plain CSS (no Tailwind, no framework — but you CAN add Tailwind CDN if you want) |
| **LLM** | OpenAI GPT-4o (6-pass pipeline) |
| **Research** | Serper.dev API |

**Template rendering pattern (IMPORTANT):**
```python
# app/routes/web.py — how templates are rendered
def render(name: str, request: Request, **context) -> HTMLResponse:
    template = template_env.get_template(name)
    html = template.render(request=request, **context)
    return HTMLResponse(html)

# Route example:
@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.slug == "ais-technolabs").first()
    recent = db.query(ContentRequest).order_by(ContentRequest.created_at.desc()).limit(10).all()
    return render("dashboard.html", request, user={"full_name": "AIS Admin", "role": "admin"}, brand=brand, recent_requests=recent)
```

**Base template** exists at `app/templates/base.html` — extend it with `{% extends "base.html" %}` and override `{% block title %}` and `{% block content %}`.

**Current CSS** is at `static/style.css` — dark theme CSS variables already set up. You can scrap it entirely and rebuild, or extend it.

---

## 3. EXISTING ROUTES (what pages need templates)

These are all defined in `app/routes/web.py`. Each route passes data from DB to template. You build the HTML.

| Route | Template | Data passed | Purpose |
|---|---|---|---|
| `GET /login` | `login.html` | `user: None` | Login form |
| `POST /login` | redirects to `/dashboard` | `email, password` (Form) | Auth — on failure, re-render with `error` |
| `GET /dashboard` | `dashboard.html` | `user: {full_name, role}`, `brand: Brand ORM object`, `recent_requests: [ContentRequest]` | Main hub after login |
| `GET /content/new` | `content_new.html` | `user`, `brand` | Content request form — topic, keywords, format selection |
| `GET /content/{request_id}` | `content_view.html` | `user`, `brand`, `request: ContentRequest`, `items: [GeneratedContent]` | View generated content (NOT BUILT YET) |
| `GET /settings` | `settings.html` | `user`, `brand`, `saved: None` | Brand profile editor |
| `POST /settings` | `settings.html` | `user`, `brand`, `saved: True`, +14 form fields | Save brand settings |
| `GET /calendar` | `calendar.html` | `user`, `entries: []` | Content calendar (placeholder) |

---

## 4. DATA MODELS (what you can reference in templates)

### Brand (the multi-tenant core)
```python
brand.id               # int
brand.name             # "AIS Technolabs"
brand.slug             # "ais-technolabs"
brand.website          # "https://www.aistechnolabs.com/"
brand.niche            # "iGaming & Casino Software (B2B)"
brand.brand_voice      # long text — LLM prompt for tone
brand.brand_facts      # long text — product catalog, stats, USPs
brand.approved_claims  # "ISO 27001:2013, 16+ years, 600+ clients..."
brand.banned_terms     # "guaranteed revenue, guaranteed profit..."
brand.compliance_rules # numbered list of rules
brand.author_bio       # "AIS Technolabs is an ISO-certified..."
brand.default_cta      # "Get a free consultation → URL"
brand.default_language # "English"
brand.visual_style     # "Professional, tech-forward B2B imagery..."
brand.brand_colors     # "#0A1628 (dark navy), #E87722 (orange)..."
brand.n8n_webhook_url  # "https://n8n-.../webhook/ais-technolabs-blog"
```

### ContentRequest (one per generation run)
```python
cr.request_id          # "a3f5c91b" — unique short UUID
cr.primary_topic       # "how to choose white label casino software"
cr.products_to_feature # "White-Label Casino Platform, Crypto Casino"
cr.seed_keywords       # "casino software, iGaming platform..."
cr.word_count          # 1500
cr.kw_count            # 10
cr.formats             # '["blog","linkedin_carousel","email_newsletter"]' — JSON string
cr.publish_targets     # JSON string or None
cr.status              # "pending" | "researching" | "generating" | "validating" | "done" | "failed"
cr.created_at          # datetime (use .strftime('%b %d, %Y %H:%M'))
cr.completed_at        # datetime or None
```

### GeneratedContent (one per format per request)
```python
gc.id                  # int
gc.request_id          # FK → ContentRequest
gc.format              # "blog" | "linkedin_carousel" | "email_newsletter"
gc.title               # "How to Choose White Label Casino Software..."
gc.meta_title          # 50-60 chars SEO title
gc.meta_description    # 150-160 chars
gc.slug                # "how-to-choose-white-label-casino-software"
gc.body_html           # full HTML content
gc.body_markdown       # markdown version (for social/email)
gc.faq_json            # JSON string: FAQPage JSON-LD
gc.schema_json         # JSON string: BlogPosting + FAQPage schemas
gc.status              # "draft" | "needs_fix" | "approved" | "published"
gc.flags               # "banned:guaranteed revenue; compliance:guaranteed\s+revenue"
gc.image_url           # URL or None
gc.keywords            # JSON string: ["kw1", "kw2", ...]
gc.created_at          # datetime
gc.published_at        # datetime or None
```

---

## 5. PAGES TO BUILD — FULL SPECS

### 5.1 Login (`login.html`)
- **Extends:** base.html (no nav — nav only shows when `user` is set)
- **Layout:** Centered card, dark theme, minimal
- **Fields:** Email + Password + Submit
- **States:** Error message if auth fails (`error` variable)
- **Credential hint:** Show "admin@ais-tech.com" as placeholder
- **Branding:** "ContentForge" with the ⚡ emoji or a subtle icon

### 5.2 Dashboard (`dashboard.html`) — MAIN PAGE
- **Extends:** base.html
- **Layout sections:**
  1. **Hero header:** Brand name (big), niche (subtitle), "New Content" CTA button
  2. **Stats row (3 cards):** Total Content Generated, Published, Formats Used — pull from DB queries (the route gets `recent_requests` — you can count statuses)
  3. **Recent Content list:** Cards showing topic, date, status badge, format icons — most recent first
  4. **Empty state:** If no content yet, show a welcoming CTA card: "Generate your first piece of content"
- **Data available:** `brand` (ORM object), `recent_requests` (list of ContentRequest ORM objects)
- **HTMX:** Consider polling for status updates on in-progress items

### 5.3 Content Request Form (`content_new.html`)
- **Extends:** base.html
- **Layout:** Single-column form, max-width 700px
- **Sections:**
  1. **Topic (required):** text input with prompt placeholder
  2. **Products to feature:** textarea (2 rows)
  3. **Seed Keywords:** text input, comma-separated
  4. **Word Count + Keyword Count:** side-by-side dropdowns
  5. **Content Formats:** Checkbox group — Blog (checked), LinkedIn Carousel, Email Newsletter — visual toggles, not plain checkboxes
  6. **Internal Links:** textarea for URLs
  7. **Notification Email:** optional
  8. **Submit:** Full-width primary CTA: "⚡ Generate Content" — on submit, show loading state, then redirect to `/content/{request_id}`
- **Data available:** `brand` (ORM object)
- **POST target:** The form should POST to `/content/new` (needs a route added) which creates the ContentRequest, fires the pipeline, and redirects to the view page.

### 5.4 Content View (`content_view.html`) — NEEDS BUILDING
- **Extends:** base.html
- **Layout:** 
  1. **Header:** Title, date, status badge, format badges
  2. **Tab bar:** One tab per generated format (Blog | LinkedIn | Email) — HTMX tab switching
  3. **Content preview:** The generated HTML rendered inline. Blog shows full article. LinkedIn shows slide cards. Email shows preview.
  4. **SEO metadata card:** meta_title, meta_description, slug, keywords, competitor data
  5. **FAQ section:** Rendered from faq_json
  6. **Schema preview:** Collapsible code block showing JSON-LD
  7. **Validation flags:** If status is NEEDS_FIX, show flagged issues in red cards
  8. **Actions row:** Approve → enqueue for publish, Regenerate, Download, Copy
- **Data available:** `request` (ContentRequest ORM), `items` (list of GeneratedContent ORM objects)

### 5.5 Settings (`settings.html`) — EXISTING, NEEDS POLISH
- **Extends:** base.html
- **Current state:** All fields are plain textareas. Works but ugly.
- **Improve:** 
  - Group fields into collapsible sections: "Brand Identity", "Content Guidelines", "Compliance Rules", "n8n Integration"
  - Use accordion/collapse pattern (HTMX or pure CSS)
  - Character counters on textareas
  - The "n8n Webhook URL" section should have a connection status indicator
  - Save button should show success toast
  - Add a "Test Connection" button for the n8n URL

### 5.6 Calendar (`calendar.html`) — PLACEHOLDER
- **Extends:** base.html
- **Current state:** Empty placeholder with "Phase 6" message
- **Improve:** Make it a proper placeholder with a visual calendar grid, even if empty. Show "Coming soon — auto-generate a 30-day content plan" with a preview of what it'll look like.

---

## 6. DESIGN DIRECTION

### Visual Identity
- **Product name:** ContentForge — a forge/factory metaphor. Think: crafting, refinement, raw input → polished output.
- **Color palette:** Dark navy (#0A1628) background, orange (#E87722) accent, tech blue (#1E90FF) for interactive elements, warm cream (#F5F0E8) for content cards
- **Typography:** Inter or system fonts. Clean, geometric. Headings should feel professional, body text readable at 16px.

### Mood Board Keywords
- Professional B2B SaaS
- Confident, not flashy
- Dark mode by default (it IS the theme, not a toggle)
- Clean card-based layouts
- Subtle gradients, soft shadows, generous whitespace
- "Apple meets Linear" — minimal but polished

### Component Patterns to Use
- **Cards:** Rounded corners (8-12px), subtle border, hover elevation
- **Buttons:** Rounded, clear hierarchy (primary filled, secondary outlined, ghost)
- **Badges:** Pill-shaped, color-coded by status
- **Tabs:** Underline style, smooth transitions
- **Modals/Toasts:** For confirmations, success messages
- **Loading states:** Skeleton screens or pulsing placeholders for content being generated

### HTMX Patterns
- **Polling:** `hx-get="/api/v1/status/{{ request_id }}" hx-trigger="every 5s"` for live status updates
- **Tab switching:** `hx-get="/content/{{ request_id }}/tab/blog" hx-target="#content-panel"`
- **Inline edit:** `hx-put="/settings/field/name" hx-trigger="blur"` for editable fields
- **Lazy load:** `hx-get="/content/{{ request_id }}/preview" hx-trigger="load"`

---

## 7. WHAT EXISTS NOW (baseline you're replacing)

### Current file structure:
```
templates/
├── base.html          # Nav + layout shell (keep, improve)
├── login.html         # Basic — needs design love
├── dashboard.html     # Basic cards — needs full redesign
├── content_new.html   # Plain form — needs visual overhaul
├── settings.html      # Plain textareas — needs sections/accordions
├── calendar.html      # Empty placeholder
└── content_view.html  # DOES NOT EXIST — build from scratch

static/
└── style.css          # CSS variables + basic utility classes — replace entirely
```

### What to KEEP:
- The `base.html` extends pattern (`{% extends "base.html" %}`)
- The `render()` function in routes (don't change routes, just build templates)
- The route data contracts (what gets passed to each template)

### What to CHANGE:
- ALL CSS — scrap `style.css` and rebuild
- ALL templates — rebuild each from scratch with proper design
- The nav in `base.html` — make it more polished
- Add HTMX interactivity wherever it improves UX

---

## 8. AIS TECHNOLABS BRAND IDENTITY (what the dashboard shows)

This is the first client. The seeded data has:
- **Logo/Name:** AIS Technolabs (no logo file — just text styling)
- **Colors for their content:** #0A1628 (navy), #E87722 (orange), #1E90FF (blue)
- **Niche:** iGaming & Casino Software (B2B)
- **Products:** White-label casino, sportsbook, poker platforms, game dev, IT staffing
- **Stats:** 16+ years, 3,900+ projects, 600+ clients, 95% retention

The dashboard should feel like it belongs to THEM — not generic. Show their name prominently.

---

## 9. WHAT TO DO

1. **Read PLAN.md** — full architecture context
2. **Read app/routes/web.py** — understand what data each route passes
3. **Read app/models.py** — understand the ORM objects available in templates
4. **Rebuild ALL templates** — login, dashboard, content_new, content_view, settings, calendar
5. **Rewrite style.css** — complete visual system
6. **Start the app** to test: `./run.sh` or `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

### Priority order:
1. `base.html` + `style.css` (foundation)
2. `login.html` (entry point)
3. `dashboard.html` (main hub)
4. `content_new.html` (core workflow)
5. `content_view.html` (results display) — NEEDS ROUTE UPDATES TOO
6. `settings.html` (config)
7. `calendar.html` (placeholder polish)

---

## 10. IMPORTANT CONSTRAINTS

- **Don't change Python code** unless adding new routes for content_view or HTMX endpoints. The template rendering pattern stays.
- **Jinja2, not React.** Server-rendered HTML.
- **HTMX for interactivity** — no fetch/axios in JS. Use HTMX attributes.
- **SQLite** — no async DB needed for templates (routes are sync).
- **The app is at `/home/aditya/workspace/contentforge/`** — templates in `app/templates/`, CSS in `static/`.
- **Run with:** `cd /home/aditya/workspace/contentforge && ../marketing-agent/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- **Credentials for login:** `admin@ais-tech.com` / `admin123`