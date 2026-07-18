#!/usr/bin/env python3
"""Merge IMLS 2018 museum CSV exports into searchable JSON + SQLite."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "museum-2018" / "source"
OUT_DIR = ROOT / "data" / "museum-2018"
OVERRIDES_PATH = OUT_DIR / "overrides.json"

DISCIPLINE_LABELS = {
    "ART": "Art museum",
    "GMU": "General museum",
    "HSC": "History / science / children's",
    "NAT": "Natural history / nature center",
    "BOT": "Botanical garden / arboretum",
    "ZOO": "Zoo / aquarium",
    "SCI": "Science / technology center",
    "HIS": "History museum / historic site",
    "CHI": "Children's museum",
    "HAI": "Historic house",
}

SEARCH_FIELDS = [
    "MID",
    "DISCIPLINE",
    "COMMONNAME",
    "LEGALNAME",
    "ALTNAME",
    "ADCITY",
    "ADSTATE",
    "ADZIP5",
    "PHONE",
    "WEBURL",
    "EIN",
    "INSTNAME",
]


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in row.items():
        cleaned[key.strip()] = (value or "").strip()

    if "DISCIPL" in cleaned and "DISCIPLINE" not in cleaned:
        cleaned["DISCIPLINE"] = cleaned.pop("DISCIPL")
    elif "DISCIPL" in cleaned:
        cleaned.pop("DISCIPL", None)

    return cleaned


def load_overrides() -> list[dict]:
    if not OVERRIDES_PATH.is_file():
        return []
    data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    return data.get("overrides", [])


def apply_overrides(records: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    """Merge human corrections keyed by MID before export."""
    by_mid = {record["MID"]: record for record in records if record.get("MID")}
    applied = 0

    for entry in load_overrides():
        mid = entry.get("mid", "")
        fields = entry.get("fields") or {}
        if not mid or not fields:
            continue
        record = by_mid.get(mid)
        if not record:
            print(f"Warning: override for unknown MID {mid} — skipped")
            continue
        for key, value in fields.items():
            record[key] = "" if value is None else str(value).strip()
        applied += 1

    merged = sorted(by_mid.values(), key=lambda item: item.get("COMMONNAME", "").lower())
    return merged, applied


def load_records() -> tuple[list[dict[str, str]], Counter]:
    records_by_mid: dict[str, dict[str, str]] = {}
    source_counts: Counter = Counter()

    for csv_path in sorted(SOURCE_DIR.glob("*.csv")):
        with csv_path.open(newline="", encoding="latin-1") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                normalized = normalize_row(row)
                mid = normalized.get("MID", "")
                if not mid:
                    continue
                records_by_mid[mid] = normalized
                source_counts[csv_path.name] += 1

    records = sorted(records_by_mid.values(), key=lambda item: item.get("COMMONNAME", "").lower())
    return records, source_counts


def search_blob(record: dict[str, str]) -> str:
    parts = [record.get(field, "") for field in SEARCH_FIELDS]
    return " ".join(part for part in parts if part).lower()


def slim_record(record: dict[str, str]) -> dict[str, str]:
    discipline = record.get("DISCIPLINE", "")
    return {
        "mid": record.get("MID", ""),
        "name": record.get("COMMONNAME", ""),
        "legal": record.get("LEGALNAME", ""),
        "discipline": discipline,
        "discipline_label": DISCIPLINE_LABELS.get(discipline, discipline),
        "city": record.get("ADCITY", ""),
        "state": record.get("ADSTATE", ""),
        "zip": record.get("ADZIP5", ""),
        "phone": record.get("PHONE", ""),
        "web": record.get("WEBURL", ""),
        "lat": record.get("LATITUDE", ""),
        "lon": record.get("LONGITUDE", ""),
        "revenue": record.get("REVENUE15", ""),
        "income": record.get("INCOME15", ""),
        "ein": record.get("EIN", ""),
        "search": search_blob(record),
    }


def write_json(records: list[dict[str, str]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    slim_path = OUT_DIR / "museums.json"
    by_mid_path = OUT_DIR / "museums-by-mid.json"

    slim_records = [slim_record(record) for record in records]

    slim_path.write_text(json.dumps(slim_records, separators=(",", ":")), encoding="utf-8")
    by_mid_path.write_text(
        json.dumps({record["MID"]: record for record in records}, indent=2),
        encoding="utf-8",
    )


def write_sqlite(records: list[dict[str, str]]) -> None:
    db_path = OUT_DIR / "museums.sqlite"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE museums (
                mid TEXT PRIMARY KEY,
                discipline TEXT,
                commonname TEXT,
                legalname TEXT,
                altname TEXT,
                adcity TEXT,
                adstate TEXT,
                adzip5 TEXT,
                phone TEXT,
                weburl TEXT,
                latitude REAL,
                longitude REAL,
                revenue15 INTEGER,
                income15 INTEGER,
                ein TEXT,
                data_json TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX idx_museums_name ON museums(commonname)")
        conn.execute("CREATE INDEX idx_museums_state ON museums(adstate)")
        conn.execute("CREATE INDEX idx_museums_discipline ON museums(discipline)")

        rows = []
        for record in records:
            lat = record.get("LATITUDE") or None
            lon = record.get("LONGITUDE") or None
            revenue = record.get("REVENUE15") or None
            income = record.get("INCOME15") or None
            rows.append(
                (
                    record.get("MID", ""),
                    record.get("DISCIPLINE", ""),
                    record.get("COMMONNAME", ""),
                    record.get("LEGALNAME", ""),
                    record.get("ALTNAME", ""),
                    record.get("ADCITY", ""),
                    record.get("ADSTATE", ""),
                    record.get("ADZIP5", ""),
                    record.get("PHONE", ""),
                    record.get("WEBURL", ""),
                    float(lat) if lat else None,
                    float(lon) if lon else None,
                    int(revenue) if revenue else None,
                    int(income) if income else None,
                    record.get("EIN", ""),
                    json.dumps(record, separators=(",", ":")),
                )
            )

        conn.executemany(
            """
            INSERT INTO museums (
                mid, discipline, commonname, legalname, altname,
                adcity, adstate, adzip5, phone, weburl,
                latitude, longitude, revenue15, income15, ein, data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def write_meta(records: list[dict[str, str]], source_counts: Counter, override_count: int) -> None:
    states = Counter(record.get("ADSTATE", "") for record in records if record.get("ADSTATE"))
    disciplines = Counter(
        record.get("DISCIPLINE", "") for record in records if record.get("DISCIPLINE")
    )

    meta = {
        "dataset": "IMLS Museum Universe Data File 2018",
        "year": 2018,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "source_files": dict(source_counts),
        "states": dict(states.most_common()),
        "disciplines": {
            code: {
                "count": count,
                "label": DISCIPLINE_LABELS.get(code, code),
            }
            for code, count in disciplines.most_common()
        },
        "discipline_labels": DISCIPLINE_LABELS,
        "overrides_applied": override_count,
        "overrides_file": "data/museum-2018/overrides.json",
        "search_ui": "web/index.html",
        "files": {
            "slim_json": "data/museum-2018/museums.json",
            "by_mid_json": "data/museum-2018/museums-by-mid.json",
            "sqlite": "data/museum-2018/museums.sqlite",
        },
    }

    (OUT_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main() -> None:
    records, source_counts = load_records()
    records, override_count = apply_overrides(records)
    write_json(records)
    write_sqlite(records)
    write_meta(records, source_counts, override_count)
    suffix = f" ({override_count} override(s) applied)" if override_count else ""
    print(f"Built {len(records)} museum records into {OUT_DIR}{suffix}")


if __name__ == "__main__":
    main()
