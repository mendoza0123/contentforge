"""
ContentForge — 6-Pass GPT-4o Blog Generation Pipeline
The core content engine. Mirrors the Dhanwantri n8n pipeline in pure Python.
Each pass feeds the output of the previous pass as input.
"""
import json
from openai import OpenAI
from app.config import settings
from app.engine.assembler import GenerationContext
from app.engine.validator import (
    extract_content,
    strip_code_fences,
    parse_json_safe,
)

# ═══════════════════════════════════════════════════════════════
# Pass 1 · Outline
# ═══════════════════════════════════════════════════════════════

PASS1_SYSTEM = """You are an SEO, AEO and GEO content strategist writing for this niche: {niche}.

House structure to follow exactly:
1) Open with a one-sentence bold pull-quote inside a blockquote as the hook.
2) A 3 to 4 paragraph intro that ends with the primary keyword in bold.
3) 4 to 6 H2 sections in a logical arc: Understanding → Why it matters → How it works → deeper H3 sub-sections → Conclusion.
4) Repeat the primary keyword in most headings and throughout the body.
5) Flowing prose paragraphs, minimal or no bullet lists.
6) Do NOT hand-code a Table of Contents; the CMS builds it from headings.
7) Close with a bold brand pull-quote inside a blockquote that names the brand, links to the brand website, and states the call to action.

Return ONLY a JSON object:
{{
  "hook": "pull-quote text",
  "intro": "intro plan (2-3 sentences describing the intro arc)",
  "sections": [
    {{
      "h2": "H2 heading text",
      "h3": ["H3 sub-heading if needed"],
      "key_points": ["Key point 1", "Key point 2"]
    }}
  ],
  "faq_slot": true,
  "disclaimer_slot": true,
  "closing_quote": "brand pull-quote with website link and CTA",
  "keyword_map": {{"primary": "{primary_keyword}", "secondary": ["kw1", "kw2"]}}
}}

{brand_block}

COMPLIANCE:
{compliance}

Voice: {brand_voice}
Never use these words: {banned_terms}"""


def pass1_outline(client: OpenAI, ctx: GenerationContext) -> dict:
    """Pass 1: Generate structured JSON outline with keyword map."""
    system = PASS1_SYSTEM.format(
        niche=ctx.niche,
        primary_keyword=ctx.primary_keyword,
        brand_block=ctx.brand_prompt_block(),
        compliance=ctx.compliance,
        brand_voice=ctx.brand_voice,
        banned_terms=ctx.banned_terms,
    )

    user = ctx.research_block()

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
    )

    raw = extract_content(resp)
    outline = parse_json_safe(raw) or {"raw": raw}
    return outline


# ═══════════════════════════════════════════════════════════════
# Pass 2 · Draft
# ═══════════════════════════════════════════════════════════════

PASS2_SYSTEM = """Expand the OUTLINE into a full blog article in clean semantic HTML (h1,h2,h3,p,blockquote,strong,em,a).

Target {wc_min} to {wc_max} words.

House structure:
1) Open with a one-sentence bold pull-quote inside a blockquote as the hook.
2) A 3 to 4 paragraph intro that ends with the primary keyword in bold.
3) 4 to 6 H2 sections: Understanding → Why it matters → How it works → deeper H3 sub-sections → Conclusion.
4) Repeat the primary keyword in most headings and throughout the body.
5) Flowing prose paragraphs, minimal or no bullet lists.
6) Do NOT hand-code a Table of Contents; the CMS builds it from headings.
7) Close with a bold brand pull-quote inside a blockquote that links to {website} and states the CTA: {cta}

Use brand facts ONLY from context; quote verbatim. Never invent product names, prices, or service descriptions.

{brand_block}

COMPLIANCE:
{compliance}

End the article body with this exact disclaimer paragraph:
{disclaimer}

Output HTML only — no markdown, no code fences."""


