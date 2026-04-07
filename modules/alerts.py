"""
alerts.py — Sends fun, emoji-rich Discord alerts for rental listings.
"""

import logging
import os
import requests

logger = logging.getLogger(__name__)

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")

_aud_czk_rate: float | None = None


def get_aud_czk_rate() -> float:
    global _aud_czk_rate
    if _aud_czk_rate:
        return _aud_czk_rate
    try:
        resp = requests.get("https://api.frankfurter.app/latest?from=AUD&to=CZK", timeout=10)
        _aud_czk_rate = resp.json()["rates"]["CZK"]
        logger.info(f"AUD/CZK rate: {_aud_czk_rate}")
    except Exception as e:
        logger.warning(f"Could not fetch AUD/CZK rate: {e}. Using fallback 15.0")
        _aud_czk_rate = 15.0
    return _aud_czk_rate


def send_alert(listing: dict, alert_types: list[str]):
    if not DISCORD_WEBHOOK:
        logger.warning("DISCORD_WEBHOOK_URL not set — skipping alert.")
        return

    rate    = get_aud_czk_rate()
    payload = _build_payload(listing, alert_types, rate)

    try:
        resp = requests.post(
            DISCORD_WEBHOOK,
            json=payload,
            headers={"User-Agent": "HopHome/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info(f"Alert sent for {listing['id']} ({', '.join(alert_types)})")
    except requests.RequestException as e:
        logger.error(f"Discord send failed: {e}")


def send_summary(total: int, new: int, drops: int):
    if not DISCORD_WEBHOOK:
        return
    msg = (
        f"🦘 **HopHome Daily Summary**\n"
        f"Scanned **{total}** listings in Brisbane today.\n"
        f"🆕 New listings: **{new}** · 📉 Price drops: **{drops}**"
    )
    try:
        requests.post(
            DISCORD_WEBHOOK,
            json={"content": msg},
            headers={"User-Agent": "HopHome/1.0"},
            timeout=10,
        )
    except requests.RequestException as e:
        logger.error(f"Summary send failed: {e}")


def _score_bar(score: float) -> str:
    """Visual progress bar for score."""
    filled = int(score / 10)
    empty  = 10 - filled
    return "▓" * filled + "░" * empty


def _score_emoji(score: float) -> str:
    if score >= 80:
        return "🟢"
    elif score >= 60:
        return "🟡"
    else:
        return "🔴"


def _build_payload(listing: dict, alert_types: list[str], rate: float) -> dict:
    price_week  = listing.get("price_aud_week",  0)
    price_month = listing.get("price_aud_month", 0)
    price_czk   = int(price_month * rate)

    prop_emoji = "🏡" if listing.get("property_type") == "house" else "🏢"
    prop_label = "House" if listing.get("property_type") == "house" else "Apartment"

    kanga      = listing.get("kangaroo_chance", "LOW 😓")
    dist_cbd   = listing.get("dist_cbd_km",   "?")
    dist_beach = listing.get("dist_beach_km", "?")
    t_cbd      = listing.get("transit_cbd_min",   "?")
    t_beach    = listing.get("transit_beach_min", "?")
    mode_cbd   = listing.get("transit_cbd_mode",   "🚌 Bus")
    mode_beach = listing.get("transit_beach_mode", "🚌 Bus")
    beds       = listing.get("bedrooms",      "?")
    score      = listing.get("score", 0)
    inspection = listing.get("inspection_date", "—")

    # Title
    if "high_score" in alert_types and "price_drop" in alert_types:
        title = "🏡🔥 MEGA DEAL — NEW + PRICE DROP + HIGH SCORE!"
    elif "high_score" in alert_types:
        title = "⭐ HOT DEAL ALERT!"
    elif "price_drop" in alert_types:
        title = "📉 PRICE DROP ALERT!"
    else:
        title = "🆕 New Listing!"

    # Price drop line
    drop_line = ""
    if "price_drop" in alert_types:
        drop_pct  = listing.get("_price_drop_pct", 0)
        old_price = listing.get("_old_price_week", price_week)
        drop_line = f"\n📉 Price dropped **{drop_pct}%** (was ${old_price:.0f}/week)"

    # Optional school & hospital lines
    school_line   = ""
    hospital_line = ""

    dist_school = listing.get("dist_school_km")
    name_school = listing.get("nearest_school")
    if dist_school is not None:
        school_line = f"\n🏫 Nearest school: **{name_school}** ({dist_school} km)"

    dist_hospital = listing.get("dist_hospital_km")
    name_hospital = listing.get("nearest_hospital")
    if dist_hospital is not None:
        hospital_line = f"\n🏥 Nearest hospital: **{name_hospital}** ({dist_hospital} km)"

    # Score emoji
    score_emoji = _score_emoji(score)

    description = (
        f"📍 **{listing.get('suburb', '?')}** · {prop_emoji} {prop_label}\n"
        f"💰 **${price_week:.0f}/week** · ${price_month:.0f}/month (~{price_czk:,} CZK)\n"
        f"🛏 **{beds} bedrooms**\n"
        f"🔍 Inspection: {inspection}\n"
        f"\n"
        f"🏙️ CBD: **{dist_cbd} km** · {mode_cbd} ~{t_cbd} min\n"
        f"🌊 Beach: **{dist_beach} km** · {mode_beach} ~{t_beach} min\n"
        f"🦘 Kangaroo chance: **{kanga}**"
        f"{school_line}"
        f"{hospital_line}"
        f"{drop_line}\n"
        f"\n"
        f"{score_emoji} Score: **{score}/100**\n"
        f"🔗 [View listing]({listing.get('url', '')})"
    )

    embed = {
        "title":       title,
        "description": description,
        "color":       _embed_color(alert_types, score),
        "url":         listing.get("url", ""),
        "footer":      {"text": "HopHome 🦘 • Smart Rental Alerts for Brisbane"},
    }

    image_url = listing.get("image_url", "")
    if image_url and image_url.startswith("http"):
        embed["image"] = {"url": image_url}

    return {"embeds": [embed]}


def _embed_color(alert_types: list[str], score: float) -> int:
    """Color based on score: green=high, yellow=medium, red=low."""
    if score >= 80:
        return 0x2ECC71   # zelená
    elif score >= 60:
        return 0xF1C40F   # žlutá
    else:
        return 0xE74C3C   # červená
