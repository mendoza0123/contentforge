# ContentForge — Multi-Tenant SEO/AEO/GEO Content Engine

> **Status:** Planning Phase  
> **Created:** August 23, 2026  
> **Inspired by:** Dhanwantri · AyurVaani Blog Engine (n8n + GPT-4o)  
> **Target:** Production-ready multi-tenant SaaS content platform

---

## 1. Project Overview

**ContentForge** is a multi-tenant, multi-format content generation engine. It takes a keyword/topic input and produces SEO/AEO/GEO-optimized content across formats — blogs, social carousels, email newsletters, video scripts, and podcast outlines — all grounded in a brand's unique voice, product catalog, and compliance rules.

### What it inherits from Dhanwantri
- **Multi-pass LLM pipeline** — sequential generation passes (outline → draft → SEO audit → FAQ → GEO → metadata) each refining the output
- **SEO/AEO/GEO triple optimization** — every piece optimized for Google, voice snippets, and AI search engines simultaneously
- **Compliance-first** — brand-specific rules enforced by the LLM and post-generation validation
- **Human-in-the-loop** — content lands as drafts for review before publishing

### What's new / "more advanced"
| Capability | Dhanwantri | ContentForge |
|---|---|---|
| Tenancy | Single-brand (Dhanwantri Pharma) | **Multi-tenant** — any brand can onboard |
| Content formats | Blog only | **Multi-format** — blogs, social, email, video, podcast |
| Architecture | n8n-only (no-code) | **Hybrid** — Python/FastAPI core + n8n ops layer |
| Brand config | Hardcoded in form/webhook | **Self-serve brand profiles** with custom voice, guidelines, product catalog |
| Publishing | Shopify, WordPress, Webhook | Shopify, WordPress, Webhook + **Postiz (social) + Mailchimp (email)** |
| Research | Serper + DataForSEO | **Serper only** (free tier, GPT-4o fallback for volume estimates) |
| AEO/GEO scope | Blog FAQ + entity structuring | **Every format** — voice-search snippets for social, email, scripts |
| Image generation | Prompt-only (not called) | **Full integration** — hero images, carousel slides, YouTube thumbnails via Flux/fal.ai |
| Scheduling | Manual trigger only | **Content calendar** — 30-day auto-plan + cron publishing via n8n |
| Analytics | None | **Feedback loop** — GSC + social analytics → auto-adjust future content |

