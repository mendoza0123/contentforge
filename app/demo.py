"""
ContentForge — Run engine for the dashboard.

Two ways to run a content request:

  demo  — walks a seeded run through the pipeline in ~11s and writes a stored
          result. A pitch never stalls on a third-party API, and it works with
          no network at all.
  live  — POSTs the request to the brand's n8n webhook and waits for n8n's
          `Publish → Webhook` node to call back into
          POST /api/v1/webhook/n8n-result, which flips the request to `done`.

Both paths leave the same shape behind (a ContentRequest plus GeneratedContent
rows), so the viewer doesn't care which one produced the content.
"""
import json
import re
from datetime import datetime, timezone

import httpx

from app.models import ContentRequest, GeneratedContent, utcnow

# ═══════════════════════════════════════════════════════════════
# Pipeline shape — mirrors the 7 OpenAI passes in the n8n workflow
# ═══════════════════════════════════════════════════════════════

STEPS = [
    "Keyword research",
    "Outline & angle",
    "Long-form draft",
    "SEO audit",
    "AEO answer block",
    "GEO structuring",
    "Metadata & schema",
]

SETTLED = ("done", "failed")

# Demo timeline: (elapsed seconds at which this status begins, status, caption)
DEMO_TIMELINE = [
    (0.0, "pending", "Queued — warming up the engine"),
    (1.5, "researching", "Researching keywords and competitors"),
    (4.0, "generating", "Drafting the long-form article"),
    (8.0, "validating", "Auditing SEO, AEO and compliance"),
    (11.0, "done", "Complete"),
]
DEMO_TOTAL = DEMO_TIMELINE[-1][0]

# A real n8n run is 2–4 minutes. The bar creeps toward the ceiling of whatever
# stage n8n last reported, so it always moves but never overtakes the truth.
LIVE_EXPECTED = 190.0
LIVE_CEILING = {
    "pending": 12,
    "researching": 38,
    "generating": 76,
    "validating": 95,
}
LIVE_CAPTION = {
    "pending": "Handed to n8n — waiting for the first pass",
    "researching": "n8n is pulling keywords and SERP data",
    "generating": "n8n is drafting and structuring the piece",
    "validating": "Running the compliance and SEO audit",
}

# A live run finishes when n8n calls back. If the callback never lands — the
# workflow errored, or its publish branch has no callback step — fail the run
# rather than spinning forever.
LIVE_TIMEOUT = 900.0
LIVE_TIMEOUT_MESSAGE = (
    "n8n never called back. Check the run in n8n: whichever publish branch it "
    "took has to end in the 'Publish → Webhook (ContentForge)' node, and that "
    "node has to POST to this app's /api/v1/webhook/n8n-result."
)


# ═══════════════════════════════════════════════════════════════
# Progress model consumed by _run_status.html
# ═══════════════════════════════════════════════════════════════

def _elapsed(cr: ContentRequest) -> float:
    """Seconds since the request was created. Handles naive rows from SQLite."""
    created = cr.created_at
    if not created:
        return 0.0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - created).total_seconds())


def settle(db, cr: ContentRequest) -> bool:
    """Bring a run's status up to date on read. True if it changed.

    A demo run finishes on the clock: its result was stored at submit, and the
    row walks the timeline and flips to done as the panel is polled. Nothing
    runs in the background, so a host that freezes the process between
    requests — any serverless function — still sees the run complete.

    A live run is failed once n8n has had 15 minutes and never called back.
    """
    if cr.status in SETTLED:
        return False

    elapsed = _elapsed(cr)

    if (cr.run_mode or "demo") == "demo":
        stage = "pending"
        for at, status, _caption in DEMO_TIMELINE:
            if elapsed >= at:
                stage = status
        if stage == cr.status:
            return False
        cr.status = stage
        if stage == "done":
            cr.completed_at = utcnow()
        db.commit()
        return True

    if elapsed < LIVE_TIMEOUT:
        return False
    cr.status = "failed"
    cr.error_message = LIVE_TIMEOUT_MESSAGE
    db.commit()
    return True