def pass2_draft(client: OpenAI, ctx: GenerationContext, outline: dict) -> str:
    """Pass 2: Expand outline into full HTML blog draft."""
    system = PASS2_SYSTEM.format(
        wc_min=ctx.wc_min,
        wc_max=ctx.wc_max,
        website=ctx.website,
        cta=ctx.cta,
        brand_block=ctx.brand_prompt_block(),
        compliance=ctx.compliance,
        disclaimer=ctx.compliance or "",
    )

    outline_text = json.dumps(outline, indent=2)

    user = f"OUTLINE:\n{outline_text}\n\nBRAND & PRODUCT FACTS:\n{ctx.brand_facts}"

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
        max_tokens=4000,
    )

    html = extract_content(resp)
    return strip_code_fences(html)


# ═══════════════════════════════════════════════════════════════
# Pass 3 · SEO Audit
# ═══════════════════════════════════════════════════════════════

PASS3_SYSTEM = """You are a technical SEO editor. Return the corrected full HTML, preserving the house structure (opening pull-quote, H2/H3 arc, closing brand pull-quote, disclaimer).

Fixes to make:
- Keyword density: ~1 to 1.5% (natural, not stuffed)
- Ensure one H1 and logical H2/H3 nesting
- Improve readability (shorter paragraphs, transition phrases)
- Add 2 to 4 internal links as anchor tags using ONLY these URLs where they fit naturally: {internal_links}
- If no URLs are provided, do NOT add or invent any links — never use placeholder or example.com URLs
- Do NOT change any fact, product name, the pull-quotes, or the disclaimer
- Do NOT change the brand name, CTA, or any quoted text

Return HTML only — no markdown, no code fences."""


def pass3_seo_audit(client: OpenAI, ctx: GenerationContext, draft_html: str) -> str:
    """Pass 3: SEO audit — keyword density, heading validation, internal links."""
    system = PASS3_SYSTEM.format(
        internal_links=ctx.internal_links or "(none provided — do not add or invent any links)"
    )

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"DRAFT:\n{draft_html}"},
        ],
        temperature=0.7,
        max_tokens=4000,
    )

    html = extract_content(resp)
    return strip_code_fences(html)


# ═══════════════════════════════════════════════════════════════
# Pass 4 · AEO FAQ
# ═══════════════════════════════════════════════════════════════

PASS4_SYSTEM = """You are an answer-engine optimization specialist. Append an FAQ section just before the conclusion and emit schema.

Return ONLY JSON:
{{
  "body": "the full article HTML with an added FAQ section of 5 to 7 Q and A pairs (use <h2>FAQ</h2><dl><dt>Q</dt><dd>A</dd></dl> format)",
  "faq": [
    {{"q": "Question text", "a": "Answer text"}}
  ],
  "faq_schema": {{FAQPage JSON-LD object}}
}}

Requirements for FAQ answers:
- 40 to 60 words each
- First sentence answers the question outright
- Technology/business framing only (no gambling outcome claims)
- Use natural language someone would type into Google or speak to Siri/Alexa
- Keep the article, pull-quotes, and disclaimer intact in the body field"""


def pass4_aeo_faq(client: OpenAI, ctx: GenerationContext, audited_html: str) -> dict:
    """Pass 4: Append AEO FAQ section + FAQPage JSON-LD schema."""
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": PASS4_SYSTEM},
            {"role": "user", "content": f"ARTICLE:\n{audited_html}\n\nFACTS:\n{ctx.brand_facts}"},
        ],
        temperature=0.7,
        max_tokens=4000,
    )

    raw = extract_content(resp)
    return parse_json_safe(raw) or {"body": audited_html, "faq": [], "faq_schema": {}}


# ═══════════════════════════════════════════════════════════════
# Pass 5 · GEO Structuring
# ═══════════════════════════════════════════════════════════════

PASS5_SYSTEM = """You are a generative-engine optimization strategist (to be cited by ChatGPT, Perplexity, Gemini, Claude).

Enhance the ARTICLE:
1) Add cite-worthy specific statements backed by the brand facts
2) Clarify entity relationships (brand → products → industry → use cases)
3) Add a short "Why Trust Us" block using this author bio: {author_bio}
4) Authoritative or superlative claims allowed ONLY if present in: {approved_claims}
5) Keep the house structure, FAQ, pull-quotes, and disclaimer intact
6) The closing brand pull-quote must link to {website}
7) Use this CTA: {cta}

{brand_block}

COMPLIANCE:
{compliance}

Return the full HTML only — no markdown, no code fences."""