### First client
**AIS Technolabs** — B2B iGaming/casino software company (Ahmedabad, global). Content topics: casino operations, game development, sportsbook platforms, licensing, player retention, blockchain gaming, IT staffing.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      CONTENTFORGE PLATFORM                       │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Brand A  │  │  Brand B  │  │  Brand C  │  │  Brand N  │        │
│  │ (AIS Tech)│  │ (Dhanwantri)│ │ (Future)  │  │ (Future)  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │                │
│  ┌────┴─────────────┴─────────────┴─────────────┴────┐          │
│  │              Web Dashboard (FastAPI + Jinja2 + HTMX) │          │
│  │   • Brand onboarding  • Content request form        │          │
│  │   • Draft review      • Calendar view              │          │
│  │   • Analytics panel   • Publishing controls         │          │
│  └──────────────────────┬─────────────────────────────┘          │
│                         │                                        │
│  ┌──────────────────────┴─────────────────────────────┐          │
│  │              CORE ENGINE (Python/FastAPI)            │          │
│  │                                                      │          │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │          │
│  │  │ Research  │  │Generation│  │Validation│          │          │
│  │  │  Layer   │→ │ Pipeline │→ │  Layer   │          │          │
│  │  │ (Serper) │  │(GPT-4o xN)│  │(compliance│          │          │
│  │  └──────────┘  └──────────┘  │  scan)   │          │          │
│  │                              └──────────┘          │          │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │          │
│  │  │  Image   │  │  Format  │  │ Publish  │          │          │
│  │  │Generation│  │ Adapters │  │  Queue   │          │          │
│  │  │(fal.ai)  │  │(social,  │  │(outbox → │          │          │
│  │  └──────────┘  │ email,..)│  │  n8n)    │          │          │
│  │                └──────────┘  └──────────┘          │          │
│  └──────────────────────┬─────────────────────────────┘          │
│                         │                                        │
│  ┌──────────────────────┴─────────────────────────────┐          │
│  │              DATA LAYER (SQLite → Postgres)          │          │
│  │   Brands • Content • Calendar • Analytics • Queue    │          │
│  └──────────────────────┬─────────────────────────────┘          │
│                         │                                        │
│  ┌──────────────────────┴─────────────────────────────┐          │
│  │              n8n OPERATIONS LAYER                    │          │
│  │                                                      │          │
│  │  • Cron trigger → polls publish queue every 15m      │          │
│  │  • Publishing webhooks → Shopify, WP, Postiz, MC    │          │
│  │  • Analytics ingest → GSC API, social API → webhook  │          │
│  │  • Slack/email notifications → review reminders      │          │
│  └──────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Architecture principles
1. **Python does the thinking, n8n does the doing** — All LLM orchestration, content generation, validation, and business logic lives in the Python/FastAPI app. n8n handles scheduling, HTTP webhooks to external platforms, and notification delivery.
2. **Stateless engine, stateful data** — The core engine is a pure function: `(brand_profile, topic_input) → content_bundle`. All state is in SQLite.
3. **Outbox pattern for publishing** — Content is generated and saved. A publish queue table holds pending items. n8n cron polls the queue, publishes, and marks complete.
4. **Per-brand isolation** — Every query is scoped to `brand_id`. API keys, brand profiles, content history, and analytics are all namespaced.

---

## 3. Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Backend** | Python 3.11+ / FastAPI | Your established stack (marketing-agent, gym-diet-planner) |
| **Database** | SQLite (dev) → PostgreSQL (prod) | Start simple, migrate when needed |
| **ORM** | SQLAlchemy 2.0 | Models + migrations |
| **Frontend** | Jinja2 + HTMX + Tailwind CSS | Server-rendered, no JS framework |
| **LLM** | OpenAI GPT-4o (fixed) | Proven from Dhanwantri. Single provider, reliable. |
| **Research** | Serper.dev API (free tier: 2,500 queries) | Google search + PAA. No DataForSEO paywall. |
| **Images** | Flux via fal.ai (`fal.run/` sync endpoint) | From Dhanwantri roadmap |
| **Publishing** | n8n workflows (HTTP nodes) | Reuse your n8n infra + n8n_api.py tooling |
| **Social** | Postiz (self-hosted) | Dhanwantri roadmap recommendation |
| **Email** | Mailchimp API (campaign creation) | Industry standard |
| **Analytics** | Google Search Console API + social APIs | Feedback loop data |
| **Auth** | Simple JWT (python-jose) + bcrypt | Multi-tenant needs auth |
| **Async** | httpx (for external API calls) | Non-blocking Serper, fal.ai, publishing |

---

## 4. Data Model

### 4.1 Brands
```sql
brands (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,              -- "AIS Technolabs"
    slug            TEXT UNIQUE NOT NULL,       -- "ais-technolabs"
    website         TEXT,                       -- "https://www.aistechnolabs.com/"
    niche           TEXT,                       -- "iGaming / Casino Software"
    brand_voice     TEXT,                       -- brand voice description for LLM
    brand_facts     TEXT,                       -- grounding anchor (products, services, USPs)
    approved_claims TEXT,                       -- claims the brand can make
    banned_terms    TEXT,                       -- comma-separated banned words
    compliance_rules TEXT,                      -- niche-specific rules (AYUSH, iGaming regs, etc.)
    author_bio      TEXT,                       -- default author bio for content
    default_cta     TEXT,                       -- "Get a free demo today"
    target_markets  TEXT,                       -- JSON array of {"country":"US","geo":"gl:us",...}
    default_lang    TEXT DEFAULT 'English',
    openai_api_key  TEXT,                       -- per-brand API key (or use platform default)
    serper_api_key  TEXT,
    created_at      DATETIME,
    updated_at      DATETIME
)
```