def progress_for(cr: ContentRequest) -> dict:
    """Build the {pct, note, mode, steps[]} context the run panel renders."""
    mode = cr.run_mode or "demo"
    status = cr.status or "pending"

    if status == "done":
        return {
            "pct": 100,
            "note": "Complete",
            "mode": mode,
            "steps": [{"name": n, "state": "done"} for n in STEPS],
        }

    if status == "failed":
        steps = [{"name": n, "state": "pending"} for n in STEPS]
        steps[0]["state"] = "failed"
        return {
            "pct": 100,
            "note": "Run failed",
            "mode": mode,
            "steps": steps,
        }

    elapsed = _elapsed(cr)

    if mode == "live":
        pct = min(LIVE_CEILING.get(status, 90), 4 + (elapsed / LIVE_EXPECTED) * 95)
        note = LIVE_CAPTION.get(status, "Running on n8n")
    else:
        pct = min(97.0, (elapsed / DEMO_TOTAL) * 100)
        note = DEMO_TIMELINE[0][2]
        for at, st, caption in DEMO_TIMELINE:
            if elapsed >= at and st != "done":
                note = caption

    pct = int(round(pct))
    active = min(len(STEPS) - 1, int(pct / 100 * len(STEPS)))

    steps = []
    for i, name in enumerate(STEPS):
        if i < active:
            state = "done"
        elif i == active:
            state = "active"
        else:
            state = "pending"
        steps.append({"name": name, "state": state})

    return {"pct": pct, "note": note, "mode": mode, "steps": steps}


# ═══════════════════════════════════════════════════════════════
# n8n payload — matches the webhook's "Normalize Inputs" node exactly
# ═══════════════════════════════════════════════════════════════

# Our publish choices → the strings n8n's "Route by Publish Target" switch
# matches on. Anything else falls through to its draft-only no-op.
PUBLISH_TARGETS = {
    "Draft only": "Webhook",
    "Webhook": "Webhook",
    "WordPress": "WordPress",
    "Shopify": "Shopify",
}

def build_payload(brand, cr: ContentRequest) -> dict:
    """Body for POST {brand.n8n_webhook_url}.

    Field names and types come from the workflow's Normalize Inputs node —
    note word_count is a "min-max" *string*, and publish_target must be one of
    Shopify / WordPress / Webhook or n8n falls through to draft-only.
    """
    wc = cr.word_count or 1500
    return {
        "request_id": cr.request_id,
        "brand": brand.name if brand else "AIS Technolabs",
        "website": (brand.website if brand else "") or "",
        "niche": (brand.niche if brand else "") or "",
        "primary_topic": cr.primary_topic,
        "target_market": cr.target_market or "United States",
        "language": (brand.default_language if brand else "English") or "English",
        "brand_voice": (brand.brand_voice if brand else "") or "",
        "brand_facts": (brand.brand_facts if brand else "") or "",
        "products_to_feature": cr.products_to_feature or "",
        "approved_claims": (brand.approved_claims if brand else "") or "",
        "banned_terms": (brand.banned_terms if brand else "") or "",
        "author_bio": (brand.author_bio if brand else "") or "",
        "cta": (brand.default_cta if brand else "") or "",
        "compliance_disclaimer": (brand.compliance_rules if brand else "") or "",
        "word_count": f"{max(800, wc - 300)}-{wc + 300}",
        "kw_count": cr.kw_count or 10,
        "seed_keywords": cr.seed_keywords or "",
        "internal_links": cr.internal_links or "",
        # n8n routes on this exact string. Its "Webhook" branch publishes
        # nowhere and POSTs the finished draft back to us — which is precisely
        # what "Draft only" means here, so that's what we ask for. Shopify and
        # WordPress publish at n8n's end and never call back.
        "publish_target": PUBLISH_TARGETS.get(
            cr.publish_target or "Draft only", "Webhook"
        ),
        "notify_email": cr.notify_email or "",
    }


# ═══════════════════════════════════════════════════════════════
# Run dispatch
# ═══════════════════════════════════════════════════════════════

# n8n's first node is "Ack (respond now)", so a healthy dispatch returns in
# well under a second. Anything slower is a problem worth reporting, and a
# serverless function has only seconds before the platform kills it.
DISPATCH_TIMEOUT = 8.0


def start_run(db, cr: ContentRequest, brand) -> None:
    """Dispatch a run inside the request that created it.

    Nothing is handed to a thread. A serverless function is frozen the moment
    it responds, so work deferred past the response simply never happens —
    the POST to n8n would not go out, the demo would never finish.
    """
    if (cr.run_mode or "demo") == "live":
        _dispatch_live(db, cr, brand)
    else:
        # The stored result is written now. The pipeline walk the panel shows
        # is drawn from elapsed time, and settle() advances the row on read.
        seed_items(db, cr, brand.id if brand else 1)
    db.commit()


