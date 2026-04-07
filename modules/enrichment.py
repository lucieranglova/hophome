"""
enrichment.py — Enriches listings with distance, transport and kangaroo data.
"""

import logging
import requests
from geopy.distance import geodesic

logger = logging.getLogger(__name__)

# Brisbane CBD coords
CBD   = (-27.4698, 153.0251)
BEACH = (-27.9944, 153.4306)  # Surfers Paradise

# Travel speeds (km/h)
BUS_SPEED_KMH   = 25
TRAIN_SPEED_KMH = 40

# Brisbane train lines by suburb keyword mapping
TRAIN_LINES = {
    "ferny grove": "Ferny Grove line", "keperra": "Ferny Grove line",
    "mitchelton": "Ferny Grove line", "ashgrove": "Ferny Grove line",
    "bardon": "Ferny Grove line",
    "ipswich": "Ipswich line", "oxley": "Ipswich line",
    "darra": "Ipswich line", "wacol": "Ipswich line",
    "springfield": "Springfield line", "richlands": "Springfield line",
    "indooroopilly": "Ipswich/Springfield line",
    "toowong": "Ipswich/Springfield line",
    "gold coast": "Gold Coast line", "beenleigh": "Beenleigh line",
    "logan": "Beenleigh line", "woodridge": "Beenleigh line",
    "browns plains": "Beenleigh line",
    "sunshine coast": "Sunshine Coast line", "nambour": "Sunshine Coast line",
    "caboolture": "Caboolture line", "petrie": "Caboolture line",
    "redcliffe": "Redcliffe Peninsula line", "kippa-ring": "Redcliffe Peninsula line",
    "shorncliffe": "Shorncliffe line", "sandgate": "Shorncliffe line",
    "doomben": "Doomben line", "ascot": "Doomben line",
    "cleveland": "Cleveland line", "manly": "Cleveland line",
    "wynnum": "Cleveland line", "cannon hill": "Cleveland line",
    "fortitude valley": "City loop", "central": "City loop",
    "roma street": "City loop", "south brisbane": "City loop",
}

# Atlas of Living Australia — kangaroo sightings
ALA_URL = (
    "https://biocache-ws.ala.org.au/ws/occurrences/search"
    "?q=Macropus+giganteus"
    "&fq=state:Queensland"
    "&fq=decade:2020"
    "&pageSize=0&facet=on&facets=cl10158&flimit=1000"
)

_ala_cache: dict[str, int] | None = None


def enrich(listing: dict, config: dict) -> dict:
    """Add distance, transport, school, hospital and kangaroo data."""
    lat = listing.get("lat")
    lon = listing.get("lon")

    if not lat or not lon:
        lat, lon = geocode_suburb(listing["suburb"])
        listing["lat"] = lat
        listing["lon"] = lon

    if lat and lon:
        coords     = (lat, lon)
        dist_cbd   = round(geodesic(coords, CBD).km,   1)
        dist_beach = round(geodesic(coords, BEACH).km, 1)
    else:
        dist_cbd   = 15.0
        dist_beach = 50.0

    listing["dist_cbd_km"]   = dist_cbd
    listing["dist_beach_km"] = dist_beach

    # Transit times + MHD line name
    listing["transit_cbd_min"],   listing["transit_cbd_mode"]   = estimate_transit(listing["suburb"], dist_cbd,   "cbd")
    listing["transit_beach_min"], listing["transit_beach_mode"] = estimate_transit(listing["suburb"], dist_beach, "beach")

    # Optional — school and hospital
    enrichment_cfg = config.get("enrichment", {})
    if enrichment_cfg.get("show_school") and lat and lon:
        dist_s, name_s = find_nearest_amenity(lat, lon, "school")
        listing["dist_school_km"]  = dist_s
        listing["nearest_school"]  = name_s
    else:
        listing["dist_school_km"]  = None
        listing["nearest_school"]  = None

    if enrichment_cfg.get("show_hospital") and lat and lon:
        dist_h, name_h = find_nearest_amenity(lat, lon, "hospital")
        listing["dist_hospital_km"] = dist_h
        listing["nearest_hospital"] = name_h
    else:
        listing["dist_hospital_km"] = None
        listing["nearest_hospital"] = None

    listing["kangaroo_chance"] = get_kangaroo_chance(listing["suburb"])

    return listing


def estimate_transit(suburb: str, dist_km: float, dest: str) -> tuple[int, str]:
    """Returns (minutes, mode_label) for transit estimate."""
    suburb_lower = suburb.lower()

    # Check if suburb is on a train line
    line = None
    for keyword, line_name in TRAIN_LINES.items():
        if keyword in suburb_lower:
            line = line_name
            break

    if line and dest == "cbd":
        speed = TRAIN_SPEED_KMH
        wait  = 8
        mode  = f"🚆 {line}"
    else:
        speed = BUS_SPEED_KMH
        wait  = 12
        mode  = "🚌 Bus"

    minutes = int(round((dist_km / speed) * 60 + wait))
    return minutes, mode


def find_nearest_amenity(lat: float, lon: float, amenity: str) -> tuple[float | None, str]:
    """
    Find nearest school or hospital using Overpass API (OpenStreetMap).
    Returns (distance_km, name).
    """
    try:
        query = f"""
        [out:json][timeout:10];
        node[amenity={amenity}](around:10000,{lat},{lon});
        out 1;
        """
        resp = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query,
            headers={"User-Agent": "HopHome/1.0"},
            timeout=12,
        )
        data = resp.json()
        elements = data.get("elements", [])
        if not elements:
            return None, f"No {amenity} found nearby"

        el   = elements[0]
        name = el.get("tags", {}).get("name", amenity.capitalize())
        dist = round(geodesic((lat, lon), (el["lat"], el["lon"])).km, 1)
        return dist, name

    except Exception as e:
        logger.warning(f"Overpass {amenity} lookup failed: {e}")
        return None, f"{amenity.capitalize()} data unavailable"


def geocode_suburb(suburb: str) -> tuple[float | None, float | None]:
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{suburb}, Brisbane, Queensland, Australia", "format": "json", "limit": 1},
            headers={"User-Agent": "HopHome/1.0"},
            timeout=10,
        )
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        logger.warning(f"Geocoding failed for {suburb}: {e}")
    return None, None


def get_kangaroo_chance(suburb: str) -> str:
    global _ala_cache
    if _ala_cache is None:
        _ala_cache = _fetch_ala_sightings()

    suburb_clean = suburb.lower().split(" qld")[0].strip()
    count = _ala_cache.get(suburb_clean, 0)

    if count == 0:
        outer_keywords = ["forest", "mountain", "hills", "creek", "valley", "park", "heights"]
        if any(w in suburb_clean for w in outer_keywords):
            return "MEDIUM 😮"
        return "LOW 😓"
    elif count < 5:
        return "MEDIUM 😮"
    return "HIGH 🤩"


def _fetch_ala_sightings() -> dict[str, int]:
    try:
        resp   = requests.get(ALA_URL, timeout=15)
        data   = resp.json()
        counts = {}
        for facet in data.get("facetResults", []):
            if facet.get("fieldName") == "cl10158":
                for item in facet.get("fieldResult", []):
                    counts[item.get("label", "").lower()] = item.get("count", 0)
        logger.info(f"ALA: loaded sightings for {len(counts)} suburbs.")
        return counts
    except Exception as e:
        logger.warning(f"ALA fetch failed: {e}. Using heuristics.")
        return {}