### 4.2 Users (platform users, not content audience)
```sql
users (
    id              INTEGER PRIMARY KEY,
    brand_id        INTEGER FK → brands.id,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    full_name       TEXT,
    role            TEXT DEFAULT 'editor',     -- 'admin', 'editor', 'viewer'
    created_at      DATETIME
)
```

### 4.3 Publishing Targets (per brand)
```sql
publishing_targets (
    id              INTEGER PRIMARY KEY,
    brand_id        INTEGER FK → brands.id,
    target_type     TEXT NOT NULL,              -- 'shopify','wordpress','postiz','mailchimp','webhook'
    label           TEXT,                       -- "AIS Blog (WordPress)"
    config_json     TEXT,                       -- {"base_url":"...","token":"...","blog_id":"..."}
    is_active       BOOLEAN DEFAULT 1,
    created_at      DATETIME
)
```

### 4.4 Content Requests
```sql
content_requests (
    id              INTEGER PRIMARY KEY,
    brand_id        INTEGER FK → brands.id,
    request_id      TEXT UNIQUE,                -- UUID for webhook/polling
    primary_topic   TEXT NOT NULL,
    products_to_feature TEXT,
    seed_keywords   TEXT,
    internal_links  TEXT,                       -- JSON array of URLs
    word_count      INTEGER DEFAULT 1500,
    kw_count        INTEGER DEFAULT 10,
    formats         TEXT,                       -- JSON: ["blog","linkedin_carousel","email","youtube_short"]
    publish_targets TEXT,                       -- JSON array of publishing_target IDs
    notify_email    TEXT,
    status          TEXT DEFAULT 'pending',     -- pending|researching|generating|validating|done|failed
    created_at      DATETIME,
    completed_at    DATETIME
)
```

### 4.5 Generated Content
```sql
generated_content (
    id              INTEGER PRIMARY KEY,
    request_id      TEXT FK → content_requests.request_id,
    brand_id        INTEGER FK → brands.id,
    format          TEXT NOT NULL,              -- 'blog','linkedin_carousel','instagram_carousel',
                                               -- 'twitter_thread','email_newsletter',
                                               -- 'youtube_short','youtube_long','podcast_outline'
    title           TEXT,
    meta_title      TEXT,                       -- SEO title (50-60 chars)
    meta_description TEXT,                      -- SEO description (150-160 chars)
    slug            TEXT,
    body_html       TEXT,                       -- main content in HTML
    body_markdown   TEXT,                       -- markdown version for social/email
    faq_json        TEXT,                       -- FAQPage JSON-LD
    schema_json     TEXT,                       -- full schema.org JSON-LD
    image_prompt    TEXT,                       -- Flux prompt
    negative_prompt TEXT,                       -- Flux negative prompt
    image_url       TEXT,                       -- generated image URL (fal.ai result)
    image_alt       TEXT,
    keywords        TEXT,                       -- JSON array of keyword objects
    competitor_data TEXT,                       -- JSON: top 3 organic results
    status          TEXT DEFAULT 'draft',       -- draft|needs_fix|approved|published
    flags           TEXT,                       -- validation flags
    review_notes    TEXT,
    created_at      DATETIME,
    published_at    DATETIME
)
```

### 4.6 Content Calendar
```sql
content_calendar (
    id              INTEGER PRIMARY KEY,
    brand_id        INTEGER FK → brands.id,
    topic           TEXT NOT NULL,
    formats         TEXT,                       -- JSON array
    scheduled_date  DATE NOT NULL,
    request_id      TEXT FK,                    -- populated after generation
    status          TEXT DEFAULT 'planned',     -- planned|generated|published|skipped
    created_at      DATETIME
)
```