def _dispatch_live(db, cr: ContentRequest, brand) -> None:
    """POST to n8n. It acks immediately, then calls us back when it's done."""
    url = brand.n8n_webhook_url if brand else None
    if not url:
        cr.status = "failed"
        cr.error_message = "No n8n webhook URL is set for this brand."
        return

    try:
        resp = httpx.post(url, json=build_payload(brand, cr), timeout=DISPATCH_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        cr.status = "failed"
        cr.error_message = f"Could not reach n8n: {exc}"
        print(f"   ❌ n8n dispatch failed for {cr.request_id}: {exc}")
        return

    cr.status = "researching"
    print(f"   📤 Dispatched {cr.request_id} to n8n ({resp.status_code})")


# ═══════════════════════════════════════════════════════════════
# Seeded output
# ═══════════════════════════════════════════════════════════════

def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:80] or "untitled"


def _fit(text: str, lo: int, hi: int, filler: str) -> str:
    """Trim to <= hi on a word boundary, pad with filler until >= lo."""
    while len(text) < lo and filler:
        text = f"{text} {filler}".strip()
    if len(text) <= hi:
        return text
    cut = text[:hi]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,.;:—-")


def _title_of(topic: str) -> str:
    t = (topic or "content").strip().rstrip("?.")
    return t[0].upper() + t[1:] if t else "Untitled"


def _keywords(topic: str, seeds: str, count: int) -> list:
    """A believable keyword table: seeds first, then generated long-tails."""
    base = _title_of(topic).lower()
    head = [s.strip() for s in (seeds or "").split(",") if s.strip()]
    tails = [
        base,
        f"best {base}",
        f"{base} cost",
        f"{base} providers",
        f"{base} for startups",
        f"how to choose {base}",
        f"{base} 2026",
        f"{base} comparison",
        f"{base} features",
        f"{base} vs custom build",
        f"enterprise {base}",
        f"{base} checklist",
        f"{base} requirements",
        f"white label {base}",
    ]
    words, seen = [], set()
    for kw in head + tails:
        k = kw.lower()[:70]
        if k and k not in seen:
            seen.add(k)
            words.append(k)
    out = []
    for i, kw in enumerate(words[: max(3, count)]):
        out.append(
            {
                "keyword": kw,
                "volume": max(70, 4400 - i * 320),
                "difficulty": min(72, 18 + i * 4),
                "intent": "commercial" if i % 3 else "informational",
            }
        )
    return out


def _blog_html(topic: str, brand, products: str, links: str) -> str:
    t = _title_of(topic)
    brand_name = brand.name if brand else "the team"
    cta = (brand.default_cta if brand else "") or ""
    product_line = (products or "").strip()
    link_list = [l.strip() for l in (links or "").splitlines() if l.strip()]

    parts = [
        f"<p><strong>{t}</strong> is one of the first decisions that shapes everything "
        f"downstream — your launch date, your running costs, and how much of the platform "
        f"you actually own. This guide walks through what matters, in the order it matters.</p>",

        "<h2>The short answer</h2>",
        f"<p>Most teams evaluating this are really weighing three things: time to market, "
        f"total cost of ownership, and control over the codebase. A ready-to-deploy platform "
        f"typically moves fastest; a bespoke build gives you the most room to differentiate. "
        f"The right call depends on which of those three you are least able to compromise on.</p>",

        "<h2>What to evaluate first</h2>",
        "<ul>"
        "<li><strong>Ownership.</strong> Do you keep the source, the IP, and the revenue, "
        "or are you renting a platform and sharing a percentage forever?</li>"
        "<li><strong>Time to launch.</strong> Weeks or quarters? Ask for a delivery plan "
        "with named milestones, not a range.</li>"
        "<li><strong>Compliance and licensing.</strong> Confirm which jurisdictions are "
        "supported out of the box and what each additional one costs.</li>"
        "<li><strong>Integrations.</strong> Payments, KYC, analytics and CRM should be "
        "documented integrations, not a services line item.</li>"
        "<li><strong>Support model.</strong> Who is on the hook at 2am in your busiest "
        "market, and what does the SLA actually promise?</li>"
        "</ul>",

        "<h2>Where teams get this wrong</h2>",
        "<p>The most expensive mistake is optimising for the launch and not for month "
        "eighteen. A platform that ships quickly but locks you into revenue sharing can "
        "cost several times a one-off build by the time you are at scale. Model both over "
        "three years before you sign anything.</p>",
        "<p>The second is treating compliance as a launch checklist rather than an ongoing "
        "obligation. Requirements shift, and a platform that cannot adapt to them becomes "
        "a liability rather than an asset.</p>",

        "<h2>A practical evaluation checklist</h2>",
        "<ol>"
        "<li>Write down your must-have markets and confirm licensing support for each.</li>"
        "<li>Ask for a live environment, not a slide deck.</li>"
        "<li>Get the integration list in writing, with versions.</li>"
        "<li>Model three-year cost including revenue share, hosting and support.</li>"
        "<li>Confirm in the contract who owns the code and the data.</li>"
        "<li>Agree the escalation path and response times before go-live.</li>"
        "</ol>",
    ]

    if product_line:
        parts += [
            "<h2>How we approach it</h2>",
            f"<p>{brand_name} delivers this through {product_line} — built so you own the "
            f"code and the IP outright, with no revenue sharing, and a delivery plan that "
            f"gets you to a live environment in weeks rather than quarters.</p>",
        ]

    if link_list:
        items = "".join(
            f'<li><a href="{u}">{u.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title() or u}</a></li>'
            for u in link_list[:5]
        )
        parts += ["<h2>Related reading</h2>", f"<ul>{items}</ul>"]

    parts += [
        "<h2>Bottom line</h2>",
        "<p>Decide what you cannot compromise on first — speed, cost, or control — then "
        "let that pick the approach. Every credible provider should be able to show you a "
        "working environment, a delivery plan, and a contract that says plainly who owns "
        "what at the end of it.</p>",
    ]

    if cta:
        parts.append(f'<p class="cta"><strong>{cta}</strong></p>')

    if brand and brand.compliance_rules:
        parts.append(
            "<p><em>This article is written for operators and technology buyers. "
            "Platform availability and licensing requirements vary by jurisdiction.</em></p>"
        )

    return "\n".join(parts)