def pass5_geo_structuring(client: OpenAI, ctx: GenerationContext, faq_data: dict) -> str:
    """Pass 5: GEO structuring — authority signals, entities, Why-Trust-Us."""
    article_body = faq_data.get("body", "")

    system = PASS5_SYSTEM.format(
        author_bio=ctx.author_bio,
        approved_claims=ctx.approved_claims,
        website=ctx.website,
        cta=ctx.cta,
        brand_block=ctx.brand_prompt_block(),
        compliance=ctx.compliance,
    )

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"ARTICLE:\n{article_body}"},
        ],
        temperature=0.7,
        max_tokens=4000,
    )

    html = extract_content(resp)
    return strip_code_fences(html)


# ═══════════════════════════════════════════════════════════════
# Pass 6 · Metadata
# ═══════════════════════════════════════════════════════════════

PASS6_SYSTEM = """Return ONLY JSON:
{{
  "meta_title": "50-60 chars including the primary keyword",
  "meta_description": "150-160 chars including the primary keyword",
  "slug": "lowercase-hyphenated-url-friendly",
  "image_alt": ["alt text 1", "alt text 2"],
  "article_schema": {{BlogPosting JSON-LD, author name from the bio, publisher name {brand} }}
}}"""


def pass6_metadata(client: OpenAI, ctx: GenerationContext, final_html: str) -> dict:
    """Pass 6: Generate SEO metadata + BlogPosting JSON-LD schema."""
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": PASS6_SYSTEM.format(brand=ctx.brand)},
            {
                "role": "user",
                "content": f"FINAL ARTICLE:\n{final_html}\nPRIMARY KEYWORD: {ctx.primary_keyword}",
            },
        ],
        temperature=0.7,
    )

    raw = extract_content(resp)
    return parse_json_safe(raw) or {}


# ═══════════════════════════════════════════════════════════════
# Orchestrator: Run full 6-pass pipeline
# ═══════════════════════════════════════════════════════════════

def generate_blog(client: OpenAI, ctx: GenerationContext) -> dict:
    """
    Run the full 6-pass blog generation pipeline.
    Returns a dict with all outputs ready for storage.
    """
    print(f"   📝 Pass 1/6 — Outline...")
    outline = pass1_outline(client, ctx)

    print(f"   📝 Pass 2/6 — Draft...")
    draft_html = pass2_draft(client, ctx, outline)

    print(f"   📝 Pass 3/6 — SEO Audit...")
    audited_html = pass3_seo_audit(client, ctx, draft_html)

    print(f"   📝 Pass 4/6 — AEO FAQ...")
    faq_data = pass4_aeo_faq(client, ctx, audited_html)

    print(f"   📝 Pass 5/6 — GEO Structuring...")
    final_html = pass5_geo_structuring(client, ctx, faq_data)

    print(f"   📝 Pass 6/6 — Metadata...")
    metadata = pass6_metadata(client, ctx, final_html)

    # Extract FAQ body from Pass 4
    faq_body = faq_data.get("body", final_html)
    faq_list = faq_data.get("faq", [])
    faq_schema = faq_data.get("faq_schema", {})

    result = {
        "title": metadata.get("meta_title", ctx.primary_keyword),
        "meta_title": metadata.get("meta_title", ""),
        "meta_description": metadata.get("meta_description", ""),
        "slug": metadata.get("slug", ""),
        "body_html": faq_body,  # use Pass 4's body (includes FAQ)
        "body_markdown": "",  # could convert HTML → MD in future
        "faq_json": json.dumps(faq_list),
        "schema_json": json.dumps({
            "article": metadata.get("article_schema", {}),
            "faq": faq_schema,
        }),
        "image_alt": metadata.get("image_alt", []),
        "keywords": ctx.keywords,
        "primary_keyword": ctx.primary_keyword,
        "competitor_data": json.dumps(ctx.competitors),
    }

    print(f"   ✅ Blog generation complete: {result['title']}")
    return result