### 4.7 Publish Queue (Outbox)
```sql
publish_queue (
    id              INTEGER PRIMARY KEY,
    content_id      INTEGER FK → generated_content.id,
    brand_id        INTEGER FK → brands.id,
    target_id       INTEGER FK → publishing_targets.id,
    target_type     TEXT,
    payload_json    TEXT,                       -- The exact payload for the publishing API
    status          TEXT DEFAULT 'queued',      -- queued|published|failed
    attempt_count   INTEGER DEFAULT 0,
    last_error      TEXT,
    created_at      DATETIME,
    published_at    DATETIME
)
```

### 4.8 Analytics Snapshots
```sql
analytics_snapshots (
    id              INTEGER PRIMARY KEY,
    content_id      INTEGER FK → generated_content.id,
    brand_id        INTEGER FK → brands.id,
    source          TEXT,                       -- 'gsc','linkedin','instagram','mailchimp'
    metric_name     TEXT,                       -- 'clicks','impressions','ctr','position','engagement'
    metric_value    FLOAT,
    snapshot_date   DATE,
    created_at      DATETIME
)
```

---

## 5. Content Generation Pipeline

### 5.1 Pipeline Overview

The generation pipeline is format-aware. Every format shares a **common research phase** followed by **format-specific generation passes**.

```
INPUT: primary_topic + brand_profile
  │
  ├─ PHASE 1: RESEARCH (common to all formats)
  │   ├─ Serper search → top 10 organic + PAA questions
  │   ├─ Keyword extraction → cluster + score
  │   └─ Competitor analysis → top 3 results with snippets
  │
  ├─ PHASE 2: CONTEXT ASSEMBLY (common)
  │   └─ Merge brand profile + research → ground truth bundle
  │
  ├─ PHASE 3: MULTI-FORMAT GENERATION (parallel per format)
  │   │
  │   ├─ FORMAT: blog
  │   │   ├─ Pass 1 · Outline (JSON: hook, intro, sections, keyword_map, faq_slot)
  │   │   ├─ Pass 2 · Draft (HTML, 1200-2500 words, Veratick house structure)
  │   │   ├─ Pass 3 · SEO Audit (keyword density, headings, internal links)
  │   │   ├─ Pass 4 · AEO FAQ (5-7 Q&A + FAQPage JSON-LD)
  │   │   ├─ Pass 5 · GEO Structuring (authority, entities, Why-Trust-Us)
  │   │   └─ Pass 6 · Metadata (title, description, slug, BlogPosting JSON-LD)
  │   │
  │   ├─ FORMAT: linkedin_carousel
  │   │   ├─ Pass 1 · Hook + Narrative Arc (story-driven, data-backed)
  │   │   ├─ Pass 2 · Slide Breakdown (10 slides, visual-first, 30-50 words/slide)
  │   │   ├─ Pass 3 · SEO/AEO (keyword-optimized captions, hashtags, alt-text)
  │   │   └─ Pass 4 · CTA + Engagement (conversation starter, poll idea)
  │   │
  │   ├─ FORMAT: instagram_carousel
  │   │   ├─ Pass 1 · Visual Narrative (10 slides, bold stats + minimal text)
  │   │   ├─ Pass 2 · Slide Content (hook slide → problem → solution → proof → CTA)
  │   │   ├─ Pass 3 · SEO/AEO (caption keywords, hashtag strategy, alt-text)
  │   │   └─ Pass 4 · Visual Brief (color palette, image style for each slide)
  │   │
  │   ├─ FORMAT: twitter_thread
  │   │   ├─ Pass 1 · Hook Tweet (scroll-stopper, curiosity gap)
  │   │   ├─ Pass 2 · Thread Body (7-12 tweets, narrative arc, data points)
  │   │   └─ Pass 3 · Engagement (CTA tweet, quote-tweet prompt, hashtags)
  │   │
  │   ├─ FORMAT: email_newsletter
  │   │   ├─ Pass 1 · Subject Line Variants (3 options, A/B test ready)
  │   │   ├─ Pass 2 · Body (HTML email, preview text, header, sections, CTA)
  │   │   └─ Pass 3 · Personalization + Segmentation hints
  │   │
  │   ├─ FORMAT: youtube_short
  │   │   ├─ Pass 1 · Hook (first 3 seconds, pattern-interrupt)
  │   │   ├─ Pass 2 · Script (60-second pacing, visual cues, B-roll notes)
  │   │   └─ Pass 3 · Title + Description + Tags (SEO-optimized)
  │   │
  │   ├─ FORMAT: youtube_long
  │   │   ├─ Pass 1 · Structure (intro → chapters → conclusion, 8-15 min)
  │   │   ├─ Pass 2 · Full Script (dialogue + visual directions + B-roll)
  │   │   └─ Pass 3 · Thumbnail brief + Title + Description + Tags
  │   │
  │   └─ FORMAT: podcast_outline
  │       ├─ Pass 1 · Episode Structure (intro → segments → outro, 20-40 min)
  │       ├─ Pass 2 · Talking Points (host questions, guest prompts, transitions)
  │       └─ Pass 3 · Show Notes (summary, timestamps, links, SEO description)
  │
  ├─ PHASE 4: VALIDATION (common)
  │   ├─ Compliance scan (banned terms, unverified claims, brand voice check)
  │   ├─ Force-append disclaimer if required
  │   └─ Set status: draft / needs_fix / approved
  │
  ├─ PHASE 5: IMAGE GENERATION (per format, optional)
  │   ├─ Blog → hero image (1200x630)
  │   ├─ LinkedIn carousel → 10 slide images (1080x1080)
  │   ├─ Instagram carousel → 10 slide images (1080x1080 or 1080x1350)
  │   ├─ Email → header image (600x200)
  │   ├─ YouTube Short → 9:16 thumbnail (1080x1920)
  │   ├─ YouTube Long → 16:9 thumbnail (1280x720)
  │   └─ All via Flux (fal.ai sync endpoint)
  │
  └─ PHASE 6: PUBLISH QUEUE
      └─ Enqueue to publish_queue for each selected target + format combo
```