def _faqs(topic: str) -> list:
    t = _title_of(topic).lower()
    return [
        (
            f"How long does {t} usually take?",
            "For a ready-to-deploy platform, typically four to eight weeks from kickoff to "
            "a live environment. A fully bespoke build is usually a quarter or more, "
            "depending on the integration list.",
        ),
        (
            f"What does {t} cost?",
            "Cost is driven by scope, the number of markets you need licensed, and whether "
            "you pay a one-off build fee or an ongoing revenue share. Model both over three "
            "years — the cheaper option at launch is often the more expensive one at scale.",
        ),
        (
            "Do we own the source code?",
            "You should. Ask for it explicitly in the contract, alongside IP assignment and "
            "a data export guarantee. Any provider that will not commit to this in writing "
            "is telling you something useful.",
        ),
        (
            "Which integrations are supported out of the box?",
            "Payments, KYC/AML, analytics and CRM should all be documented, versioned "
            "integrations. Ask for the list in writing before you sign.",
        ),
        (
            "How is ongoing support handled?",
            "Look for a named escalation path, a written SLA with response times, and "
            "coverage that matches the timezones of your busiest markets.",
        ),
    ]


def _slides(topic: str, brand) -> list:
    t = _title_of(topic)
    brand_name = brand.name if brand else "We"
    return [
        # No numbers in the titles — the card prints its own "03 / 8" counter,
        # and a hand-written one beside it only ever disagrees. The cover is
        # slide 1, so every title here was already off by one.
        {"title": t, "body": "A 7-point evaluation framework for operators and technology buyers."},
        {"title": "Start with ownership", "body": "Do you keep the source, the IP and the revenue — or are you renting the platform forever?"},
        {"title": "Time to launch", "body": "Weeks or quarters? Ask for named milestones, not a range."},
        {"title": "Compliance first", "body": "Confirm which jurisdictions are supported out of the box, and what each extra one costs."},
        {"title": "Integrations", "body": "Payments, KYC, analytics, CRM. Documented and versioned — or it is a services line item in disguise."},
        {"title": "Support model", "body": "Who is on the hook at 2am in your busiest market? Get the SLA in writing."},
        {"title": "Model three years", "body": "Revenue share compounds. The cheap option at launch is often the expensive one at scale."},
        {"title": "The bottom line", "body": f"Decide what you cannot compromise on — speed, cost or control. {brand_name} can walk you through the trade-offs."},
    ]


def _email_html(topic: str, brand) -> str:
    t = _title_of(topic)
    cta = (brand.default_cta if brand else "") or "Reply to this email and we'll set up a call."
    return (
        f"<p>Hi there,</p>"
        f"<p>If <strong>{t.lower()}</strong> is on your roadmap this quarter, three things "
        f"decide how it goes: how much of the platform you actually own, how fast you can "
        f"launch, and what it costs you at scale — not at signature.</p>"
        f"<p>We put together a short guide on how to weigh those against each other, "
        f"including the checklist we use in evaluations:</p>"
        f"<ul>"
        f"<li>Ownership of code, IP and revenue</li>"
        f"<li>Realistic time to a live environment</li>"
        f"<li>Licensing coverage per market</li>"
        f"<li>Three-year total cost, modelled both ways</li>"
        f"</ul>"
        f"<p>{cta}</p>"
        f"<p>— The team</p>"
    )


