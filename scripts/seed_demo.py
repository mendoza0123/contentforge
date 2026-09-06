#!/usr/bin/env python
"""
Reset the dashboard to a clean, pitch-ready state.

Wipes every content request for the brand and rebuilds a small back catalogue of
finished runs, so the dashboard has real numbers and the recent list has
something to click into before anyone types a topic.

    ./scripts/seed_demo.py              # rebuild the AIS Technolabs catalogue
    ./scripts/seed_demo.py --if-empty   # seed only if the brand has no runs
    ./scripts/seed_demo.py --wipe       # clear it and leave the dashboard empty

Safe to run repeatedly — it always starts from a clean slate.

The app also calls seed_catalogue_if_empty() at startup, so a fresh database —
which on a serverless host is every cold start — opens on the catalogue with
no manual step.
"""
import argparse
import json
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.demo import seed_items  # noqa: E402
from app.models import (  # noqa: E402
    Brand,
    ContentRequest,
    GeneratedContent,
    generate_uuid,
    get_session,
    init_db,
    utcnow,
)

BRAND_SLUG = "ais-technolabs"

# (days ago, topic, seed keywords, products, word count, formats, published?)
CATALOGUE = [
    (
        21,
        "how to choose white label casino software",
        "white label casino software, casino platform provider, turnkey casino",
        "White-Label Casino Platform, Casino Game Development",
        2000,
        ["blog", "linkedin_carousel", "email_newsletter"],
        True,
    ),
    (
        14,
        "crypto casino software development cost",
        "crypto casino software, bitcoin casino development, web3 gambling platform",
        "Crypto Casino Software, White-Label Casino Platform",
        1500,
        ["blog", "linkedin_carousel"],
        True,
    ),
    (
        9,
        "sportsbook software for cricket betting platforms",
        "cricket betting software, sportsbook platform, sports betting development",
        "Sports Betting Software, iGaming CRM",
        2000,
        ["blog", "email_newsletter"],
        True,
    ),
    (
        5,
        "gaming licence options for new operators",
        "curacao gaming licence, malta gaming authority, kahnawake licence",
        "Gaming Licensing Assistance",
        1500,
        ["blog"],
        False,
    ),
    (
        2,
        "sweepstakes casino platforms in the US market",
        "sweepstakes casino software, social casino platform, US iGaming",
        "Sweepstakes Casino Software",
        1200,
        ["blog", "linkedin_carousel"],
        False,
    ),
]


def clear_catalogue(db, brand) -> tuple:
    """Delete every run for the brand, plus orphaned content from earlier
    manual tests that has no request behind it. Returns (runs, orphans)."""
    request_ids = [
        r.request_id
        for r in db.query(ContentRequest).filter(
            ContentRequest.brand_id == brand.id
        )
    ]
    db.query(GeneratedContent).filter(
        GeneratedContent.request_id.in_(request_ids)
    ).delete(synchronize_session=False)
    db.query(ContentRequest).filter(
        ContentRequest.brand_id == brand.id
    ).delete(synchronize_session=False)
    orphans = (
        db.query(GeneratedContent)
        .filter(
            ~GeneratedContent.request_id.in_(
                db.query(ContentRequest.request_id)
            )
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return len(request_ids), orphans


def build_catalogue(db, brand) -> None:
    """Write the finished runs. Assumes the brand currently has none."""
    now = utcnow()
    for days, topic, keywords, products, words, formats, published in CATALOGUE:
        created = now - timedelta(days=days, hours=3)
        cr = ContentRequest(
            brand_id=brand.id,
            request_id=generate_uuid(),
            primary_topic=topic,
            seed_keywords=keywords,
            products_to_feature=products,
            word_count=words,
            kw_count=12,
            formats=json.dumps(formats),
            target_market="United States",
            publish_target="Draft only",
            run_mode="demo",
            status="done",
            created_at=created,
            completed_at=created + timedelta(minutes=3),
        )
        db.add(cr)
        db.flush()

        seed_items(db, cr, brand.id)
        db.flush()

        for item in db.query(GeneratedContent).filter(
            GeneratedContent.request_id == cr.request_id
        ):
            item.created_at = created + timedelta(minutes=3)
            if published:
                item.status = "published"
                item.published_at = created + timedelta(hours=4)

        print(f"   ✅ {topic}  ({', '.join(formats)})")

    db.commit()


def seed_catalogue_if_empty(db) -> bool:
    """Build the catalogue for a brand that has no runs yet. True if it did.

    Never deletes anything: a live n8n run takes minutes, and this can be the
    first thing a restarted process executes. Closes the session it is given.
    """
    try:
        brand = db.query(Brand).filter(Brand.slug == BRAND_SLUG).first()
        if not brand:
            return False
        existing = (
            db.query(ContentRequest)
            .filter(ContentRequest.brand_id == brand.id)
            .count()
        )
        if existing:
            return False
        build_catalogue(db, brand)
        return True
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="clear the catalogue and leave the dashboard empty",
    )
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="seed only a brand with no runs; never delete existing work",
    )
    args = parser.parse_args()

    engine = init_db(settings.database_url)
    db = get_session(engine)()

    try:
        brand = db.query(Brand).filter(Brand.slug == BRAND_SLUG).first()
        if not brand:
            # A fresh deploy has no database at all, so seeding can run before
            # the app has ever started. Create the brand the app would.
            from app.main import _seed_database

            _seed_database(get_session(engine)())
            db.rollback()
            brand = db.query(Brand).filter(Brand.slug == BRAND_SLUG).first()

        if not brand:
            print(f"❌ No brand with slug '{BRAND_SLUG}'. Start the app once to seed it.")
            return 1

        if args.if_empty:
            existing = (
                db.query(ContentRequest)
                .filter(ContentRequest.brand_id == brand.id)
                .count()
            )
            if existing:
                print(f"✅ {existing} run(s) already here — leaving them alone.")
                return 0

        cleared, orphans = clear_catalogue(db, brand)
        print(f"🧹 Cleared {cleared} request(s) and {orphans} orphaned item(s)")

        if args.wipe:
            print("✅ Dashboard is empty.")
            return 0

        build_catalogue(db, brand)

        totals = (
            db.query(GeneratedContent)
            .filter(GeneratedContent.brand_id == brand.id)
            .count()
        )
        print(f"\n✅ {len(CATALOGUE)} runs · {totals} content items for {brand.name}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
