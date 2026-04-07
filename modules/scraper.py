"""
scraper.py — Fetches rental listings from Domain.com.au official API.
Falls back to mock data when Production access is pending.
"""

import logging
import os
import re
import requests

logger = logging.getLogger(__name__)

DOMAIN_CLIENT_ID     = os.environ.get("DOMAIN_CLIENT_ID")
DOMAIN_CLIENT_SECRET = os.environ.get("DOMAIN_CLIENT_SECRET")

TOKEN_URL  = "https://auth.domain.com.au/v1/connect/token"
SEARCH_URL = "https://api.domain.com.au/v1/listings/residential/_search"

# ---------------------------------------------------------------------------
# Mock listings — used for testing until Production API access is approved
# ---------------------------------------------------------------------------
MOCK_LISTINGS = [
    {
        "id": "mock-001",
        "title": "47 Fig Tree Pocket Rd, Fig Tree Pocket",
        "price_aud_week":  480,
        "price_aud_month": 2078,
        "property_type":   "house",
        "suburb":          "Fig Tree Pocket",
        "bedrooms":        3,
        "url":             "https://www.domain.com.au/mock-001",
        "image_url":       "",
        "inspection_date": "2026-04-12",
        "lat": -27.5259,
        "lon": 152.9642,
    },
    {
        "id": "mock-002",
        "title": "12/45 Brookes St, Fortitude Valley",
        "price_aud_week":  550,
        "price_aud_month": 2381,
        "property_type":   "apartment",
        "suburb":          "Fortitude Valley",
        "bedrooms":        2,
        "url":             "https://www.domain.com.au/mock-002",
        "image_url":       "",
        "inspection_date": "2026-04-13",
        "lat": -27.4561,
        "lon": 153.0390,
    },
    {
        "id": "mock-003",
        "title": "8 Raven St, Camp Hill",
        "price_aud_week":  420,
        "price_aud_month": 1818,
        "property_type":   "house",
        "suburb":          "Camp Hill",
        "bedrooms":        3,
        "url":             "https://www.domain.com.au/mock-003",
        "image_url":       "",
        "inspection_date": "2026-04-12",
        "lat": -27.4897,
        "lon": 153.0671,
    },
    {
        "id": "mock-004",
        "title": "3/22 Water St, Graceville",
        "price_aud_week":  390,
        "price_aud_month": 1688,
        "property_type":   "apartment",
        "suburb":          "Graceville",
        "bedrooms":        2,
        "url":             "https://www.domain.com.au/mock-004",
        "image_url":       "",
        "inspection_date": "2026-04-14",
        "lat": -27.5147,
        "lon": 152.9993,
    },
    {
        "id": "mock-005",
        "title": "15 Outlook Cres, Bardon",
        "price_aud_week":  575,
        "price_aud_month": 2489,
        "property_type":   "house",
        "suburb":          "Bardon",
        "bedrooms":        4,
        "url":             "https://www.domain.com.au/mock-005",
        "image_url":       "",
        "inspection_date": "2026-04-13",
        "lat": -27.4581,
        "lon": 152.9881,
    },
]


def get_access_token() -> str:
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type":    "client_credentials",
            "client_id":     DOMAIN_CLIENT_ID,
            "client_secret": DOMAIN_CLIENT_SECRET,
            "scope":         "api_listings_read api_agencies_read",
        },
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    logger.info("Domain API token obtained.")
    return token


def fetch_listings(config: dict) -> list[dict]:
    if not DOMAIN_CLIENT_ID or not DOMAIN_CLIENT_SECRET:
        logger.warning("Missing Domain API credentials — using mock data.")
        return _get_mock_listings(config)

    try:
        token   = get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }
        listings = _fetch_from_api(headers, config)
        if not listings:
            logger.warning("API returned 0 listings — falling back to mock data.")
            return _get_mock_listings(config)
        return listings
    except Exception as e:
        logger.error(f"API fetch failed: {e} — falling back to mock data.")
        return _get_mock_listings(config)


