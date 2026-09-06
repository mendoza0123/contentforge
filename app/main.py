"""
ContentForge — FastAPI Application
Multi-tenant SEO/AEO/GEO Content Generation Engine.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.models import init_db, get_session, Brand, User, CalendarEntry
from app.auth import hash_password


# ═══════════════════════════════════════════════════════════════
# Lifespan: startup / shutdown
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_ready()
    yield
    app.state.engine.dispose()


def _ensure_ready() -> None:
    """Initialise the database exactly once, lifespan or not.

    Vercel calls the ASGI app per request and never sends lifespan events, so
    startup work that lives only in `lifespan` never runs there and the first
    request dies on a missing app.state. Every entry point funnels through
    here instead; it is idempotent, so the lifespan and a cold request agree.
    """
    if getattr(app.state, "SessionLocal", None) is not None:
        return

    engine = init_db(settings.database_url)
    app.state.engine = engine
    app.state.SessionLocal = get_session(engine)
    print(f"✅ Database initialized: {settings.database_url}")

    # Default brand + admin, then the finished catalogue if the brand has no
    # runs yet — a fresh database opens pitch-ready instead of on an empty
    # state, and on a serverless host a fresh database is every cold start.
    _seed_database(app.state.SessionLocal())
    from scripts.seed_demo import seed_catalogue_if_empty

    seed_catalogue_if_empty(app.state.SessionLocal())
    print("✅ Seed data checked")


def _seed_database(db: Session):
    """Create default brand and admin user if they don't exist."""
    try:
        # AIS Technolabs brand
        if not db.query(Brand).filter(Brand.slug == "ais-technolabs").first():
            ais = Brand(
                name="AIS Technolabs",
                slug="ais-technolabs",
                website="https://www.aistechnolabs.com/",
                niche="iGaming & Casino Software",
                brand_voice=(
                    "Professional, confident, growth-oriented, and consultative B2B tone. "
                    "Mixes technical authority with entrepreneurial energy. "
                    "Key themes: ownership/control ('fully owned, zero revenue sharing'), "
                    "speed ('ready-to-launch'), partnership ('trusted partner'), "
                    "innovation ('next-gen, AI-driven'). "
                    "Uses bold aspirational language balanced with credibility signals. "
                    "Avoids overly casual language; stays polished and businesslike."
                ),
                brand_facts=(
                    "AIS Technolabs PVT LTD (AIS Group Ventures) is an ISO 27001:2013 and "
                    "ISO 9001 certified IT consulting and software development company "
                    "headquartered in Ahmedabad, India, with offices in USA (CA), Canada, and UK.\n\n"
                    "KEY PRODUCTS & SERVICES:\n"
                    "- White-label casino, crypto casino, and sportsbook platforms (ready in 4-8 weeks)\n"
                    "- Casino game development (slots, poker, blackjack, roulette, baccarat, teen patti, rummy, crash games)\n"
                    "- Sweepstakes casino software and platforms\n"
                    "- Sports betting software (cricket, football/soccer, horse racing, esports)\n"
                    "- Poker software and platforms\n"
                    "- iGaming CRM and tracking solutions\n"
                    "- Gaming licensing assistance (Curacao, Malta, Kahnawake, Zambia)\n"
                    "- Remote IT talent staffing (500+ task forces, 13+ tech stacks)\n\n"
                    "KEY STATS:\n"
                    "- 16+ years in industry, 3,900+ projects delivered, 600+ global clients\n"
                    "- 180+ apps launched, 1,500+ happy customers, 95% client retention\n"
                    "- Operates in 36+ countries\n"
                    "- Core promise: clients own code, IP, and keep all revenue (zero revenue sharing)"
                ),
                approved_claims=(
                    "ISO 27001:2013 certified, ISO 9001 certified, "
                    "16+ years experience, 3,900+ projects, 600+ global clients, "
                    "1,500+ happy customers, 95% retention, "
                    "4.5 star rating (526 reviews), 4.9 star rating (165 reviews)"
                ),
                banned_terms=(
                    "guaranteed revenue, guaranteed profit, guaranteed players, "
                    "guaranteed ROI, #1 in industry, best in the world, "
                    "only provider, cheapest"
                ),
                compliance_rules=(
                    "1. Never claim guaranteed revenue or profit from casino operation.\n"
                    "2. Never claim specific player acquisition numbers.\n"
                    "3. For gambling-related content, include responsible gaming note where appropriate.\n"
                    "4. Do not promote gambling to minors or in jurisdictions where it's illegal.\n"
                    "5. Focus on technology, platform features, and business enablement — not gambling outcomes.\n"
                    "6. Client names/case studies should be anonymized unless explicitly approved.\n"
                    "7. Pricing and timelines: 'starting at' or 'typically', never fixed."
                ),
                author_bio=(
                    "AIS Technolabs is an ISO-certified iGaming and software development company "
                    "with 16+ years of experience delivering white-label casino, sportsbook, and "
                    "poker platforms to operators in 36+ countries."
                ),
                default_cta="Get a free consultation → https://www.aistechnolabs.com/contact/",
                target_markets=(
                    '[{"country":"United States","geo":"gl:us"},'
                    '{"country":"United Kingdom","geo":"gl:uk"},'
                    '{"country":"Canada","geo":"gl:ca"},'
                    '{"country":"India","geo":"gl:in"},'
                    '{"country":"UAE","geo":"gl:ae"},'
                    '{"country":"Global","geo":"gl:global"}]'
                ),
                default_language="English",
                visual_style=(
                    "Professional, tech-forward B2B imagery. Dark theme with blue and orange accents. "
                    "Geometric patterns, abstract tech visuals, casino/gaming UI elements shown tastefully."
                ),
                brand_colors="#0A1628 (dark navy), #E87722 (orange accent), #1E90FF (tech blue), #FFFFFF (white)",
            )
            db.add(ais)
            db.flush()

            # Admin user for AIS
            admin = User(
                brand_id=ais.id,
                email="admin@ais-tech.com",
                password_hash=hash_password("admin123"),  # change on first login
                full_name="AIS Admin",
                role="admin",
            )
            db.add(admin)
            db.commit()
            print("   ✅ Seeded AIS Technolabs brand + admin user")

    except Exception as e:
        db.rollback()
        print(f"   ⚠️  Seed warning (may already exist): {e}")
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# App factory
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="ContentForge",
    description="Multi-tenant SEO/AEO/GEO Content Generation Engine",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files
import os
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
template_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=template_dir)


# ═══════════════════════════════════════════════════════════════
# DB dependency
# ═══════════════════════════════════════════════════════════════

def get_db():
    """FastAPI dependency: yield a database session."""
    _ensure_ready()
    db = app.state.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# Health check
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ContentForge", "version": "0.1.0"}


# ═══════════════════════════════════════════════════════════════
# Import route modules (at end to avoid circular imports)
# ═══════════════════════════════════════════════════════════════

# Register route modules
from app.routes import web, api
app.include_router(web.router)
app.include_router(api.router)