#!/usr/bin/env python3
"""
Add, list, or inspect museum record overrides (survives CSV rebuild).

Usage:
  python3 manage_overrides.py list
  python3 manage_overrides.py show 8401234567
  python3 manage_overrides.py add 8401234567 --field COMMONNAME --value "Corrected Name" \\
      --source "Client call · 2026-07-17"

After add/edit, rebuild:
  python3 build_museum_2018_db.py
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES_PATH = ROOT / "data" / "museum-2018" / "overrides.json"


def load_doc() -> dict:
    if OVERRIDES_PATH.is_file():
        return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    return {"schema_version": "1.0", "description": "", "overrides": []}


def save_doc(doc: dict) -> None:
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDES_PATH.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def find_override(doc: dict, mid: str) -> dict | None:
    for entry in doc.get("overrides", []):
        if entry.get("mid") == mid:
            return entry
    return None


def cmd_list(_: argparse.Namespace) -> None:
    doc = load_doc()
    overrides = doc.get("overrides", [])
    if not overrides:
        print("No overrides.")
        return
    for entry in overrides:
        fields = ", ".join(entry.get("fields", {}).keys())
        print(f"{entry.get('mid')}  [{fields}]  {entry.get('source', '')}")


def cmd_show(args: argparse.Namespace) -> None:
    entry = find_override(load_doc(), args.mid)
    if not entry:
        raise SystemExit(f"No override for MID {args.mid}")
    print(json.dumps(entry, indent=2))


def cmd_add(args: argparse.Namespace) -> None:
    doc = load_doc()
    entry = find_override(doc, args.mid)
    if not entry:
        entry = {
            "mid": args.mid,
            "fields": {},
            "source": args.source or "",
            "corrected_at": date.today().isoformat(),
            "corrected_by": args.by or "",
        }
        doc.setdefault("overrides", []).append(entry)

    entry["fields"][args.field] = args.value
    if args.source:
        entry["source"] = args.source
    if args.by:
        entry["corrected_by"] = args.by
    entry["corrected_at"] = date.today().isoformat()

    save_doc(doc)
    print(f"Saved override for MID {args.mid} · field {args.field}")
    print("Rebuild: python3 scripts/build_museum_2018_db.py")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage museum-database overrides")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=cmd_list)

    show_p = sub.add_parser("show", help="Show override for one MID")
    show_p.add_argument("mid")
    show_p.set_defaults(func=cmd_show)

    add_p = sub.add_parser("add", help="Add or update field override for MID")
    add_p.add_argument("mid")
    add_p.add_argument("--field", required=True, help="IMLS field name, e.g. COMMONNAME, EIN, ADCITY")
    add_p.add_argument("--value", required=True)
    add_p.add_argument("--source", help="Why corrected (client call, 990, site visit)")
    add_p.add_argument("--by", help="Who corrected")
    add_p.set_defaults(func=cmd_add)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