### 5.2 Generation Strategy

**Key decision:** Blog goes through the full 6-pass pipeline (SEO/AEO/GEO heavy). Social/email/video/podcast formats go through 3-4 lighter passes — they inherit the research and brand context from the blog pipeline but optimize for their specific platform.

**Parallel vs sequential:**
- Blog generation is **sequential** (each pass feeds the next) — same as Dhanwantri
- All other formats can run **in parallel** after blog is done (they use blog output as reference)
- Image generation runs **in parallel** across all formats

### 5.3 Brand Voice Injection

Every LLM pass receives the brand profile as part of its system prompt:

```python
BRAND_CONTEXT_TEMPLATE = """
You are writing for {brand_name} ({brand_website}).
Niche: {niche}
Brand Voice: {brand_voice}

KEY BRAND FACTS (quote verbatim, never invent):
{brand_facts}

APPROVED CLAIMS (may use):
{approved_claims}

BANNED TERMS (never use):
{banned_terms}

COMPLIANCE RULES:
{compliance_rules}

AUTHOR BIO:
{author_bio}

DEFAULT CTA:
{default_cta}
"""
```

---

## 6. API Design (FastAPI Routes)

### 6.1 Web Dashboard (Jinja2 + HTMX)

| Method | Path | Description |
|---|---|---|
| GET | `/` | Landing page |
| GET | `/login` | Login form |
| POST | `/login` | Authenticate |
| GET | `/dashboard` | Brand dashboard (content list, calendar, analytics) |
| GET | `/brand/{slug}` | Public brand landing (if multi-brand showcase) |
| GET | `/settings` | Brand profile settings |
| POST | `/settings` | Update brand profile |
| GET | `/content/new` | New content request form |
| POST | `/content/new` | Submit content request → triggers generation |
| GET | `/content/{request_id}` | View generated content bundle |
| GET | `/content/{request_id}/preview/{format}` | Preview specific format output |
| GET | `/content/{request_id}/approve` | Approve → enqueue for publishing |
| GET | `/calendar` | Content calendar view |
| POST | `/calendar/generate` | Auto-generate 30-day calendar |
| GET | `/analytics` | Analytics dashboard |
| GET | `/publishing` | Publishing targets management |
| POST | `/publishing/add` | Add publishing target |
| DELETE | `/publishing/{id}` | Remove publishing target |

