"""
database.py — SQLite storage for HopHome listings and price history.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = Path("data/hophome.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS listings (
                id              TEXT PRIMARY KEY,
                title           TEXT,
                price_aud_week  REAL,
                price_aud_month REAL,
                property_type   TEXT,
                suburb          TEXT,
                bedrooms        INTEGER,
                url             TEXT,
                image_url       TEXT,
                inspection_date TEXT,
                lat             REAL,
                lon             REAL,
                dist_cbd_km     REAL,
                dist_beach_km   REAL,
                transit_cbd_min INTEGER,
                transit_beach_min INTEGER,
                kangaroo_chance TEXT,
                score           REAL,
                first_seen      TEXT,
                last_seen       TEXT,
                active          INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id      TEXT,
                price_aud_week  REAL,
                recorded_at     TEXT,
                FOREIGN KEY (listing_id) REFERENCES listings(id)
            );
        """)
    logger.info("Database initialized.")


def upsert_listing(listing: dict) -> dict:
    """
    Insert or update a listing.
    Returns dict with keys: is_new (bool), price_dropped (bool), old_price (float|None)
    """
    now = datetime.utcnow().isoformat()

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM listings WHERE id = ?", (listing["id"],)
        ).fetchone()

        result = {"is_new": False, "price_dropped": False, "old_price": None}

        if existing is None:
            # New listing
            conn.execute("""
                INSERT INTO listings (
                    id, title, price_aud_week, price_aud_month,
                    property_type, suburb, bedrooms, url, image_url,
                    inspection_date, lat, lon,
                    dist_cbd_km, dist_beach_km,
                    transit_cbd_min, transit_beach_min,
                    kangaroo_chance, score,
                    first_seen, last_seen, active
                ) VALUES (
                    :id, :title, :price_aud_week, :price_aud_month,
                    :property_type, :suburb, :bedrooms, :url, :image_url,
                    :inspection_date, :lat, :lon,
                    :dist_cbd_km, :dist_beach_km,
                    :transit_cbd_min, :transit_beach_min,
                    :kangaroo_chance, :score,
                    :first_seen, :last_seen, 1
                )
            """, {**listing, "first_seen": now, "last_seen": now})

            conn.execute(
                "INSERT INTO price_history (listing_id, price_aud_week, recorded_at) VALUES (?, ?, ?)",
                (listing["id"], listing["price_aud_week"], now)
            )
            result["is_new"] = True
            logger.info(f"New listing: {listing['id']} — {listing['suburb']}")

        else:
            old_price = existing["price_aud_week"]
            new_price = listing["price_aud_week"]

            conn.execute("""
                UPDATE listings SET
                    title = :title,
                    price_aud_week = :price_aud_week,
                    price_aud_month = :price_aud_month,
                    inspection_date = :inspection_date,
                    image_url = :image_url,
                    score = :score,
                    kangaroo_chance = :kangaroo_chance,
                    last_seen = :last_seen,
                    active = 1
                WHERE id = :id
            """, {**listing, "last_seen": now})

            if old_price and new_price < old_price:
                conn.execute(
                    "INSERT INTO price_history (listing_id, price_aud_week, recorded_at) VALUES (?, ?, ?)",
                    (listing["id"], new_price, now)
                )
                result["price_dropped"] = True
                result["old_price"] = old_price
                logger.info(f"Price drop: {listing['id']} {old_price} → {new_price}")

    return result


def mark_inactive_except(active_ids: list[str]):
    """Mark listings not seen in current run as inactive."""
    if not active_ids:
        return
    placeholders = ",".join("?" * len(active_ids))
    with get_connection() as conn:
        conn.execute(
            f"UPDATE listings SET active = 0 WHERE id NOT IN ({placeholders})",
            active_ids
        )
