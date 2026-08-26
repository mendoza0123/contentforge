"""
ContentForge — API & Webhook Routes
REST API for n8n integration and programmatic access.
"""
import json
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.main import get_db
from app.models import Brand, ContentRequest, GeneratedContent, generate_uuid
from app.engine.orchestrator import run_pipeline

router = APIRouter(prefix="/api/v1")


# ═══════════════════════════════════════════════════════════════
# External trigger — submit a content request
# ═══════════════════════════════════════════════════════════════

class GenerateRequest(BaseModel):
    brand_slug: str = "ais-technolabs"
    primary_topic: str
    products_to_feature: str | None = None
    seed_keywords: str | None = None
    internal_links: str | None = None
    word_count: int = 1500
    kw_count: int = 10
    formats: str | None = None  # JSON array
    publish_targets: str | None = None  # JSON array
    notify_email: str | None = None


@router.post("/generate")
async def generate_content(body: GenerateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Webhook endpoint: submit a content generation request.
    Returns immediate ack with request_id. Content is generated in the background.
    """
    brand = db.query(Brand).filter(Brand.slug == body.brand_slug, Brand.is_active == True).first()
    if not brand:
        raise HTTPException(status_code=404, detail=f"Brand '{body.brand_slug}' not found")

    request_id = generate_uuid()
    cr = ContentRequest(
        brand_id=brand.id,
        request_id=request_id,
        primary_topic=body.primary_topic,
        products_to_feature=body.products_to_feature,
        seed_keywords=body.seed_keywords,
        internal_links=body.internal_links,
        word_count=body.word_count,
        kw_count=body.kw_count,
        formats=body.formats or json.dumps(["blog", "linkedin_carousel", "email_newsletter"]),
        publish_targets=body.publish_targets,
        notify_email=body.notify_email,
        status="researching",
    )
    db.add(cr)
    db.commit()

    # Fire the pipeline in background
    form_inputs = {
        "primary_topic": body.primary_topic,
        "products_to_feature": body.products_to_feature,
        "seed_keywords": body.seed_keywords,
        "internal_links": body.internal_links,
        "wc_min": max(body.word_count - 300, 800),
        "wc_max": body.word_count + 300,
        "kw_count": body.kw_count,
        "notify_email": body.notify_email,
    }
    background_tasks.add_task(
        _run_pipeline_bg, request_id, brand.id, brand.slug, form_inputs
    )

    return {
        "status": "accepted",
        "request_id": request_id,
        "message": "Content generation started. Poll /api/v1/status/{request_id} for progress.",
    }


def _run_pipeline_bg(request_id: str, brand_id: int, brand_slug: str, form_inputs: dict):
    """Background task: run the full generation pipeline."""
    import asyncio
    from app.models import init_db, get_session, Brand
    from app.config import settings

    engine = init_db(settings.database_url)
    SessionLocal = get_session(engine)
    db = SessionLocal()

    try:
        brand = db.query(Brand).filter(Brand.id == brand_id).first()
        if not brand:
            print(f"   ❌ Brand {brand_id} not found")
            return

        # Run the async pipeline in a sync context
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            run_pipeline(db, request_id, brand, form_inputs)
        )
        loop.close()
        print(f"   ✅ Pipeline complete: {result.get('title', 'untitled')}")
    except Exception as e:
        print(f"   ❌ Pipeline failed for {request_id}: {e}")
        import traceback
        traceback.print_exc()
        # Mark as failed
        from app.models import ContentRequest
        cr = db.query(ContentRequest).filter(ContentRequest.request_id == request_id).first()
        if cr:
            cr.status = "failed"
            cr.error_message = str(e)
            db.commit()
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# Status polling
# ═══════════════════════════════════════════════════════════════

@router.get("/status/{request_id}")
def check_status(request_id: str, db: Session = Depends(get_db)):
    """Poll generation status by request_id."""
    cr = db.query(ContentRequest).filter(ContentRequest.request_id == request_id).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Request not found")

    content = (
        db.query(GeneratedContent)
        .filter(GeneratedContent.request_id == request_id)
        .all()
    )

    return {
        "request_id": request_id,
        "status": cr.status,
        "created_at": cr.created_at.isoformat() if cr.created_at else None,
        "content_count": len(content),
        "formats": [c.format for c in content] if content else [],
    }


# ═══════════════════════════════════════════════════════════════
# n8n Result Receiver — n8n POSTs finished drafts here
# ═══════════════════════════════════════════════════════════════

# n8n's Assemble & Validate node emits its own status vocabulary. Translate it
# into the lifecycle the models and templates use.
_N8N_STATUS = {
    "PENDING_REVIEW": "draft",
    "NEEDS_FIX": "needs_fix",
    "APPROVED": "approved",
    "PUBLISHED": "published",
}


def _normalize_status(raw) -> str:
    if not raw:
        return "draft"
    key = str(raw).strip()
    return _N8N_STATUS.get(key.upper(), key.lower())


@router.post("/webhook/n8n-result")
async def receive_n8n_result(request: Request, db: Session = Depends(get_db)):
    """Receives a finished content draft from the n8n workflow's 'Publish → Webhook' node.
    Expected payload: the full JSON object from n8n's Assemble & Validate node,
    including: request_id, brand, primary_keyword, keywords, title, meta_title,
    meta_description, slug, body_html, faq_json, schema_json, status, flags,
    publish_target, notify_email, image_prompt, negative_prompt, image_alt.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    request_id = payload.get("request_id")
    if not request_id:
        raise HTTPException(status_code=400, detail="Missing request_id")

    payload["status"] = _normalize_status(payload.get("status"))

    # Update the content request status
    cr = db.query(ContentRequest).filter(ContentRequest.request_id == request_id).first()
    if cr:
        cr.status = "done"
        cr.completed_at = datetime.now(timezone.utc)

    # Upsert generated content for blog format
    existing = (
        db.query(GeneratedContent)
        .filter(
            GeneratedContent.request_id == request_id,
            GeneratedContent.format == "blog",
        )
        .first()
    )

    if existing:
        existing.title = payload.get("title", existing.title)
        existing.meta_title = payload.get("meta_title", existing.meta_title)
        existing.meta_description = payload.get("meta_description", existing.meta_description)
        existing.slug = payload.get("slug", existing.slug)
        existing.body_html = payload.get("body_html", existing.body_html)
        existing.faq_json = payload.get("faq_json", existing.faq_json)
        existing.schema_json = payload.get("schema_json", existing.schema_json)
        existing.keywords = payload.get("keywords", existing.keywords)
        existing.status = payload.get("status", "draft")
        existing.flags = payload.get("flags", existing.flags)
        existing.image_prompt = payload.get("image_prompt", existing.image_prompt)
        existing.negative_prompt = payload.get("negative_prompt", existing.negative_prompt)
        existing.image_alt = payload.get("image_alt", existing.image_alt)
        existing.published_at = datetime.now(timezone.utc)
    else:
        brand = db.query(Brand).filter(Brand.name == payload.get("brand")).first()
        gc = GeneratedContent(
            request_id=request_id,
            brand_id=brand.id if brand else (cr.brand_id if cr else 1),
            format="blog",
            title=payload.get("title", ""),
            meta_title=payload.get("meta_title", ""),
            meta_description=payload.get("meta_description", ""),
            slug=payload.get("slug", ""),
            body_html=payload.get("body_html", ""),
            faq_json=payload.get("faq_json"),
            schema_json=payload.get("schema_json"),
            keywords=payload.get("keywords"),
            status=payload.get("status", "draft"),
            flags=payload.get("flags"),
            image_prompt=payload.get("image_prompt"),
            negative_prompt=payload.get("negative_prompt"),
            image_alt=payload.get("image_alt"),
            created_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc),
        )
        db.add(gc)

    db.commit()

    print(f"   📥 Received n8n result for {request_id}: {payload.get('title', 'untitled')}")
    print(f"      Status: {payload.get('status')}, Flags: {payload.get('flags')}")

    return {"status": "ok", "request_id": request_id}


# ═══════════════════════════════════════════════════════════════
# Get full content bundle
# ═══════════════════════════════════════════════════════════════

@router.get("/content/{request_id}")
def get_content(request_id: str, db: Session = Depends(get_db)):
    """Get all generated content for a request."""
    content = (
        db.query(GeneratedContent)
        .filter(GeneratedContent.request_id == request_id)
        .all()
    )
    if not content:
        raise HTTPException(status_code=404, detail="No content found")

    return {
        "request_id": request_id,
        "items": [
            {
                "format": c.format,
                "title": c.title,
                "meta_title": c.meta_title,
                "meta_description": c.meta_description,
                "slug": c.slug,
                "body_html": c.body_html,
                "status": c.status,
                "flags": c.flags,
                "keywords": c.keywords,
                "image_url": c.image_url,
            }
            for c in content
        ],
    }