def seed_items(db, cr: ContentRequest, brand_id: int) -> None:
    """Write the stored result for a demo run, one row per requested format."""
    from app.models import Brand

    brand = db.query(Brand).filter(Brand.id == brand_id).first()

    try:
        formats = json.loads(cr.formats) if cr.formats else []
    except (ValueError, TypeError):
        formats = []
    if not formats:
        formats = ["blog"]

    # A re-run of the same request replaces its output rather than doubling it.
    db.query(GeneratedContent).filter(
        GeneratedContent.request_id == cr.request_id
    ).delete(synchronize_session=False)

    topic = cr.primary_topic or "content"
    t = _title_of(topic)
    year = (cr.created_at or utcnow()).year
    keywords = _keywords(topic, cr.seed_keywords, cr.kw_count or 10)
    faqs = _faqs(topic)
    slug = slugify(topic)
    website = (brand.website if brand else "") or "https://example.com"

    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": f"{t}: What Operators Need to Know in {year}",
        "description": _fit(
            f"A practical guide to {t.lower()} — ownership, launch timelines, licensing "
            f"and three-year cost, with the checklist we use in evaluations.",
            150, 160, "Read the full breakdown.",
        ),
        "author": {
            "@type": "Organization",
            "name": brand.name if brand else "ContentForge",
            "description": (brand.author_bio if brand else "") or "",
        },
        "datePublished": (cr.created_at or utcnow()).strftime("%Y-%m-%d"),
        "mainEntityOfPage": f"{website.rstrip('/')}/blog/{slug}",
    }

    faq_ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in faqs
        ],
    }

    for fmt in formats:
        if fmt == "linkedin_carousel":
            item = GeneratedContent(
                request_id=cr.request_id,
                brand_id=brand_id,
                format=fmt,
                title=f"{t} — 7-slide breakdown",
                meta_title=_fit(f"{t}: the 7-point checklist", 50, 60, "for operators"),
                meta_description=_fit(
                    f"A 7-slide LinkedIn carousel on {t.lower()} — ownership, launch "
                    f"timelines, licensing and total cost.",
                    150, 160, "Swipe through the full breakdown.",
                ),
                slug=f"{slug}-carousel",
                body_markdown=json.dumps(_slides(topic, brand), ensure_ascii=False),
                keywords=json.dumps(keywords[:6], ensure_ascii=False),
                status="approved",
                image_prompt=(
                    f"LinkedIn carousel cover for '{t}'. "
                    f"{(brand.visual_style if brand else '')}"
                ).strip(),
                image_alt=f"Carousel cover slide reading “{t}”",
            )
        elif fmt == "email_newsletter":
            item = GeneratedContent(
                request_id=cr.request_id,
                brand_id=brand_id,
                format=fmt,
                title=f"{t} — what actually matters",
                meta_title=_fit(f"{t}: what actually matters", 50, 60, "this quarter"),
                meta_description=_fit(
                    f"Newsletter edition on {t.lower()}: ownership, launch speed and the "
                    f"three-year cost most teams forget to model.",
                    150, 160, "Read the short version.",
                ),
                slug=f"{slug}-newsletter",
                body_html=_email_html(topic, brand),
                keywords=json.dumps(keywords[:4], ensure_ascii=False),
                status="approved",
            )
        else:  # blog
            item = GeneratedContent(
                request_id=cr.request_id,
                brand_id=brand_id,
                format="blog",
                title=f"{t}: What Operators Need to Know in {year}",
                meta_title=_fit(f"{t} — {year} Buyer's Guide", 50, 60, "for Operators"),
                meta_description=_fit(
                    f"A practical guide to {t.lower()}: ownership, launch timelines, "
                    f"licensing and three-year cost, plus the evaluation checklist.",
                    150, 160, "Read the full breakdown.",
                ),
                slug=slug,
                body_html=_blog_html(topic, brand, cr.products_to_feature, cr.internal_links),
                faq_json=json.dumps(faq_ld, indent=2, ensure_ascii=False),
                schema_json=json.dumps(schema, indent=2, ensure_ascii=False),
                keywords=json.dumps(keywords, ensure_ascii=False),
                status="approved",
                image_prompt=(
                    f"Hero image for an article titled '{t}'. "
                    f"{(brand.visual_style if brand else '')}"
                ).strip(),
                image_alt=f"Illustration representing {t.lower()}",
            )

        db.add(item)
