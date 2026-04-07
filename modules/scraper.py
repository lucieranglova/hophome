"""
scraper.py — Fetches rental listings from Domain.com.au official API.
Docs: https://developer.domain.com.au/docs/apis/pkg_agents_listings/references/listings_detailedresidentialsearch
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


def get_access_token() -> str:
    """Fetch OAuth2 access token from Domain."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type":    "client_credentials",
            "client_id":     DOMAIN_CLIENT_ID,
            "client_secret": DOMAIN_CLIENT_SECRET,
            "scope":         "api_listings_read",
        },
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    logger.info("Domain API token obtained.")
    return token


def fetch_listings(config: dict) -> list[dict]:
    """
    Fetch rental listings from Domain API.
    Returns list of normalised listing dicts matching filters.
    """
    if not DOMAIN_CLIENT_ID or not DOMAIN_CLIENT_SECRET:
        raise ValueError("Missing DOMAIN_CLIENT_ID or DOMAIN_CLIENT_SECRET")

    max_price_month = config["filters"]["max_price_aud_month"]
    max_price_week  = int(max_price_month / 4.33)
    min_bedrooms    = config["filters"]["min_bedrooms"]

    token    = get_access_token()
    headers  = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    all_listings = []
    page         = 1
    page_size    = 20

    while True:
        payload = {
            "listingType": "Rent",
            "pageSize":    page_size,
            "pageNumber":  page,
            "locations": [{
                "state":            "QLD",
                "region":           "",
                "area":             "",
                "suburb":           "",
                "postCode":         "",
                "includeSurroundingSuburbs": True,
            }],
            "rental": {
                "maxRent":     max_price_week,
                "minBedrooms": min_bedrooms,
            },
            "propertyTypes": ["House", "ApartmentUnitFlat", "Townhouse", "Villa", "Duplex"],
            "sort": {
                "sortKey":   "DateListed",
                "direction": "Descending",
            },
        }

        logger.info(f"Fetching page {page} from Domain API...")
        resp = requests.post(SEARCH_URL, json=payload, headers=headers, timeout=20)

        if resp.status_code == 401:
            logger.error("Domain API: Unauthorized. Check credentials.")
            break
        if not resp.ok:
            logger.error(f"Domain API error {resp.status_code}: {resp.text[:200]}")
            break

        data = resp.json()
        if not data:
            logger.info(f"No more results on page {page}.")
            break

        for item in data:
            listing = _normalise(item)
            if listing:
                all_listings.append(listing)

        logger.info(f"Page {page}: {len(data)} results (total {len(all_listings)})")

        if len(data) < page_size or page >= 5:
            break

        page += 1

    # Filter by property type
    allowed  = config["filters"]["property_types"]
    filtered = [l for l in all_listings if l["property_type"] in allowed]

    logger.info(f"Total: {len(all_listings)} listings, {len(filtered)} after type filter.")
    return filtered


def _normalise(item: dict) -> dict | None:
    """Convert Domain API response to HopHome listing format."""
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
        inspection_date = ""
        if inspections:
            inspection_date = inspections[0].get("openingDateTime", "")[:10]

        slug = listing.get("listingSlug", "")
        url  = f"https://www.domain.com.au/{slug}" if slug else f"https://www.domain.com.au/listing/{listing_id}"

        lat = prop_d.get("latitude")
        lon = prop_d.get("longitude")

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
            "lat":             lat,
            "lon":             lon,
        }

    except Exception as e:
        logger.warning(f"Error normalising listing: {e}")
        return None


def _extract_price(price_d: dict) -> float | None:
    """Extract weekly price in AUD from Domain price details."""
    price = price_d.get("price") or price_d.get("priceFrom")
    if price:
        return float(price)

    display = price_d.get("displayPrice", "")
    match   = re.search(r"\$?([\d,]+)", display.replace(",", ""))
    if match:
        price = float(match.group(1))
        if price > 3000:
            price = price / 4.33
        return price

    return None
