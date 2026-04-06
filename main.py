"""
main.py — HopHome orchestrator.
Runs the full pipeline: scrape → enrich → score → detect → alert.
"""

import logging
import sys
import yaml
from pathlib import Path

from modules.database   import init_db, upsert_listing, mark_inactive_except
from modules.scraper    import fetch_listings
from modules.enrichment import enrich
from modules.scoring    import score_listing
from modules.detector   import classify
from modules.alerts     import send_alert, send_summary

# ── Logging setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/hophome.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("hophome.main")


def load_config() -> dict:
    config_path = Path("config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    logger.info("=" * 60)
    logger.info("🦘 HopHome starting...")
    logger.info("=" * 60)

    config = load_config()
    init_db()

    # Step 1: Fetch listings
    logger.info("Step 1/5 — Fetching listings from Domain.com.au...")
    try:
        raw_listings = fetch_listings(config)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        send_summary(0, 0, 0)
        return

    if not raw_listings:
        logger.warning("No listings found. Exiting.")
        send_summary(0, 0, 0)
        return

    logger.info(f"Fetched {len(raw_listings)} listings after filtering.")

    stats = {"total": len(raw_listings), "new": 0, "drops": 0}
    active_ids = []

    for i, listing in enumerate(raw_listings, 1):
        logger.info(f"Processing {i}/{len(raw_listings)}: {listing.get('id')} — {listing.get('suburb')}")

        try:
            # Step 2: Enrich
            listing = enrich(listing, config)

            # Step 3: Score
            listing["score"] = score_listing(listing, config)

            # Step 4: Save to DB
            db_result = upsert_listing(listing)
            active_ids.append(listing["id"])

            # Step 5: Detect alert types
            alert_types = classify(listing, db_result, config)

            # Step 6: Send alerts
            if alert_types:
                send_alert(listing, alert_types)
                if "new" in alert_types:
                    stats["new"] += 1
                if "price_drop" in alert_types:
                    stats["drops"] += 1

        except Exception as e:
            logger.error(f"Error processing listing {listing.get('id')}: {e}", exc_info=True)
            continue

    # Mark listings not seen today as inactive
    mark_inactive_except(active_ids)

    # Daily summary
    logger.info(
        f"Done. Total: {stats['total']} | New: {stats['new']} | Price drops: {stats['drops']}"
    )
    send_summary(stats["total"], stats["new"], stats["drops"])


if __name__ == "__main__":
    main()
