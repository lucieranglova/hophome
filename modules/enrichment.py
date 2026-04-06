"""
enrichment.py — Enriches listings with distance, transport and kangaroo data.
"""

import logging
import requests
from geopy.distance import geodesic

logger = logging.getLogger(__name__)

# Brisbane CBD coords
CBD = (-27.4698, 153.0251)
# Gold Coast beach (Surfers Paradise) as nearest beach reference
BEACH = (-27.9944, 153.4306)

# Average travel speeds for estimation (km/h)
BUS_SPEED_KMH   = 25
TRAIN_SPEED_KMH = 40

# Atlas of Living Australia — kangaroo sightings API
ALA_URL = (
    "https://biocache-ws.ala.org.au/ws/occurrences/search"
    "?q=Macropus+giganteus"
    "&fq=state:Queensland"
    "&fq=decade:2020"
    "&pageSize=0"
    "&facet=on"
    "&facets=cl10158"  # suburb facet
    "&flimit=1000"
)

# Cache ALA results for the run
_ala_cache: dict[str, int] | None = None


def enrich(listing: dict, config: dict) -> dict:
    """Add distance, transport and kangaroo data to listing."""
    lat = listing.get("lat")
    lon = listing.get("lon")

    # Geocode suburb if no coordinates
    if not lat or not lon:
        lat, lon = geocode_suburb(listing["suburb"])
        listing["lat"] = lat
        listing["lon"] = lon

    if lat and lon:
        coords = (lat, lon)
        dist_cbd   = round(geodesic(coords, CBD).km,   1)
        dist_beach = round(geodesic(coords, BEACH).km, 1)
    else:
        dist_cbd   = 15.0  # fallback
        dist_beach = 50.0

    listing["dist_cbd_km"]   = dist_cbd
    listing["dist_beach_km"] = dist_beach

    # Estimate transit times
    listing["transit_cbd_min"]   = estimate_transit_min(dist_cbd,   mode="train")
    listing["transit_beach_min"] = estimate_transit_min(dist_beach, mode="bus")

    # Kangaroo chance
    listing["kangaroo_chance"] = get_kangaroo_chance(listing["suburb"])

    return listing


def geocode_suburb(suburb: str) -> tuple[float | None, float | None]:
    """Use Nominatim (free, no key) to geocode suburb."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": f"{suburb}, Brisbane, Queensland, Australia",
            "format": "json",
            "limit": 1,
        }
        headers = {"User-Agent": "HopHome/1.0 (rental-tracker)"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        logger.warning(f"Geocoding failed for {suburb}: {e}")
    return None, None


def estimate_transit_min(dist_km: float, mode: str = "bus") -> int:
    """Rough transit time estimate including waiting time."""
    speed = TRAIN_SPEED_KMH if mode == "train" else BUS_SPEED_KMH
    travel = (dist_km / speed) * 60
    wait   = 8 if mode == "train" else 12  # avg waiting time
    return int(round(travel + wait))


def get_kangaroo_chance(suburb: str) -> str:
    """
    Returns LOW / MEDIUM / HIGH based on kangaroo sightings
    from Atlas of Living Australia near the suburb.
    Uses a simple keyword-based heuristic as fallback.
    """
    global _ala_cache

    if _ala_cache is None:
        _ala_cache = _fetch_ala_sightings()

    suburb_clean = suburb.lower().split(" qld")[0].strip()
    count = _ala_cache.get(suburb_clean, 0)

    if count == 0:
        # Fallback heuristic — outer suburbs more likely
        outer_keywords = ["forest", "mountain", "hills", "creek", "valley", "park", "heights"]
        if any(w in suburb_clean for w in outer_keywords):
            return "MEDIUM 😮"
        return "LOW 😓"
    elif count < 5:
        return "MEDIUM 😮"
    else:
        return "HIGH 🤩"


def _fetch_ala_sightings() -> dict[str, int]:
    """Fetch kangaroo sighting counts by suburb from ALA."""
    try:
        resp = requests.get(ALA_URL, timeout=15)
        data = resp.json()
        counts = {}
        facets = data.get("facetResults", [])
        for facet in facets:
            if facet.get("fieldName") == "cl10158":
                for item in facet.get("fieldResult", []):
                    label = item.get("label", "").lower()
                    count = item.get("count", 0)
                    counts[label] = count
        logger.info(f"ALA: loaded sightings for {len(counts)} suburbs.")
        return counts
    except Exception as e:
        logger.warning(f"ALA fetch failed: {e}. Using heuristics.")
        return {}
