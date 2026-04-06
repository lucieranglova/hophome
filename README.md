# hophome
# 🦘 HopHome — Smart Rental Alerts for Brisbane

A Python application that monitors Brisbane rental listings, detects new listings and price changes, scores them, and sends fun emoji-rich alerts to Discord every evening.

## Features

- 🔍 Scrapes rental listings from Domain.com.au (houses & apartments)
- 💾 Stores history in SQLite — tracks new listings and price changes
- 📍 Enriches each listing with distance to CBD and beach
- 🚌 Estimates public transport travel times
- 🦘 Kangaroo sighting chance indicator (Atlas of Living Australia data)
- 💱 Converts AUD prices to CZK (Frankfurter API)
- ⭐ Scores listings 0–100 based on price, location and type
- 📣 Sends alerts to Discord for new listings, price drops and hot deals
- ⚙️ Fully configurable via `config.yaml`

## Project structure

```
hophome/
├── main.py                 # orchestrator
├── config.yaml             # filters and scoring weights
├── requirements.txt
├── data/
│   ├── hophome.db          # SQLite database
│   └── hophome.log         # run logs
├── modules/
│   ├── scraper.py          # Domain.com.au scraping
│   ├── database.py         # SQLite operations
│   ├── enrichment.py       # distances, transport, kangaroo
│   ├── scoring.py          # 0-100 scoring
│   ├── detector.py         # new listings, price drops
│   └── alerts.py           # Discord webhook
└── .github/
    └── workflows/
        └── hophome.yml     # daily cron at 19:00 CEST
```

## Setup

### 1. Clone / fork the repository

### 2. Add GitHub Secret
**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `DISCORD_WEBHOOK_URL` | Your Discord webhook URL |

### 3. Run manually to test
**Actions → HopHome — Rental Alerts → Run workflow**

## Configuration

Edit `config.yaml` to adjust filters and scoring:

```yaml
filters:
  max_price_aud_month: 2500   # max monthly rent
  min_bedrooms: 2             # minimum bedrooms

scoring:
  weights:
    price_vs_average: 30
    distance_cbd: 20
    distance_beach: 20
    property_type: 15
    bedrooms: 15
  thresholds:
    high_score: 80            # alert if score >= 80
    price_drop_pct: 5         # alert if price dropped >= 5%
```

## Alert example

```
⭐ HOT DEAL ALERT!

📍 Paddington · 🏡 House
💰 $480/week · $2,078/month (~31,000 CZK)
🛏 3 bedrooms · 🔍 Inspection: Sat 12 Apr 10:00am

🏙️ CBD: 4.2 km · 🚌 ~18 min by public transport
🌊 Beach: 48 km · 🚌 ~58 min by public transport
🦘 Kangaroo chance: MEDIUM 😮

⭐ Score: 84/100
🔗 View listing: https://domain.com.au/...
```

## APIs used

| Service | Purpose | Cost |
|---|---|---|
| Domain.com.au | Rental listings | Free (scraping) |
| Nominatim (OSM) | Geocoding suburbs | Free |
| Frankfurter API | AUD/CZK exchange rate | Free |
| Atlas of Living Australia | Kangaroo sightings | Free |
| Discord webhook | Alerts | Free |
| GitHub Actions | Scheduling | Free |
