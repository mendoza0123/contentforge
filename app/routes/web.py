"""
ContentForge — Web Dashboard Routes (Jinja2 + HTMX)
"""
import json
import os
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.main import get_db
from app.auth import authenticate_user, create_access_token, decode_access_token
from app.models import Brand, User, ContentRequest, GeneratedContent, generate_uuid
from app import demo

router = APIRouter()

# Template engine — use raw Jinja2 to avoid Starlette cache bug
template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
template_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(["html"]),
    cache_size=0,  # disable cache to avoid unhashable dict key issue
)


def _loads(raw):
    """Parse a JSON column that may be null, blank, or not JSON at all."""
    if not raw:
        return None
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


template_env.filters["from_json"] = _loads


def render(name: str, request: Request, **context) -> HTMLResponse:
    """Render a Jinja2 template and return an HTMLResponse."""
    template = template_env.get_template(name)
    html = template.render(request=request, **context)
    return HTMLResponse(html)


# ═══════════════════════════════════════════════════════════════
# Session helpers
# ═══════════════════════════════════════════════════════════════

def current_user(request: Request, db: Session):
    """Resolve the signed-in user from the cf_token cookie, or None."""
    token = request.cookies.get("cf_token")
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user = db.query(User).filter(
        User.id == payload.get("user_id"), User.is_active == True  # noqa: E712
    ).first()
    if not user:
        return None
    return {
        "user_id": user.id,
        "brand_id": user.brand_id,
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name or user.email,
    }


def brand_for(user: dict, db: Session):
    """The signed-in user's brand, falling back to the default tenant."""
    brand = None
    if user and user.get("brand_id"):
        brand = db.query(Brand).filter(Brand.id == user["brand_id"]).first()
    return brand or db.query(Brand).filter(Brand.slug == "ais-technolabs").first()


def engine_ctx(brand) -> dict:
    """Which generation engine the dashboard should advertise."""
    url = (brand.n8n_webhook_url if brand else "") or ""
    if url:
        host = urlparse(url).netloc or url
        return {"mode": "live", "label": f"n8n · {host}", "webhook_url": url}
    return {
        "mode": "demo",
        "label": "Seeded demo runs · no webhook configured",
        "webhook_url": "",
    }


def stats_for(brand, db: Session) -> dict:
    """Counters for the dashboard tiles."""
    brand_id = brand.id if brand else None

    reqs = db.query(ContentRequest)
    items = db.query(GeneratedContent)
    formats_q = db.query(func.count(func.distinct(GeneratedContent.format)))
    if brand_id:
        reqs = reqs.filter(ContentRequest.brand_id == brand_id)
        items = items.filter(GeneratedContent.brand_id == brand_id)
        formats_q = formats_q.filter(GeneratedContent.brand_id == brand_id)

    return {
        "total": items.count(),
        # Only genuinely published pieces — an approved draft isn't live yet.
        "published": items.filter(GeneratedContent.status == "published").count(),
        "formats": formats_q.scalar() or 0,
        "in_progress": reqs.filter(
            ~ContentRequest.status.in_(demo.SETTLED)
        ).count(),
    }


def recent_for(brand, db: Session, limit: int = 10):
    q = db.query(ContentRequest)
    if brand:
        q = q.filter(ContentRequest.brand_id == brand.id)
    return q.order_by(ContentRequest.created_at.desc()).limit(limit).all()


# ═══════════════════════════════════════════════════════════════
# Generated-content view model
# ═══════════════════════════════════════════════════════════════

FORMAT_ORDER = {"blog": 0, "linkedin_carousel": 1, "email_newsletter": 2}


def _faqs_of(item) -> list:
    """FAQ pairs from either FAQPage JSON-LD or a plain list of Q/A objects."""
    data = _loads(item.faq_json)
    entries = []
    if isinstance(data, dict):
        entries = data.get("mainEntity") or data.get("faqs") or []
    elif isinstance(data, list):
        entries = data

    out = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        q = e.get("q") or e.get("question") or e.get("name")
        answer = e.get("acceptedAnswer")
        if isinstance(answer, dict):
            a = answer.get("text")
        else:
            a = e.get("a") or e.get("answer") or e.get("text")
        if q:
            out.append({"q": str(q), "a": str(a or "")})
    return out


def _keywords_of(item) -> list:
    """Flat keyword strings from a list of strings, objects, or a CSV string."""
    data = _loads(item.keywords)
    if data is None and item.keywords:
        data = [k.strip() for k in str(item.keywords).split(",")]
    if not isinstance(data, list):
        return []

    out = []
    for k in data:
        if isinstance(k, str) and k.strip():
            out.append(k.strip())
        elif isinstance(k, dict):
            v = k.get("keyword") or k.get("kw") or k.get("term") or k.get("name")
            if v:
                out.append(str(v))
    return out[:24]


