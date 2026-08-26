"""
ContentForge — Generation Orchestrator
Ties research, assembly, generation, validation, and storage together.
"""
import json
import asyncio
from datetime import datetime, timezone
from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Brand, ContentRequest, GeneratedContent
from app.engine.research import search_serper, ResearchResult
from app.engine.assembler import assemble_context
from app.engine.blog import generate_blog
from app.engine.validator import (
    validate_content,
    force_append_disclaimer,
)


async def research_phase(topic: str, seed_keywords: str, brand: Brand) -> dict:
    """Phase 1: Serper research — keyword discovery + competitor analysis."""
    print(f"   🔍 Researching: {topic}")
    serper_data = await search_serper(
        topic,
        gl="us",
        hl="en",
        api_key=brand.serper_api_key or None,
    )

    research = ResearchResult(serper_data, seed_keywords=seed_keywords)
    return research.to_dict()


def generation_phase(brand: Brand, research: dict, form_inputs: dict, openai_key: str) -> dict:
    """Phase 2-4: Assemble context → Generate blog → Validate."""
    ctx = assemble_context(brand, research, form_inputs)
    client = OpenAI(api_key=openai_key or settings.openai_api_key)

    print(f"   🚀 Generating blog for: {ctx.primary_keyword}")
    result = generate_blog(client, ctx)

    # Post-generation compliance validation
    validation = validate_content(
        body_html=result["body_html"],
        brand_facts=ctx.brand_facts,
        banned_terms=ctx.banned_terms,
        compliance_rules=ctx.compliance,
    )

    # Force-append disclaimer if dropped
    result["body_html"] = force_append_disclaimer(
        result["body_html"], ctx.compliance
    )

    result["status"] = validation["status"]
    result["flags"] = validation["flags"]
    result["brand"] = brand.name
    result["publish_target"] = ctx.publish_target
    result["notify_email"] = ctx.notify_email
    result["keyword_list"] = ctx.keywords

    return result


def save_to_db(
    db: Session,
    request_id: str,
    brand: Brand,
    result: dict,
):
    """Persist generated content to the database."""
    # Update content request status
    cr = db.query(ContentRequest).filter(ContentRequest.request_id == request_id).first()
    if cr:
        cr.status = "done"
        cr.completed_at = datetime.now(timezone.utc)

    # Save generated content
    gc = GeneratedContent(
        request_id=request_id,
        brand_id=brand.id,
        format="blog",
        title=result.get("title", ""),
        meta_title=result.get("meta_title", ""),
        meta_description=result.get("meta_description", ""),
        slug=result.get("slug", ""),
        body_html=result.get("body_html", ""),
        faq_json=result.get("faq_json"),
        schema_json=result.get("schema_json"),
        keywords=json.dumps(result.get("keyword_list", [])),
        competitor_data=result.get("competitor_data"),
        research_raw=None,
        image_alt=json.dumps(result.get("image_alt", [])),
        status=result.get("status", "PENDING_REVIEW"),
        flags=result.get("flags", ""),
    )
    db.add(gc)
    db.commit()
    db.refresh(gc)

    print(f"   💾 Saved to DB: {gc.title} [{gc.id}]")
    return gc


async def run_pipeline(
    db: Session,
    request_id: str,
    brand: Brand,
    form_inputs: dict,
):
    """
    Run the complete content generation pipeline:
    Research → Assemble → Generate → Validate → Save
    
    This is the primary orchestrator called by:
    - Webhook endpoint (POST /api/v1/generate)
    - Content Request form (POST /content/new)
    - Future cron/scheduler jobs
    """
    try:
        # Phase 1: Research
        topic = form_inputs.get("primary_topic", "")
        seed_kw = form_inputs.get("seed_keywords", "")
        research = await research_phase(topic, seed_kw, brand)

        # Phase 2-4: Generate + Validate
        result = generation_phase(
            brand=brand,
            research=research,
            form_inputs=form_inputs,
            openai_key=brand.openai_api_key or settings.openai_api_key,
        )

        # Phase 5: Save
        gc = save_to_db(db, request_id, brand, result)

        return {
            "request_id": request_id,
            "status": "done",
            "content_id": gc.id,
            "title": gc.title,
            "slug": gc.slug,
            "content_status": gc.status,
            "flags": gc.flags,
        }

    except Exception as e:
        # Mark request as failed
        cr = db.query(ContentRequest).filter(ContentRequest.request_id == request_id).first()
        if cr:
            cr.status = "failed"
            cr.error_message = str(e)
            db.commit()
        raise