# 🦘 HopHome — Smart Rental Alerts for Brisbane

A Python application that monitors Brisbane rental listings, enriches them with location data, scores them, and sends fun emoji-rich alerts to Discord every evening.

> ⚠️ Currently running with **mock data** while Domain API Production access is pending approval. Once approved, see the TODO section at the bottom.

---

## Example Discord alert

> 🆕 **New Listing!**
>
> 📍 **Camp Hill** · 🏡 House
> 💰 **$420/week** · $1818/month (~26,900 CZK)
> 🛏 **3 bedrooms** · 🔍 Inspection: 2026-04-12
>
> 🏙️ CBD: **6.2 km** · 🚌 Bus ~21 min
> 🌊 Beach: **65.4 km** · 🚌 Bus ~169 min
> 🦘 Kangaroo chance: **LOW 😓**
> 🏫 Nearest school: **Camp Hill State School** (0.8 km)
> 🏥 Nearest hospital: **Greenslopes Private Hospital** (2.1 km)
>
> 🟡 Score: **67.5/100**
> 🔗 View listing

---

## Features

- 🔍 Fetches rental listings from **Domain.com.au API**
- 💾 Stores history in **SQLite** — tracks new listings and price changes
- 📍 Enriches each listing with:
  - Distance to CBD and nearest beach
  - Public transport time + **specific train line or bus**
  - Nearest school and hospital (optional, configurable)
  - 🦘 Kangaroo sighting chance (Atlas of Living Australia data)
- 💱 Converts AUD prices to CZK (Frankfurter API)
- ⭐ Scores listings **0–100** with beach proximity as top priority
- 🎨 Color-coded Discord embeds (🟢 green / 🟡 yellow / 🔴 red by score)
- 📣 Alerts for new listings, price drops (>5%) and hot deals (score >80)
- ⚙️ Fully configurable via `config.yaml`

---

## Project structure

```
hophome/
├── main.py                 # orchestrator
├── config.yaml             # filters, scoring weights, enrichment toggles
├── requirements.txt
├── data/
│   ├── hophome.db          # SQLite database
│   └── hophome.log         # run logs
├── modules/
│   ├── scraper.py          # Domain.com.au API + mock data fallback
│   ├── database.py         # SQLite operations
│   ├── enrichment.py       # distances, transport lines, school, hospital, kangaroo
│   ├── scoring.py          # 0–100 scoring (beach-first weights)
│   ├── detector.py         # new listings, price drops detection
│   └── alerts.py           # Discord webhook formatting
└── .github/
    └── workflows/
        └── hophome.yml     # daily cron at 19:00 CEST
```

---

## Setup

### 1. Clone or fork the repository

### 2. Add GitHub Secrets
**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `DISCORD_WEBHOOK_URL` | Your Discord webhook URL |
| `DOMAIN_CLIENT_ID` | Domain.com.au OAuth client ID |
| `DOMAIN_CLIENT_SECRET` | Domain.com.au OAuth client secret |

### 3. Get Domain API credentials
1. Register at [developer.domain.com.au](https://developer.domain.com.au)
2. Create a new project
3. Go to **Credentials → Create OAuth Client**
4. Go to **API Access → Add API → Listings Management → Production → Request access**
5. Copy `client_id` and `client_secret` to GitHub Secrets

### 4. Run manually to test
**Actions → HopHome — Rental Alerts → Run workflow**

---

## Configuration

Edit `config.yaml` to adjust filters, scoring and enrichment:

```yaml
filters:
  max_price_aud_month: 2500   # max monthly rent
  min_bedrooms: 2

scoring:
  weights:
    price_vs_average: 20
    distance_cbd: 10
    distance_beach: 35        # beach is the priority 🌊
    property_type: 15
    bedrooms: 20
  thresholds:
    high_score: 80
    price_drop_pct: 5

enrichment:
  show_school: true           # show nearest school
  show_hospital: true         # show nearest hospital
```

---

## Scoring

Each listing is scored 0–100 based on weighted criteria:

| Criterion | Weight | Notes |
|---|---|---|
| Price vs suburb average | 20% | Cheaper = better |
| Distance to CBD | 10% | Closer = better |
| Distance to beach | 35% | **Top priority** — bonus for < 20 km |
| Property type | 15% | House > Apartment |
| Bedrooms | 20% | More = better |

Score colours in Discord: 🟢 ≥ 80 · 🟡 60–79 · 🔴 < 60

---

## Alert types

| Type | Trigger |
|---|---|
| 🆕 New listing | First time seen |
| 📉 Price drop | Price fell ≥ 5% since last seen |
| ⭐ Hot deal | Score ≥ 80 |
| 🔥 Mega deal | New + price drop + high score |

---

## APIs used

| Service | Purpose | Cost |
|---|---|---|
| Domain.com.au API | Rental listings | Free (approved project) |
| Nominatim (OSM) | Geocoding suburbs | Free |
| Overpass API (OSM) | Nearest school / hospital | Free |
| Frankfurter API | AUD/CZK exchange rate | Free |
| Atlas of Living Australia | Kangaroo sightings 🦘 | Free |
| Discord webhook | Alerts | Free |
| GitHub Actions | Scheduling | Free |

---

## TODO after Production API approval

- [ ] Remove `rm -f data/hophome.db` from workflow (restores price history tracking)
- [ ] Confirm `SEARCH_URL` in `scraper.py` points to production endpoint
