"""
ContentForge — Web Dashboard Routes (Jinja2 + HTMX)
"""
import os
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.templating import _TemplateResponse as TemplateResponse
from sqlalchemy.orm import Session

from app.main import get_db
from app.auth import authenticate_user, create_access_token
from app.models import Brand, User, ContentRequest, GeneratedContent

router = APIRouter()

# Template engine — use raw Jinja2 to avoid Starlette cache bug
template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
template_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(["html"]),
    cache_size=0,  # disable cache to avoid unhashable dict key issue
)


def render(name: str, request: Request, **context) -> HTMLResponse:
    """Render a Jinja2 template and return an HTMLResponse."""
    template = template_env.get_template(name)
    html = template.render(request=request, **context)
    return HTMLResponse(html)


# ═══════════════════════════════════════════════════════════════
# Auth pages
# ═══════════════════════════════════════════════════════════════

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
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

    brand = db.query(Brand).filter(Brand.id == user["brand_id"]).first()
    token = create_access_token(
        {
            "sub": user["email"],
            "user_id": user["user_id"],
            "brand_id": user["brand_id"],
            "role": user["role"],
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
    brand = db.query(Brand).filter(Brand.slug == "ais-technolabs").first()

    recent_requests = (
        db.query(ContentRequest)
        .filter(ContentRequest.brand_id == brand.id if brand else True)
        .order_by(ContentRequest.created_at.desc())
        .limit(10)
        .all()
    )

    return render(
        "dashboard.html",
        request,
        user={"full_name": "AIS Admin", "role": "admin"},
        brand=brand,
        recent_requests=recent_requests,
    )


@router.get("/content/new", response_class=HTMLResponse)
def content_new(request: Request, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.slug == "ais-technolabs").first()
    return render(
        "content_new.html",
        request,
        user={"full_name": "AIS Admin"},
        brand=brand,
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.slug == "ais-technolabs").first()
    return render(
        "settings.html",
        request,
        user={"full_name": "AIS Admin"},
        brand=brand,
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
    brand = db.query(Brand).filter(Brand.slug == "ais-technolabs").first()
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
        brand.n8n_webhook_url = n8n_webhook_url or brand.n8n_webhook_url
        db.commit()
        db.refresh(brand)

    return render(
        "settings.html",
        request,
        user={"full_name": "AIS Admin"},
        brand=brand,
        saved=True,
    )


@router.get("/calendar", response_class=HTMLResponse)
def calendar_page(request: Request, db: Session = Depends(get_db)):
    return render(
        "calendar.html",
        request,
        user={"full_name": "AIS Admin"},
        entries=[],
    )