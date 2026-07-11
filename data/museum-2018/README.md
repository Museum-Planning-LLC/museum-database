# US Museum Database 2018

Merged, searchable export of the **2018 IMLS Museum Universe Data File** CSV release.

## Contents

| Path | Purpose |
|------|---------|
| `source/*.csv` | Original 2018 CSV exports (3 files) |
| `museums.json` | Slim search index (~30k records) |
| `museums-by-mid.json` | Full records keyed by `MID` |
| `museums.sqlite` | SQLite database for scripts and SQL queries |
| `meta.json` | Build metadata, counts, discipline labels |

## Search UI

Open **`web/index.html`** locally or on GitHub Pages.

## Rebuild

After updating source CSVs:

```bash
python3 scripts/build_museum_2018_db.py
```

## Source notes

- Records are deduplicated by `MID` when the same museum appears in multiple source files.
- `DISCIPL` from File 1 is normalized to `DISCIPLINE` to match Files 2 and 3.
- Empty `MID` rows are dropped.
- Field values are trimmed; source encoding is Latin-1.

## Data use

This dataset is provided for museum planning research and benchmarking. Verify live institution details before using contact or financial fields in production workflows.