def _slides_of(item) -> list:
    """Carousel slides — stored as a JSON array in body_markdown."""
    data = _loads(item.body_markdown)
    out = []
    if isinstance(data, list):
        for s in data:
            if isinstance(s, dict):
                out.append(
                    {
                        "title": s.get("title") or s.get("headline") or "",
                        "body": s.get("body") or s.get("text") or "",
                    }
                )
            elif isinstance(s, str) and s.strip():
                out.append({"title": "", "body": s.strip()})
        return out

    # Fallback: markdown with "## " headings, one slide per heading.
    for block in (item.body_markdown or "").split("\n## "):
        block = block.strip().lstrip("# ").strip()
        if not block:
            continue
        head, _, body = block.partition("\n")
        out.append({"title": head.strip(), "body": body.strip()})
    return out


def decorate(items: list) -> list:
    """Attach the computed attributes the viewer template reads."""
    for it in items:
        it.faqs = _faqs_of(it)
        it.keyword_list = _keywords_of(it)
        it.slides = _slides_of(it) if it.format == "linkedin_carousel" else []
    return items


# ═══════════════════════════════════════════════════════════════
# Auth pages
# ═══════════════════════════════════════════════════════════════

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    if current_user(request, db):
        return RedirectResponse("/dashboard", status_code=303)
    return render("login.html", request, user=None)


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, email, password)
    if not user:
        return render("login.html", request, user=None, error="Invalid email or password")

    token = create_access_token(
        {
            "sub": user["email"],
            "user_id": user["user_id"],
            "brand_id": user["brand_id"],
            "role": user["role"],
            "full_name": user.get("full_name") or user["email"],
        }
    )
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("cf_token", token, httponly=True, samesite="lax")
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("cf_token")
    return response


# ═══════════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════════

@router.get("/", response_class=HTMLResponse)
def root(request: Request):
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    brand = brand_for(user, db)
    return render(
        "dashboard.html",
        request,
        user=user,
        brand=brand,
        engine=engine_ctx(brand),
        stats=stats_for(brand, db),
        recent_requests=recent_for(brand, db),
    )


# ═══════════════════════════════════════════════════════════════
# New content
#   NOTE: /content/new must stay declared above /content/{request_id},
#   or "new" gets matched as a request_id.
# ═══════════════════════════════════════════════════════════════

