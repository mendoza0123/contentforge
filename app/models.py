"""
ContentForge — SQLAlchemy Data Models
Multi-tenant content generation engine.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Float,
    String,
    Text,
    DateTime,
    Date,
    Boolean,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()


def get_engine(database_url: str):
    """Create SQLAlchemy engine with SQLite-specific settings."""
    # timeout: run threads hold their own connection, so a background write can
    # land while a request is writing. Wait rather than throw "database is locked".
    connect_args = (
        {"check_same_thread": False, "timeout": 15}
        if database_url.startswith("sqlite")
        else {}
    )
    return create_engine(database_url, echo=False, connect_args=connect_args)


def get_session(engine):
    """Create a session factory."""
    return sessionmaker(bind=engine)


def generate_uuid() -> str:
    """Generate a short UUID for request tracking."""
    return uuid.uuid4().hex[:12]


def utcnow():
    """Timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════
# Brands (multi-tenant core)
# ═══════════════════════════════════════════════════════════════

class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False)
    website = Column(String(500))
    niche = Column(String(200))
    brand_voice = Column(Text)                     # LLM prompt: brand voice description
    brand_facts = Column(Text)                     # grounding anchor: products, services, USPs
    approved_claims = Column(Text)                 # claims allowed in content
    banned_terms = Column(Text)                    # comma-separated banned words
    compliance_rules = Column(Text)                # niche-specific rules (AYUSH, iGaming, etc.)
    author_bio = Column(Text)                      # default author bio
    default_cta = Column(Text)                     # "Get a free demo today"
    target_markets = Column(Text)                  # JSON: [{"country":"US","geo":"gl:us"},...]
    default_language = Column(String(50), default="English")
    visual_style = Column(Text)                    # image generation: style description
    brand_colors = Column(Text)                    # image generation: hex palette
    n8n_webhook_url = Column(String(500))          # n8n trigger webhook URL for content generation
    openai_api_key = Column(String(200))           # per-brand key (or use platform default)
    serper_api_key = Column(String(200))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    users = relationship("User", back_populates="brand", cascade="all, delete-orphan")
    content_requests = relationship("ContentRequest", back_populates="brand", cascade="all, delete-orphan")
    publishing_targets = relationship("PublishingTarget", back_populates="brand", cascade="all, delete-orphan")
    calendar_entries = relationship("CalendarEntry", back_populates="brand", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Brand {self.slug}>"


# ═══════════════════════════════════════════════════════════════
# Users (platform users, not content audience)
# ═══════════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    full_name = Column(String(200))
    role = Column(String(50), default="editor")    # admin / editor / viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    brand = relationship("Brand", back_populates="users")

    def __repr__(self):
        return f"<User {self.email}>"


# ═══════════════════════════════════════════════════════════════
# Publishing Targets (per-brand CMS / platform configs)
# ═══════════════════════════════════════════════════════════════

class PublishingTarget(Base):
    __tablename__ = "publishing_targets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    target_type = Column(String(50), nullable=False)   # shopify / wordpress / postiz / mailchimp / webhook
    label = Column(String(200))                        # "AIS Blog (WordPress)"
    config_json = Column(Text)                         # {"base_url":"...","token":"...","blog_id":"..."}
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    brand = relationship("Brand", back_populates="publishing_targets")

    def __repr__(self):
        return f"<PublishingTarget {self.label}>"


# ═══════════════════════════════════════════════════════════════
# Content Requests (one request → many formats)
# ═══════════════════════════════════════════════════════════════

class ContentRequest(Base):
    __tablename__ = "content_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    request_id = Column(String(50), unique=True, default=generate_uuid)

    # Input fields
    primary_topic = Column(String(500), nullable=False)
    products_to_feature = Column(Text)
    seed_keywords = Column(Text)
    internal_links = Column(Text)                      # JSON array of URLs
    word_count = Column(Integer, default=1500)
    kw_count = Column(Integer, default=10)
    formats = Column(Text)                             # JSON: ["blog","linkedin_carousel","email_newsletter"]
    publish_targets = Column(Text)                     # JSON array of publishing_target IDs
    notify_email = Column(String(200))
    target_market = Column(String(100), default="United States")
    publish_target = Column(String(50), default="Draft only")   # Shopify / WordPress / Webhook / Draft only
    run_mode = Column(String(20), default="demo")               # demo / live

    # State tracking
    status = Column(String(50), default="pending")     # pending / researching / generating / validating / done / failed
    error_message = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime)

    # Relationships
    brand = relationship("Brand", back_populates="content_requests")
    generated_content = relationship("GeneratedContent", back_populates="request", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ContentRequest {self.request_id}>"


# ═══════════════════════════════════════════════════════════════
# Generated Content (one per format per request)
# ═══════════════════════════════════════════════════════════════

class GeneratedContent(Base):
    __tablename__ = "generated_content"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(50), ForeignKey("content_requests.request_id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    format = Column(String(50), nullable=False)        # blog / linkedin_carousel / email_newsletter / etc.

    # SEO metadata
    title = Column(String(500))
    meta_title = Column(String(200))                   # 50-60 chars
    meta_description = Column(String(300))             # 150-160 chars
    slug = Column(String(500))

    # Content bodies
    body_html = Column(Text)                           # main content in HTML
    body_markdown = Column(Text)                       # markdown for social/email
    faq_json = Column(Text)                            # FAQPage JSON-LD
    schema_json = Column(Text)                         # full schema.org JSON-LD

    # Research data used
    keywords = Column(Text)                            # JSON array of keyword objects
    competitor_data = Column(Text)                     # JSON: top 3 organic results
    research_raw = Column(Text)                        # full Serper response for debugging

    # Image generation (Phase 5)
    image_prompt = Column(Text)
    negative_prompt = Column(Text)
    image_url = Column(String(500))
    image_alt = Column(Text)

    # Lifecycle
    status = Column(String(50), default="draft")       # draft / needs_fix / approved / published
    flags = Column(Text)                               # validation flags
    review_notes = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    published_at = Column(DateTime)

    # Relationships
    request = relationship("ContentRequest", back_populates="generated_content")

    def __repr__(self):
        return f"<GeneratedContent {self.format} for {self.request_id}>"


# ═══════════════════════════════════════════════════════════════
# Content Calendar (scheduled topics)
# ═══════════════════════════════════════════════════════════════

class CalendarEntry(Base):
    __tablename__ = "calendar_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    topic = Column(String(500), nullable=False)
    formats = Column(Text)                             # JSON array
    scheduled_date = Column(Date, nullable=False)
    request_id = Column(String(50))                    # populated after generation
    status = Column(String(50), default="planned")     # planned / generated / published / skipped
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    brand = relationship("Brand", back_populates="calendar_entries")

    def __repr__(self):
        return f"<CalendarEntry {self.topic} on {self.scheduled_date}>"


# ═══════════════════════════════════════════════════════════════
# Publish Queue (Outbox pattern — n8n polls this)
# ═══════════════════════════════════════════════════════════════

class PublishQueue(Base):
    __tablename__ = "publish_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("generated_content.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    target_id = Column(Integer, ForeignKey("publishing_targets.id"), nullable=False)
    target_type = Column(String(50))
    payload_json = Column(Text)                        # exact payload for publishing API
    status = Column(String(50), default="queued")      # queued / published / failed
    attempt_count = Column(Integer, default=0)
    last_error = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    published_at = Column(DateTime)

    def __repr__(self):
        return f"<PublishQueue #{self.id} [{self.target_type}] {self.status}>"


# ═══════════════════════════════════════════════════════════════
# Analytics Snapshots (Phase 6)
# ═══════════════════════════════════════════════════════════════

class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("generated_content.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    source = Column(String(50))                        # gsc / linkedin / instagram / mailchimp
    metric_name = Column(String(100))                  # clicks / impressions / ctr / position
    metric_value = Column(Float)
    snapshot_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    def __repr__(self):
        return f"<AnalyticsSnapshot {self.source}.{self.metric_name}={self.metric_value}>"


# Columns added after the first release. SQLite has no online ALTER for these
# through SQLAlchemy, and the demo DB is long-lived, so add them by hand.
_ADDED_COLUMNS = {
    "content_requests": {
        "target_market": "VARCHAR(100)",
        "publish_target": "VARCHAR(50)",
        "run_mode": "VARCHAR(20)",
    },
}


def _apply_pending_columns(engine):
    """Add any missing columns to existing tables. No-op on a fresh database."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in inspector.get_table_names():
                continue
            have = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    print(f"   ➕ Added column {table}.{name}")


def init_db(database_url: str):
    """Create all tables and bring existing ones up to date."""
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    _apply_pending_columns(engine)
    return engine