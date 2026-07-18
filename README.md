# museum-database

Searchable US museum database and market-screening tools for **[Museum Planning LLC](https://github.com/Museum-Planning-LLC)**.

**Repo:** [Museum-Planning-LLC/museum-database](https://github.com/Museum-Planning-LLC/museum-database)

## What's here

| Asset | Path |
|-------|------|
| **30,175 museums** (2018 IMLS) | `data/museum-2018/` |
| Search UI | `web/index.html` |
| Build script | `scripts/build_museum_2018_db.py` |
| Balanced-market screener | `scripts/screen_balanced_markets.py` |

## Search UI

Open `web/index.html` locally, or enable GitHub Pages on this repo:

**https://museum-planning-llc.github.io/museum-database/web/**

Features:

- Search name, city, state, MID, phone, website, EIN
- Filter by state and discipline
- Sort by name, state, or 2015 revenue
- Click a row for full record details

## Data files

| File | Size (approx.) | Purpose |
|------|----------------|---------|
| `data/museum-2018/museums.json` | 14 MB | Slim search index |
| `data/museum-2018/museums-by-mid.json` | 41 MB | Full records keyed by MID |
| `data/museum-2018/museums.sqlite` | 42 MB | SQL queries and enrichment |
| `data/museum-2018/source/*.csv` | 11 MB | Original IMLS 2018 CSV exports |

## Rebuild museum database

Place source CSVs in `data/museum-2018/source/`, then:

```bash
python3 scripts/build_museum_2018_db.py
```

Human corrections live in `data/museum-2018/overrides.json` and are merged at build time (survives CSV rebuilds).

```bash
# List / add corrections
python3 scripts/manage_overrides.py list
python3 scripts/manage_overrides.py add 8401234567 --field EIN --value "592048869" \
  --source "Client verification · 2026-07-17"
python3 scripts/build_museum_2018_db.py
```

See `overrides.json` for schema. Used by Digital-Twin resiliency studies before PDF export.

## Balanced-market screening (50/50 Black / White cities)

Screen US cities where Black alone and White alone are each roughly **40–60%** of the combined Black+White population, then cross-reference museums already in that city.

Requires a free [Census API key](https://api.census.gov/data/key_signup.html):

```bash
export CENSUS_API_KEY=your_key_here
python3 scripts/screen_balanced_markets.py
```

Output: `data/balanced-markets.json`

Each market record includes:

- `pct_black_bw`, `pct_white_bw`, `balance_score`
- `museum_count`, `art_museum_count`
- `opportunity_flag` — `true` when no museums appear in the 2018 extract for that city

## Source

Merged from the **2018 IMLS Museum Universe Data File** (3 CSV exports). Records deduplicated by `MID`.

## Related repos

- [museum-planner-2.0](https://github.com/Museum-Planning-LLC/museum-planner-2.0) — Museum Planner essays and book hubs
- [website-2.0](https://github.com/Museum-Planning-LLC/website-2.0) — museumplanning.com marketing site
