"""
ContentForge — Pydantic Schemas
Request/response validation for the API.
"""
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ═══════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    brand_id: int
    brand_slug: str
    user_name: str
    role: str


# ═══════════════════════════════════════════════════════════════
# Brand
# ═══════════════════════════════════════════════════════════════

class BrandCreate(BaseModel):
    name: str
    slug: str
    website: Optional[str] = None
    niche: Optional[str] = None
    brand_voice: Optional[str] = None
    brand_facts: Optional[str] = None
    approved_claims: Optional[str] = None
    banned_terms: Optional[str] = None
    compliance_rules: Optional[str] = None
    author_bio: Optional[str] = None
    default_cta: Optional[str] = None
    target_markets: Optional[str] = None
    default_language: str = "English"
    visual_style: Optional[str] = None
    brand_colors: Optional[str] = None


class BrandUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    niche: Optional[str] = None
    brand_voice: Optional[str] = None
    brand_facts: Optional[str] = None
    approved_claims: Optional[str] = None
    banned_terms: Optional[str] = None
    compliance_rules: Optional[str] = None
    author_bio: Optional[str] = None
    default_cta: Optional[str] = None
    target_markets: Optional[str] = None
    default_language: Optional[str] = None
    visual_style: Optional[str] = None
    brand_colors: Optional[str] = None


class BrandOut(BaseModel):
    id: int
    name: str
    slug: str
    website: Optional[str]
    niche: Optional[str]
    brand_voice: Optional[str]
    brand_facts: Optional[str]
    approved_claims: Optional[str]
    banned_terms: Optional[str]
    compliance_rules: Optional[str]
    author_bio: Optional[str]
    default_cta: Optional[str]
    target_markets: Optional[str]
    default_language: str
    visual_style: Optional[str]
    brand_colors: Optional[str]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# Content Request
# ═══════════════════════════════════════════════════════════════

class ContentRequestCreate(BaseModel):
    primary_topic: str
    products_to_feature: Optional[str] = None
    seed_keywords: Optional[str] = None
    internal_links: Optional[List[str]] = None
    word_count: int = 1500
    kw_count: int = 10
    formats: List[str] = Field(
        default_factory=lambda: ["blog", "linkedin_carousel", "email_newsletter"]
    )
    publish_targets: Optional[List[int]] = None
    notify_email: Optional[str] = None


class ContentRequestOut(BaseModel):
    request_id: str
    primary_topic: str
    formats: List[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# Generated Content
# ═══════════════════════════════════════════════════════════════

class GeneratedContentOut(BaseModel):
    id: int
    request_id: str
    format: str
    title: Optional[str]
    meta_title: Optional[str]
    meta_description: Optional[str]
    slug: Optional[str]
    body_html: Optional[str]
    body_markdown: Optional[str]
    faq_json: Optional[str]
    schema_json: Optional[str]
    status: str
    flags: Optional[str]
    image_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# Publishing
# ═══════════════════════════════════════════════════════════════

class PublishingTargetCreate(BaseModel):
    target_type: str
    label: Optional[str] = None
    config_json: Optional[str] = None


class PublishingTargetOut(BaseModel):
    id: int
    target_type: str
    label: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# Webhook responses
# ═══════════════════════════════════════════════════════════════

class GenerateAck(BaseModel):
    status: str = "accepted"
    message: str
    request_id: str