### 6.2 REST API (for n8n, webhooks, external triggers)

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/generate` | Webhook: submit content request → returns `request_id` |
| GET | `/api/v1/status/{request_id}` | Poll generation status |
| GET | `/api/v1/content/{request_id}` | Get full content bundle (JSON) |
| GET | `/api/v1/publish/queue` | n8n polls this for pending publish jobs |
| POST | `/api/v1/publish/confirm/{queue_id}` | n8n confirms publish success/failure |
| POST | `/api/v1/analytics/ingest` | n8n sends analytics data from GSC/social |
| GET | `/api/v1/calendar/{brand_id}` | Get upcoming content calendar |
| POST | `/api/v1/brand/onboard` | Programmatic brand onboarding |

---

## 7. n8n Integration Layer

### 7.1 Workflows needed

| Workflow | Trigger | What it does |
|---|---|---|
| **Content Publisher** | Cron (every 15 min) | Polls `/api/v1/publish/queue`, publishes to Shopify/WP/Postiz/MC via HTTP nodes, confirms back |
| **Analytics Collector** | Cron (daily) | Pulls GSC data, social metrics → POST to `/api/v1/analytics/ingest` |
| **Calendar Runner** | Cron (daily) | Checks calendar for today's scheduled content → triggers generation if not done |
| **Review Reminder** | Cron (daily) | Finds content in `draft` > 48h → Slack/email notification |
| **Form Webhook (optional)** | Webhook POST | Alternative trigger: external form → ContentForge API |

### 7.2 n8n credentials needed

- ContentForge API key (JWT bearer token)
- Shopify Admin API token (per brand)
- WordPress REST API token (per brand)
- Postiz API key
- Mailchimp API key
- Google Search Console OAuth
- Slack/Email for notifications

---

## 8. Image Generation (Flux via fal.ai)

### 8.1 Image specs per format

| Format | Dimensions | Aspect Ratio | Style |
|---|---|---|---|
| Blog hero | 1200×630 | 1.91:1 (OG image) | Professional, branded |
| LinkedIn carousel | 1080×1080 | 1:1 | Clean, data-visual, B2B |
| Instagram carousel | 1080×1350 | 4:5 | Bold, visual-first, stat-driven |
| Email header | 600×200 | 3:1 | Subtle, brand-color |
| YouTube Short thumb | 1080×1920 | 9:16 | High-contrast, face/text combo |
| YouTube Long thumb | 1280×720 | 16:9 | Custom thumbnail style |

### 8.2 Flux prompt template (per brand)

```python
FLUX_BRAND_TEMPLATE = """
{brand_name} brand image. {format_context}.
Style: {brand_visual_style}.
Color palette: {brand_colors}.
NO text, NO letters, NO watermarks, NO logos.
Professional, high-resolution, photorealistic.
"""
```

### 8.3 fal.ai integration

```python
import httpx

async def generate_image(prompt: str, negative_prompt: str, 
                         width: int, height: int) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://fal.run/fal-ai/flux/schnell",
            headers={"Authorization": f"Key {FAL_API_KEY}"},
            json={
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "image_size": {"width": width, "height": height},
                "num_inference_steps": 4,  # schnell is fast
            },
            timeout=60.0,
        )
        return resp.json()