@router.get("/content/new", response_class=HTMLResponse)
def content_new(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    brand = brand_for(user, db)
    return render(
        "content_new.html",
        request,
        user=user,
        brand=brand,
        engine=engine_ctx(brand),
    )


@router.post("/content/new")
def content_new_submit(
    request: Request,
    db: Session = Depends(get_db),
    primary_topic: str = Form(default=""),
    seed_keywords: str = Form(default=""),
    products_to_feature: str = Form(default=""),
    word_count: str = Form(default="1500"),
    kw_count: str = Form(default="10"),
    target_market: str = Form(default="United States"),
    publish_target: str = Form(default="Draft only"),
    formats: list[str] = Form(default=[]),
    internal_links: str = Form(default=""),
    notify_email: str = Form(default=""),
    run_mode: str = Form(default="demo"),
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    brand = brand_for(user, db)
    engine = engine_ctx(brand)

    def reject(message: str):
        return render(
            "content_new.html",
            request,
            user=user,
            brand=brand,
            engine=engine,
            error=message,
        )

    topic = (primary_topic or "").strip()
    if not topic:
        return reject("Give the engine a primary topic to work from.")

    picked = [f for f in formats if f]
    if not picked:
        return reject("Pick at least one output format.")

    # A live run needs a webhook to call. Fall back rather than launching
    # something that can never finish.
    mode = "live" if run_mode == "live" and engine["webhook_url"] else "demo"

    def as_int(value, default):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    cr = ContentRequest(
        brand_id=brand.id if brand else 1,
        request_id=generate_uuid(),
        primary_topic=topic,
        products_to_feature=(products_to_feature or "").strip() or None,
        seed_keywords=(seed_keywords or "").strip() or None,
        internal_links=(internal_links or "").strip() or None,
        word_count=as_int(word_count, 1500),
        kw_count=as_int(kw_count, 10),
        formats=json.dumps(picked),
        notify_email=(notify_email or "").strip() or None,
        target_market=target_market or "United States",
        publish_target=publish_target or "Draft only",
        run_mode=mode,
        status="pending",
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)

    demo.start_run(cr, brand)

    return RedirectResponse(f"/content/{cr.request_id}", status_code=303)


@router.get("/content/{request_id}", response_class=HTMLResponse)
def content_view(request: Request, request_id: str, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    cr = db.query(ContentRequest).filter(
        ContentRequest.request_id == request_id
    ).first()
    if not cr:
        return RedirectResponse("/dashboard", status_code=303)

    demo.settle_if_stale(db, cr)

    items = (
        db.query(GeneratedContent)
        .filter(GeneratedContent.request_id == request_id)
        .all()
    )
    items.sort(key=lambda i: FORMAT_ORDER.get(i.format, 99))

    brand = brand_for(user, db)
    return render(
        "content_view.html",
        request,
        user=user,
        brand=brand,
        request_obj=cr,
        items=decorate(items),
        progress=demo.progress_for(cr),
    )


# ═══════════════════════════════════════════════════════════════
# HTMX partials
# ═══════════════════════════════════════════════════════════════

@router.get("/partials/recent", response_class=HTMLResponse)
def partial_recent(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return HTMLResponse("", headers={"HX-Redirect": "/login"})

    brand = brand_for(user, db)
    return render(
        "_recent_list.html",
        request,
        user=user,
        brand=brand,
        stats=stats_for(brand, db),
        recent_requests=recent_for(brand, db),
    )


@router.get("/partials/run/{request_id}", response_class=HTMLResponse)
def partial_run(request: Request, request_id: str, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return HTMLResponse("", headers={"HX-Redirect": "/login"})

    cr = db.query(ContentRequest).filter(
        ContentRequest.request_id == request_id
    ).first()
    if not cr:
        return HTMLResponse("", headers={"HX-Refresh": "true"})

    demo.settle_if_stale(db, cr)

    # Settled: stop polling and let the page reload into the finished article.
    if cr.status in demo.SETTLED:
        return HTMLResponse("", headers={"HX-Refresh": "true"})

    return render(
        "_run_status.html",
        request,
        user=user,
        request_obj=cr,
        progress=demo.progress_for(cr),
    )


# ═══════════════════════════════════════════════════════════════
# Settings
# ═══════════════════════════════════════════════════════════════

@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    brand = brand_for(user, db)
    return render(
        "settings.html",
        request,
        user=user,
        brand=brand,
        engine=engine_ctx(brand),
        saved=None,
    )


@router.post("/settings")
def settings_save(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(default=""),
    website: str = Form(default=""),
    niche: str = Form(default=""),
    brand_voice: str = Form(default=""),
    brand_facts: str = Form(default=""),
    approved_claims: str = Form(default=""),
    banned_terms: str = Form(default=""),
    compliance_rules: str = Form(default=""),
    author_bio: str = Form(default=""),
    default_cta: str = Form(default=""),
    default_language: str = Form(default="English"),
    visual_style: str = Form(default=""),
    brand_colors: str = Form(default=""),
    n8n_webhook_url: str = Form(default=""),
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    brand = brand_for(user, db)
    if brand:
        brand.name = name or brand.name
        brand.website = website or brand.website
        brand.niche = niche or brand.niche
        brand.brand_voice = brand_voice or brand.brand_voice
        brand.brand_facts = brand_facts or brand.brand_facts
        brand.approved_claims = approved_claims or brand.approved_claims
        brand.banned_terms = banned_terms or brand.banned_terms
        brand.compliance_rules = compliance_rules or brand.compliance_rules
        brand.author_bio = author_bio or brand.author_bio
        brand.default_cta = default_cta or brand.default_cta
        brand.default_language = default_language or brand.default_language
        brand.visual_style = visual_style or brand.visual_style
        brand.brand_colors = brand_colors or brand.brand_colors
        # Blank clears the webhook — that's how you switch back to demo-only.
        brand.n8n_webhook_url = (n8n_webhook_url or "").strip() or None
        db.commit()
        db.refresh(brand)

    return render(
        "settings.html",
        request,
        user=user,
        brand=brand,
        engine=engine_ctx(brand),
        saved=True,
    )


# ═══════════════════════════════════════════════════════════════
# Calendar
# ═══════════════════════════════════════════════════════════════

@router.get("/calendar", response_class=HTMLResponse)
def calendar_page(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    from app.models import CalendarEntry

    brand = brand_for(user, db)
    entries = []
    if brand:
        entries = (
            db.query(CalendarEntry)
            .filter(CalendarEntry.brand_id == brand.id)
            .order_by(CalendarEntry.scheduled_date.asc())
            .all()
        )

    return render(
        "calendar.html",
        request,
        user=user,
        brand=brand,
        entries=entries,
    )
