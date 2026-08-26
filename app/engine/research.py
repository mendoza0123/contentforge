"""
ContentForge — Research Layer
Serper.dev integration: Google search, People Also Ask, keyword extraction.
Free tier: 2,500 queries/month. No DataForSEO paywall.
"""
import json
import httpx
from app.config import settings

SERPER_URL = "https://google.serper.dev/search"


async def search_serper(query: str, gl: str = "us", hl: str = "en", api_key: str | None = None) -> dict:
    """
    Execute a Google search via Serper.dev.
    Returns: {
        "organic": [{title, link, snippet, position, ...}],
        "peopleAlsoAsk": [{question, snippet, ...}],
        "relatedSearches": [{query}, ...],
        "knowledgeGraph": {...} or null
    }
    """
    key = api_key or settings.serper_api_key
    if not key:
        return {"organic": [], "peopleAlsoAsk": [], "relatedSearches": [], "error": "No Serper API key configured"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            SERPER_URL,
            json={"q": query, "gl": gl, "hl": hl},
            headers={
                "X-API-KEY": key,
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()


def extract_keywords(serper_data: dict) -> list[str]:
    """Extract keyword candidates from Serper results without DataForSEO."""
    pool = set()

    # Related searches
    for r in serper_data.get("relatedSearches", []):
        if r.get("query"):
            pool.add(r["query"])

    # People Also Ask questions
    for q in serper_data.get("peopleAlsoAsk", []):
        if q.get("question"):
            pool.add(q["question"])

    return list(pool)


def score_and_cluster(
    keywords: list[str],
    seed_keywords: str,
    kw_count: int = 10,
) -> dict:
    """
    Score keywords by heuristic relevance, pick top N, extract competitors.
    No DataForSEO volume data — uses positional ranking as proxy.
    Returns: {
        "primary_keyword": str,
        "keywords": [str, ...],
        "competitors": [{title, link, snippet}, ...]
    }
    """
    # Add seed keywords to pool
    pool = set(keywords)
    for k in (seed_keywords or "").split(","):
        k = k.strip()
        if k and len(k) > 3:
            pool.add(k)

    # Simple scoring: longer keywords are more specific = higher score
    # In production, this would use Serper "position" as a weighting factor
    scored = []
    for kw in pool:
        if not kw or len(kw) < 4:
            continue
        score = min(len(kw) / 10.0, 5.0)  # cap at 5.0
        scored.append({"kw": kw, "score": round(score, 2)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:kw_count]
    primary = top[0]["kw"] if top else ""

    return {
        "primary_keyword": primary,
        "keywords": [k["kw"] for k in top],
    }


def extract_competitors(serper_data: dict, limit: int = 3) -> list[dict]:
    """Extract top competitor organic results for content gap analysis."""
    competitors = []
    for r in serper_data.get("organic", [])[:limit]:
        competitors.append({
            "title": r.get("title", ""),
            "link": r.get("link", ""),
            "snippet": r.get("snippet", ""),
        })
    return competitors


class ResearchResult:
    """Structured research output for downstream consumption."""

    def __init__(self, serper_data: dict, seed_keywords: str = "", kw_count: int = 10):
        self.raw = serper_data
        self.organic = serper_data.get("organic", [])
        self.paa = serper_data.get("peopleAlsoAsk", [])
        self.related = serper_data.get("relatedSearches", [])
        self.knowledge = serper_data.get("knowledgeGraph", {})

        keywords = extract_keywords(serper_data)
        clustered = score_and_cluster(keywords, seed_keywords, kw_count)
        self.primary_keyword = clustered["primary_keyword"]
        self.keywords = clustered["keywords"]
        self.competitors = extract_competitors(serper_data)

    def to_dict(self) -> dict:
        return {
            "primary_keyword": self.primary_keyword,
            "keywords": self.keywords,
            "competitors": self.competitors,
            "top_organic": [
                {"title": o.get("title"), "link": o.get("link"), "snippet": o.get("snippet")}
                for o in self.organic[:5]
            ],
            "paa_questions": [q.get("question") for q in self.paa[:10]],
        }