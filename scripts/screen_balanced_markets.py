#!/usr/bin/env python3
"""
Screen US cities for roughly balanced Black/White populations and cross-reference museums.

Uses the Census Data API (ACS 5-year). Requires a free API key:
https://api.census.gov/data/key_signup.html

  export CENSUS_API_KEY=your_key_here
  python3 scripts/screen_balanced_markets.py
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUSEUM_DB = ROOT / "data" / "museum-2018" / "museums.sqlite"
OUT_PATH = ROOT / "data" / "balanced-markets.json"

ACS_YEAR = 2023
MIN_POPULATION = 10_000
LOW_PCT = 0.40
HIGH_PCT = 0.60

STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09",
    "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17",
    "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30", "NE": "31",
    "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
    "WI": "55", "WY": "56", "PR": "72",
}
FIPS_TO_STATE = {value: key for key, value in STATE_FIPS.items()}


def normalize_city(name: str) -> str:
    value = name.upper().strip()
    value = re.sub(r"\s+(CITY|TOWN|VILLAGE|BOROUGH|CDP)$", "", value)
    value = re.sub(r"[^A-Z0-9 ]+", "", value)
    return re.sub(r"\s+", " ", value).strip()


def fetch_acs_places(api_key: str) -> list[dict]:
    variables = "NAME,B01003_001E,B02001_002E,B02001_003E"
    query = urllib.parse.urlencode(
        {
            "get": variables,
            "for": "place:*",
            "in": "state:*",
            "key": api_key,
        }
    )
    url = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5?{query}"
    with urllib.request.urlopen(url, timeout=120) as response:
        rows = json.load(response)

    headers = rows[0]
    records = []
    for row in rows[1:]:
        item = dict(zip(headers, row))
        total = int(item["B01003_001E"])
        white = int(item["B02001_002E"])
        black = int(item["B02001_003E"])
        if total < MIN_POPULATION:
            continue

        bw_total = white + black
        if bw_total <= 0:
            continue

        pct_white = white / bw_total
        pct_black = black / bw_total
        if not (LOW_PCT <= pct_white <= HIGH_PCT and LOW_PCT <= pct_black <= HIGH_PCT):
            continue

        state_fips = item["state"]
        place_fips = item["place"]
        state_abbr = FIPS_TO_STATE.get(state_fips, "")
        city_name = item["NAME"].split(",")[0].strip()

        records.append(
            {
                "name": city_name,
                "state": state_abbr,
                "state_fips": state_fips,
                "place_fips": place_fips,
                "geoid": f"{state_fips}{place_fips}",
                "population": total,
                "white_alone": white,
                "black_alone": black,
                "pct_white_bw": round(pct_white, 4),
                "pct_black_bw": round(pct_black, 4),
                "balance_score": round(1 - abs(pct_white - 0.5) * 2, 4),
                "city_key": f"{normalize_city(city_name)}|{state_abbr}",
            }
        )

    records.sort(key=lambda item: (-item["balance_score"], -item["population"]))
    return records


def museum_counts_by_city() -> dict[str, dict]:
    counts: dict[str, dict] = defaultdict(
        lambda: {
            "museum_count": 0,
            "art_museum_count": 0,
            "museum_names": [],
        }
    )

    conn = sqlite3.connect(MUSEUM_DB)
    try:
        rows = conn.execute(
            """
            SELECT commonname, discipline, adcity, adstate
            FROM museums
            WHERE adcity != '' AND adstate != ''
            """
        )
        for commonname, discipline, adcity, adstate in rows:
            key = f"{normalize_city(adcity)}|{adstate}"
            bucket = counts[key]
            bucket["museum_count"] += 1
            if discipline == "ART":
                bucket["art_museum_count"] += 1
            if len(bucket["museum_names"]) < 8:
                bucket["museum_names"].append(commonname)
    finally:
        conn.close()

    return dict(counts)


def enrich_markets(markets: list[dict], museum_counts: dict[str, dict]) -> list[dict]:
    enriched = []
    for market in markets:
        museums = museum_counts.get(market["city_key"], {})
        enriched.append(
            {
                **market,
                "museum_count": museums.get("museum_count", 0),
                "art_museum_count": museums.get("art_museum_count", 0),
                "sample_museums": museums.get("museum_names", []),
                "opportunity_flag": museums.get("museum_count", 0) == 0,
            }
        )
    return enriched


def main() -> None:
    api_key = os.environ.get("CENSUS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "Set CENSUS_API_KEY first. Get a free key at https://api.census.gov/data/key_signup.html"
        )

    if not MUSEUM_DB.exists():
        raise SystemExit(f"Missing museum database: {MUSEUM_DB}")

    markets = fetch_acs_places(api_key)
    museum_counts = museum_counts_by_city()
    enriched = enrich_markets(markets, museum_counts)

    payload = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "census_dataset": f"ACS 5-year {ACS_YEAR}",
            "museum_database": str(MUSEUM_DB.relative_to(ROOT)),
        },
        "criteria": {
            "min_population": MIN_POPULATION,
            "pct_black_range": [LOW_PCT, HIGH_PCT],
            "pct_white_range": [LOW_PCT, HIGH_PCT],
            "denominator": "white_alone + black_alone",
        },
        "market_count": len(enriched),
        "markets": enriched,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    no_museum = sum(1 for item in enriched if item["opportunity_flag"])
    print(f"Wrote {len(enriched)} balanced markets to {OUT_PATH}")
    print(f"{no_museum} balanced cities have zero museums in the 2018 IMLS extract")


if __name__ == "__main__":
    main()
