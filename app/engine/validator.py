"""
ContentForge — Compliance Validator
Post-generation quality & compliance scan.
"""
import re
import json
from datetime import datetime, timezone


def validate_content(
    body_html: str,
    brand_facts: str = "",
    banned_terms: str = "",
    compliance_rules: str = "",
) -> dict:
    """
    Scan generated content for compliance violations.
    Returns: {"status": "NEEDS_FIX" | "PENDING_REVIEW", "flags": [str, ...]}
    """
    flags = []

    # 1. Banned terms scan (case-insensitive)
    for term in (banned_terms or "").split(","):
        term = term.strip()
        if term and re.search(re.escape(term), body_html, re.IGNORECASE):
            flags.append(f"banned:{term}")

    # 2. iGaming-specific compliance words (revenue/profit/ROI guarantees)
    gaming_red_flags = [
        r"guaranteed\s+revenue",
        r"guaranteed\s+profit",
        r"guaranteed\s+ROI",
        r"guaranteed\s+players?",
        r"guaranteed\s+returns?",
        r"#1\s+in\s+(the\s+)?industry",
        r"best\s+in\s+the\s+world",
        r"only\s+provider",
        r"cheapest",
    ]
    for pattern in gaming_red_flags:
        if re.search(pattern, body_html, re.IGNORECASE):
            flags.append(f"compliance:{pattern}")

    # 3. Price verification — flag any $/₹ price not found in brand_facts
    prices = re.findall(r'[₹$]\s?[\d,]+(?:\.\d{2})?', body_html)
    flat_facts = (brand_facts or "").replace(" ", "")
    for price in prices:
        price_flat = price.replace(" ", "")
        if price_flat not in flat_facts:
            flags.append(f"unverified-price:{price}")

    # 4. Check for placeholder links (example.com, placeholder URLs)
    if re.search(r'example\.com|placeholder|yourdomain\.com', body_html, re.IGNORECASE):
        flags.append("placeholder-links")

    # Determine status
    status = "NEEDS_FIX" if flags else "PENDING_REVIEW"

    return {
        "status": status,
        "flags": "; ".join(flags) if flags else "",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def force_append_disclaimer(body_html: str, disclaimer: str) -> str:
    """Ensure the compliance disclaimer is present in the body HTML."""
    if not disclaimer:
        return body_html
    # Check if disclaimer's first 30 chars appear anywhere
    if disclaimer[:30].lower() in body_html.lower():
        return body_html
    return body_html + f'\n<p class="disclaimer"><em>{disclaimer}</em></p>'


def parse_json_safe(raw: str) -> dict | None:
    """Safely parse JSON from LLM output, stripping code fences."""
    if not raw:
        return None
    cleaned = re.sub(r"```(?:json)?\s*|```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def extract_content(openai_message) -> str:
    """Extract the text content from an OpenAI-compatible message object,
    handling both choices[0].message.content and direct message.content formats."""
    if isinstance(openai_message, str):
        return openai_message
    if isinstance(openai_message, dict):
        # Try choices format
        choices = openai_message.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            content = msg.get("content", "")
            if content:
                return content
        # Try direct format
        return openai_message.get("message", {}).get("content", "") or openai_message.get("content", "")
    return str(openai_message)


def strip_code_fences(html: str) -> str:
    """Remove markdown code fences from HTML output."""
    html = re.sub(r"^\s*```(?:html)?\s*", "", html, flags=re.IGNORECASE)
    html = re.sub(r"\s*```\s*$", "", html)
    return html