"""
scraper.py — Fetches rental listings from Domain.com.au
Filters by price, bedrooms and property type per config.
"""

import logging
import re
import time
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-AU,en;q=0.9",
}

BASE_URL = "https://www.domain.com.au"


def fetch_listings(config: dict) -> list[dict]:
    """
    Scrape rental listings from Domain.com.au.
    Returns list of raw listing dicts matching filters.
    """
    max_price_week = config["filters"]["max_price_aud_month"] / 4.33
    min_bedrooms   = config["filters"]["min_bedrooms"]

    all_listings = []
    page = 1

    while True:
        url = _build_url(min_bedrooms, max_price_week, page)
        logger.info(f"Scraping page {page}: {url}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Scraping error on page {page}: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        listings = _parse_page(soup)

        if not listings:
            logger.info(f"No more listings on page {page}. Done.")
            break

        all_listings.extend(listings)
        logger.info(f"Page {page}: found {len(listings)} listings (total {len(all_listings)})")

        # Stop after 5 pages to avoid hammering the server
        if page >= 5:
            break

        page += 1
        time.sleep(2)  # polite delay

    # Apply filters
    filtered = [
        l for l in all_listings
        if l["bedrooms"] >= min_bedrooms
        and l["price_aud_week"] <= max_price_week
        and l["property_type"] in config["filters"]["property_types"]
    ]

    logger.info(f"Fetched {len(all_listings)} listings, {len(filtered)} after filtering.")
    return filtered


def _build_url(min_bedrooms: int, max_price_week: float, page: int) -> str:
    max_price_rounded = int(round(max_price_week / 50) * 50)
    url = (
        f"{BASE_URL}/rent/brisbane-region-qld/"
        f"?bedrooms={min_bedrooms}-any"
        f"&price=0-{max_price_rounded}"
        f"&excludedeposittaken=1"
        f"&page={page}"
    )
    return url


def _parse_page(soup: BeautifulSoup) -> list[dict]:
    listings = []

    cards = soup.select('[data-testid="listing-card-wrapper-premiumplus"], '
                        '[data-testid="listing-card-wrapper-standard"]')

    if not cards:
        # Fallback selector
        cards = soup.select("article[data-testid]")

    for card in cards:
        try:
            listing = _parse_card(card)
            if listing:
                listings.append(listing)
        except Exception as e:
            logger.warning(f"Error parsing card: {e}")
            continue

    return listings


def _parse_card(card) -> dict | None:
    # ID from link
    link_el = card.select_one("a[href*='/rent/']")
    if not link_el:
        return None

    href = link_el.get("href", "")
    url  = href if href.startswith("http") else BASE_URL + href

    listing_id = re.search(r"-(\d+)$", href.rstrip("/"))
    listing_id = listing_id.group(1) if listing_id else href.split("/")[-1]

    # Title
    title_el = card.select_one("h2, [data-testid='listing-card-address']")
    title = title_el.get_text(strip=True) if title_el else "Unknown"

    # Price
    price_el = card.select_one("[data-testid='listing-card-price'], .listing-price")
    price_text = price_el.get_text(strip=True) if price_el else ""
    price_week = _parse_price(price_text)
    if not price_week:
        return None

    # Suburb
    suburb_el = card.select_one("[data-testid='listing-card-address-suburb']")
    suburb = suburb_el.get_text(strip=True) if suburb_el else _extract_suburb(title)

    # Bedrooms
    bed_el = card.select_one("[data-testid='property-features-bedrooms'], "
                             "[aria-label*='Bed'], span[title*='Bedroom']")
    bedrooms = int(re.search(r"\d+", bed_el.get_text()).group()) if bed_el and re.search(r"\d+", bed_el.get_text()) else 0

    # Property type
    type_el = card.select_one("[data-testid='listing-card-property-type']")
    prop_type_text = type_el.get_text(strip=True).lower() if type_el else ""
    property_type = "house" if any(w in prop_type_text for w in ["house", "townhouse", "villa", "duplex"]) else "apartment"

    # Image
    img_el = card.select_one("img[src*='domain'], img[src*='cdn']")
    image_url = img_el.get("src", "") if img_el else ""

    # Inspection date
    insp_el = card.select_one("[data-testid='listing-card-inspection']")
    inspection_date = insp_el.get_text(strip=True) if insp_el else ""

    return {
        "id":              listing_id,
        "title":           title,
        "price_aud_week":  price_week,
        "price_aud_month": round(price_week * 4.33),
        "property_type":   property_type,
        "suburb":          suburb,
        "bedrooms":        bedrooms,
        "url":             url,
        "image_url":       image_url,
        "inspection_date": inspection_date,
        "lat":             None,
        "lon":             None,
    }


def _parse_price(text: str) -> float | None:
    """Extract weekly price in AUD from price string."""
    text = text.replace(",", "").replace(" ", "")
    match = re.search(r"\$?([\d.]+)", text)
    if not match:
        return None
    price = float(match.group(1))
    # If price looks monthly (> 3000), convert to weekly
    if price > 3000:
        price = price / 4.33
    return price


def _extract_suburb(title: str) -> str:
    parts = title.split(",")
    return parts[-1].strip() if len(parts) > 1 else "Brisbane"