def _get_mock_listings(config: dict) -> list[dict]:
    logger.info("Using MOCK listings for testing.")
    max_week     = config["filters"]["max_price_aud_month"] / 4.33
    min_bedrooms = config["filters"]["min_bedrooms"]
    allowed      = config["filters"]["property_types"]
    return [
        l for l in MOCK_LISTINGS
        if l["price_aud_week"] <= max_week
        and l["bedrooms"] >= min_bedrooms
        and l["property_type"] in allowed
    ]


def _fetch_from_api(headers: dict, config: dict) -> list[dict]:
    max_price_week = int(config["filters"]["max_price_aud_month"] / 4.33)
    min_bedrooms   = config["filters"]["min_bedrooms"]
    all_listings   = []
    page           = 1
    page_size      = 20

    while True:
        payload = {
            "listingType": "Rent",
            "pageSize":    page_size,
            "pageNumber":  page,
            "locations": [{
                "state":                     "QLD",
                "region":                    "",
                "area":                      "",
                "suburb":                    "",
                "postCode":                  "",
                "includeSurroundingSuburbs": True,
            }],
            "rental": {
                "maxRent":     max_price_week,
                "minBedrooms": min_bedrooms,
            },
            "propertyTypes": ["House", "ApartmentUnitFlat", "Townhouse", "Villa", "Duplex"],
            "sort": {"sortKey": "DateListed", "direction": "Descending"},
        }

        logger.info(f"Fetching page {page} from Domain API...")
        resp = requests.post(SEARCH_URL, json=payload, headers=headers, timeout=20)

        if not resp.ok:
            logger.error(f"Domain API error {resp.status_code}: {resp.text[:500]}")
            break

        data = resp.json()
        if not data:
            break

        for item in data:
            listing = _normalise(item)
            if listing:
                all_listings.append(listing)

        logger.info(f"Page {page}: {len(data)} results (total {len(all_listings)})")

        if len(data) < page_size or page >= 5:
            break
        page += 1

    allowed = config["filters"]["property_types"]
    return [l for l in all_listings if l["property_type"] in allowed]


def _normalise(item: dict) -> dict | None:
    try:
        listing = item.get("listing", item)
        price_d = listing.get("priceDetails", {})
        prop_d  = listing.get("propertyDetails", {})
        media   = listing.get("media", [])

        listing_id = str(listing.get("id", ""))
        if not listing_id:
            return None

        price_week = _extract_price(price_d)
        if not price_week:
            return None

        raw_type  = prop_d.get("propertyType", "").lower()
        prop_type = "house" if any(
            w in raw_type for w in ["house", "townhouse", "villa", "duplex", "terrace"]
        ) else "apartment"

        suburb   = prop_d.get("suburb", "") or prop_d.get("displayableAddress", "Brisbane")
        bedrooms = int(prop_d.get("bedrooms", 0) or 0)

        image_url = ""
        for m in media:
            if m.get("category") == "Image":
                image_url = m.get("url", "")
                break

        inspections     = listing.get("inspectionDetails", {}).get("inspections", [])
        inspection_date = inspections[0].get("openingDateTime", "")[:10] if inspections else ""

        slug = listing.get("listingSlug", "")
        url  = f"https://www.domain.com.au/{slug}" if slug else f"https://www.domain.com.au/listing/{listing_id}"

        return {
            "id":              listing_id,
            "title":           prop_d.get("displayableAddress", suburb),
            "price_aud_week":  price_week,
            "price_aud_month": round(price_week * 4.33),
            "property_type":   prop_type,
            "suburb":          suburb,
            "bedrooms":        bedrooms,
            "url":             url,
            "image_url":       image_url,
            "inspection_date": inspection_date,
            "lat":             prop_d.get("latitude"),
            "lon":             prop_d.get("longitude"),
        }
    except Exception as e:
        logger.warning(f"Error normalising listing: {e}")
        return None


def _extract_price(price_d: dict) -> float | None:
    price = price_d.get("price") or price_d.get("priceFrom")
    if price:
        return float(price)
    display = price_d.get("displayPrice", "")
    match   = re.search(r"\$?([\d,]+)", display.replace(",", ""))
    if match:
        price = float(match.group(1))
        return price / 4.33 if price > 3000 else price
    return None
