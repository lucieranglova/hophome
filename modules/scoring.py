"""
scoring.py — Scores each listing from 0 to 100.
Weights are configurable in config.yaml.
"""

import logging

logger = logging.getLogger(__name__)

# Suburb average price fallback (AUD/week) — used if no local data
DEFAULT_AVG_PRICE_WEEK = 550

# Reference max distances for scoring (km)
MAX_CBD_KM   = 30
MAX_BEACH_KM = 60


def score_listing(listing: dict, config: dict) -> float:
    """
    Score a listing from 0 to 100 based on weighted criteria.
    Higher = better deal.
    """
    weights = config["scoring"]["weights"]
    avg_price = config["references"].get("suburb_avg_price_aud_week", DEFAULT_AVG_PRICE_WEEK)

    scores = {}

    # 1. Price vs suburb average (cheaper = higher score)
    price   = listing.get("price_aud_week", avg_price)
    price_ratio = price / avg_price  # < 1 means cheaper than avg
    scores["price_vs_average"] = max(0, min(100, (1 - (price_ratio - 0.6)) * 100))

    # 2. Distance to CBD (closer = higher score)
    dist_cbd = listing.get("dist_cbd_km", MAX_CBD_KM)
    scores["distance_cbd"] = max(0, 100 - (dist_cbd / MAX_CBD_KM) * 100)

    # 3. Distance to beach (closer = higher score)
    dist_beach = listing.get("dist_beach_km", MAX_BEACH_KM)
    scores["distance_beach"] = max(0, 100 - (dist_beach / MAX_BEACH_KM) * 100)

    # 4. Property type (house > apartment)
    prop_type = listing.get("property_type", "apartment")
    scores["property_type"] = 100 if prop_type == "house" else 50

    # 5. Bedrooms (2BR = 50pts, 3BR = 80pts, 4BR+ = 100pts)
    beds = listing.get("bedrooms", 2)
    scores["bedrooms"] = min(100, 30 + beds * 25)

    # Weighted sum
    total_weight = sum(weights.values())
    weighted = sum(
        scores[k] * weights.get(k, 0)
        for k in scores
    )
    final_score = round(weighted / total_weight, 1)

    logger.debug(
        f"{listing.get('id')} score={final_score} "
        f"| price={scores['price_vs_average']:.0f} "
        f"| cbd={scores['distance_cbd']:.0f} "
        f"| beach={scores['distance_beach']:.0f} "
        f"| type={scores['property_type']} "
        f"| beds={scores['bedrooms']}"
    )

    return final_score