```

---

## 9. Advanced Features (Phase 2)

### 9.1 Content Calendar Auto-Generator
- Input: brand profile + niche
- GPT-4o generates a 30-day topic calendar based on: industry trends, seasonal relevance, keyword gaps, content mix (educational, promotional, thought leadership)
- Output: 30 rows in `content_calendar` table
- n8n cron picks up daily → triggers generation

### 9.2 Analytics Feedback Loop
- Daily GSC ingest: clicks, impressions, CTR, avg position per URL
- Social analytics: LinkedIn impressions/engagement, Instagram likes/shares, email open/click rates
- Monthly: GPT-4o analyzes performance → suggests topic adjustments, format shifts, keyword re-prioritization
- Feeds back into the calendar generator

### 9.3 AEO/GEO for All Formats
- Every format gets voice-search optimization (concise Q&A, featured-snippet structure)
- Social posts get AI-engine-friendly descriptions
- Email subject lines optimized for AI email assistants (Apple Intelligence, Gmail summaries)
- Video scripts include structured metadata for YouTube's AI features

---

## 10. Implementation Plan

### Phase 1: Foundation (Sprint 1 — ~5 days)

| Task | Description | Priority |
|---|---|---|
| **1.1** | Project scaffold: directory structure, requirements.txt, .env, run.sh | P0 |
| **1.2** | SQLAlchemy models: brands, users, content_requests, generated_content, publishing_targets, publish_queue | P0 |
| **1.3** | Database init + migrations (Alembic) | P0 |
| **1.4** | Brand onboarding: create brand profile for AIS Technolabs (first client) | P0 |
| **1.5** | Auth system: JWT login, brand-scoped sessions | P0 |
| **1.6** | Base templates: Jinja2 layout, navigation, brand dashboard shell | P0 |

### Phase 2: Core Engine (Sprint 2 — ~7 days)

| Task | Description | Priority |
|---|---|---|
| **2.1** | Research layer: Serper integration (search + PAA), keyword extraction, competitor analysis | P0 |
| **2.2** | Blog generation pipeline: 6-pass GPT-4o with AIS brand voice | P0 |
| **2.3** | Context assembly: merge brand profile + research → structured bundle | P0 |
| **2.4** | Validation layer: compliance scan, banned terms, disclaimer enforcement | P0 |
| **2.5** | Content request form (web UI): topic, keywords, format selection, publish targets | P0 |
| **2.6** | Webhook endpoint: POST `/api/v1/generate` for external triggers | P0 |

### Phase 3: Multi-Format (Sprint 3 — ~5 days)

| Task | Description | Priority |
|---|---|---|
| **3.1** | LinkedIn carousel generator (4-pass) | P1 |
| **3.2** | Instagram carousel generator (4-pass) | P1 |
| **3.3** | Twitter/X thread generator (3-pass) | P2 |
| **3.4** | Email newsletter generator (3-pass) | P1 |
| **3.5** | YouTube Short script generator (3-pass) | P2 |
| **3.6** | YouTube Long script generator (3-pass) | P2 |
| **3.7** | Podcast outline generator (3-pass) | P2 |
| **3.8** | Format-agnostic output renderer (preview page with format tabs) | P1 |

### Phase 4: Publishing (Sprint 4 — ~4 days)

| Task | Description | Priority |
|---|---|---|
| **4.1** | Publish queue table + outbox logic | P0 |
| **4.2** | Publishing targets CRUD (web UI + API) | P0 |
| **4.3** | n8n Content Publisher workflow (Shopify, WordPress, Webhook) | P0 |
| **4.4** | n8n Postiz publisher workflow | P1 |
| **4.5** | n8n Mailchimp publisher workflow | P1 |
| **4.6** | Review/approve flow: draft → approve → enqueue | P0 |

### Phase 5: Images (Sprint 5 — ~3 days)

| Task | Description | Priority |
|---|---|---|
| **5.1** | fal.ai Flux integration | P1 |
| **5.2** | Per-format image prompt generation | P1 |
| **5.3** | Parallel image generation across formats | P1 |
| **5.4** | Image URL storage + preview in dashboard | P1 |

### Phase 6: Advanced (Sprint 6+ — ongoing)

| Task | Description | Priority |
|---|---|---|
| **6.1** | Content calendar auto-generator | P2 |
| **6.2** | Calendar UI + n8n cron runner | P2 |
| **6.3** | GSC analytics ingest + n8n collector | P2 |
| **6.4** | Social analytics ingest | P3 |
| **6.5** | Analytics feedback loop → calendar adjustment | P3 |
| **6.6** | AEO/GEO optimization for all formats | P2 |

---

## 11. Directory Structure

```
/home/aditya/workspace/contentforge/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI app + lifespan + middleware
│   ├── config.py              # Settings from .env
│   ├── models.py              # All SQLAlchemy models
│   ├── schemas.py             # Pydantic request/response schemas
│   ├── auth.py                # JWT auth + password hashing
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── web.py             # Dashboard routes (Jinja2)
│   │   ├── api.py             # REST API routes
│   │   └── webhooks.py        # Webhook endpoints
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── research.py        # Serper integration
│   │   ├── assembler.py       # Context assembly
│   │   ├── blog.py            # 6-pass blog pipeline
│   │   ├── social.py          # LinkedIn + Instagram + Twitter
│   │   ├── email_gen.py       # Email newsletter pipeline
│   │   ├── video.py           # YouTube Shorts + Long
│   │   ├── podcast.py         # Podcast outline pipeline
│   │   ├── validator.py       # Compliance + quality validation
│   │   └── image_gen.py       # Flux/fal.ai integration
│   ├── publishing/
│   │   ├── __init__.py
│   │   └── queue.py           # Outbox pattern + publish queue
│   ├── analytics/
│   │   ├── __init__.py
│   │   └── ingest.py          # Analytics data ingestion
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── settings.html
│       ├── content_new.html
│       ├── content_view.html
│       ├── calendar.html
│       ├── analytics.html
│       └── publishing.html
├── static/
│   └── style.css
├── n8n/
│   ├── content-publisher.json
│   ├── analytics-collector.json
│   ├── calendar-runner.json
│   └── review-reminder.json
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_engine.py
│   ├── test_api.py
│   └── test_publishing.py
├── .env
├── .env.template
├── requirements.txt
├── run.sh
└── PLAN.md                    # This file
```

---

## 12. Key Learnings from Dhanwantri (applied here)

| Dhanwantri gotcha | ContentForge solution |
|---|---|
| n8n regex literals break expressions | Python does all text processing — no n8n expression limitations |
| Native OpenAI node output is `message.content` | We control the OpenAI client directly, no n8n abstraction |
| Inserting node mid-chain breaks `$json` references | Python function pipeline — explicit data flow, no implicit JSON paths |
| DataForSEO $50 paywall blocks keyword volumes | Serper-only with GPT-4o volume estimates — no paywall |
| Async webhook needs early response to avoid timeout | FastAPI async endpoints — return `{"status":"accepted"}` immediately, process in background |
| Google Sheets `defineBelow` needs exact headers | We have SQLite structured storage — no Sheets dependency for core data |
| Flux is sync via `fal.run/` not async queue | We use `fal.run/` endpoint directly |
| Duplicate Save to Review Sheet node | Python code — no duplicate nodes possible |

---

## 13. Cost Estimates (per brand, per month)

| Item | Cost |
|---|---|
| GPT-4o (blog: ~$0.06 × 30) | ~$1.80/mo |
| GPT-4o (social/email/video: ~$0.03 × 30 × 4 formats) | ~$3.60/mo |
| Serper (free tier: 2,500 queries) | $0 |
| Flux images (fal.ai: ~$0.005/img × 50 imgs) | ~$0.25/mo |
| **Total per brand (30 posts/month)** | **~$5.65/mo** |

---

## 14. Decisions Made (August 23, 2026)

1. **Formats for v1:** Blog + LinkedIn carousel + Email newsletter (B2B trifecta). Instagram, Twitter, YouTube, Podcast deferred to v2.
2. **Image generation:** Deferred to Phase 5. Text-only for Phase 1–4.
3. **Hosting:** Local-first development. Production hosting decided later.
4. **n8n instance:** TBD — reuse existing or deploy new when publishing layer is built.
5. **API keys:** OpenAI + Serper. User provides keys in .env.
6. **LLM:** OpenAI GPT-4o directly (not OpenRouter). Use `openai` Python package.

---

*Ready for review. Feedback on any section welcome before we start building.*