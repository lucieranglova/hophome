"""
scoring.py — Scores each listing from 0 to 100.
Weights are configurable in config.yaml.
Beach proximity is now prioritised.
"""

import logging

logger = logging.getLogger(__name__)

DEFAULT_AVG_PRICE_WEEK = 550
MAX_CBD_KM   = 30
MAX_BEACH_KM = 60


def score_listing(listing: dict, config: dict) -> float:
    weights   = config["scoring"]["weights"]
    avg_price = config["references"].get("suburb_avg_price_aud_week", DEFAULT_AVG_PRICE_WEEK)

    scores = {}

    # 1. Price vs suburb average
    price       = listing.get("price_aud_week", avg_price)
    price_ratio = price / avg_price
    scores["price_vs_average"] = max(0, min(100, (1 - (price_ratio - 0.6)) * 100))

    # 2. Distance to CBD
    dist_cbd = listing.get("dist_cbd_km", MAX_CBD_KM)
    scores["distance_cbd"] = max(0, 100 - (dist_cbd / MAX_CBD_KM) * 100)

    # 3. Distance to beach — higher weight, exponential bonus for < 20km
    dist_beach = listing.get("dist_beach_km", MAX_BEACH_KM)
    beach_score = max(0, 100 - (dist_beach / MAX_BEACH_KM) * 100)
    if dist_beach < 20:
        beach_score = min(100, beach_score * 1.3)  # bonus za blízkost
    scores["distance_beach"] = beach_score

    # 4. Property type
    prop_type = listing.get("property_type", "apartment")
    scores["property_type"] = 100 if prop_type == "house" else 50

    # 5. Bedrooms
    beds = listing.get("bedrooms", 2)
    scores["bedrooms"] = min(100, 30 + beds * 25)

    total_weight = sum(weights.values())
    weighted     = sum(scores[k] * weights.get(k, 0) for k in scores)
    final_score  = round(weighted / total_weight, 1)

    logger.debug(
        f"{listing.get('id')} score={final_score} "
        f"| price={scores['price_vs_average']:.0f} "
        f"| cbd={scores['distance_cbd']:.0f} "
        f"| beach={scores['distance_beach']:.0f} "
        f"| type={scores['property_type']} "
        f"| beds={scores['bedrooms']}"
    )

    return final_score
