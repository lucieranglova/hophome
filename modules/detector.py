"""
detector.py — Detects new listings, price drops and high-score deals.
"""

import logging

logger = logging.getLogger(__name__)


def classify(listing: dict, db_result: dict, config: dict) -> list[str]:
    """
    Returns list of alert types for this listing.
    Possible values: "new", "price_drop", "high_score"
    """
    alerts = []
    threshold = config["scoring"]["thresholds"]

    if db_result["is_new"] and config["alerts"]["new_listing"]:
        alerts.append("new")
        logger.info(f"[NEW] {listing['id']} — {listing['suburb']}")

    if db_result["price_dropped"] and config["alerts"]["price_drop"]:
        old  = db_result["old_price"]
        new  = listing["price_aud_week"]
        drop = ((old - new) / old) * 100
        if drop >= threshold["price_drop_pct"]:
            listing["_price_drop_pct"] = round(drop, 1)
            listing["_old_price_week"] = old
            alerts.append("price_drop")
            logger.info(f"[PRICE DROP] {listing['id']} {old:.0f} → {new:.0f} AUD/week ({drop:.1f}%)")

    if listing.get("score", 0) >= threshold["high_score"] and config["alerts"]["high_score"]:
        alerts.append("high_score")
        logger.info(f"[HIGH SCORE] {listing['id']} score={listing['score']}")

    return alerts
