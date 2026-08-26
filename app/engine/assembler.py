"""
ContentForge — Context Assembler
Merges brand profile + research results into a structured context bundle
for consumption by all LLM generation passes.
"""
import json
from app.models import Brand


class GenerationContext:
    """Immutable context bundle passed to every generation pass."""

    def __init__(self, brand: Brand, research: dict, form_inputs: dict | None = None):
        fi = form_inputs or {}

        # Brand identity
        self.brand = brand.name
        self.website = brand.website or ""
        self.niche = brand.niche or ""
        self.brand_voice = brand.brand_voice or ""
        self.brand_facts = brand.brand_facts or ""
        self.approved_claims = brand.approved_claims or ""
        self.banned_terms = brand.banned_terms or ""
        self.author_bio = brand.author_bio or ""
        self.cta = brand.default_cta or ""
        self.compliance = brand.compliance_rules or ""
        self.visual_style = brand.visual_style or ""
        self.brand_colors = brand.brand_colors or ""

        # Topic / keyword
        self.primary_topic = fi.get("primary_topic", research.get("primary_keyword", ""))
        self.primary_keyword = research.get("primary_keyword", self.primary_topic)
        self.keywords = research.get("keywords", [])
        self.competitors = research.get("competitors", [])

        # Content specs
        self.wc_min = fi.get("wc_min", 1200)
        self.wc_max = fi.get("wc_max", 1800)
        self.kw_count = fi.get("kw_count", 10)
        self.internal_links = fi.get("internal_links", "")
        self.publish_target = fi.get("publish_target", "Draft to webhook only")
        self.notify_email = fi.get("notify_email", "")

    def brand_prompt_block(self) -> str:
        """The brand grounding block injected into every LLM system prompt."""
        return (
            f"You are writing for {self.brand} ({self.website}).\n"
            f"Niche: {self.niche}\n"
            f"Brand Voice: {self.brand_voice}\n\n"
            f"KEY BRAND & PRODUCT FACTS (quote verbatim, never invent):\n{self.brand_facts}\n\n"
            f"APPROVED CLAIMS (may use):\n{self.approved_claims}\n\n"
            f"BANNED TERMS (never use): {self.banned_terms}\n\n"
            f"AUTHOR BIO: {self.author_bio}\n"
            f"CALL TO ACTION: {self.cta}\n\n"
            f"COMPLIANCE:\n{self.compliance}"
        )

    def competitor_block(self) -> str:
        """Competitor angle block for the outline pass."""
        if not self.competitors:
            return ""
        return "COMPETITOR ANGLES (beat, do not copy):\n" + json.dumps(self.competitors)

    def research_block(self) -> str:
        """Full research context for the user message."""
        return (
            f"PRIMARY KEYWORD: {self.primary_keyword}\n"
            f"SECONDARY KEYWORDS: {', '.join(self.keywords)}\n"
            f"{self.competitor_block()}\n"
            f"BRAND & PRODUCT FACTS (ground everything in these):\n{self.brand_facts}"
        )

    def to_dict(self) -> dict:
        return {
            "brand": self.brand,
            "website": self.website,
            "niche": self.niche,
            "primary_keyword": self.primary_keyword,
            "keywords": self.keywords,
            "competitors": self.competitors,
            "wc_min": self.wc_min,
            "wc_max": self.wc_max,
            "internal_links": self.internal_links,
            "publish_target": self.publish_target,
        }


def assemble_context(brand: Brand, research: dict, form_inputs: dict | None = None) -> GenerationContext:
    """Factory: create a GenerationContext from brand + research + form inputs."""
    return GenerationContext(brand, research, form_inputs)