#!/usr/bin/env python3
"""Score an Apollo person payload with the GDP model — no server needed.

Usage:
  python scripts/score_apollo.py path/to/apollo.json
  python scripts/score_apollo.py path/to/apollo.json --framing loss
  cat apollo.json | python scripts/score_apollo.py -

Accepts either a raw Apollo /people/match response ({"person": {...}}) or a
bare person object. For the Apollo-connector path: save the connector's person
JSON to a file, then run this — it bypasses the network entirely.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.scoring import score_apollo_person


def main() -> None:
    ap = argparse.ArgumentParser(description="Run an Apollo person payload through the GDP model.")
    ap.add_argument("source", help="Path to a JSON file, or '-' to read from stdin.")
    ap.add_argument("--framing", choices=["missed_out", "loss"], default=None)
    args = ap.parse_args()

    raw = sys.stdin.read() if args.source == "-" else Path(args.source).read_text()
    data = json.loads(raw)
    person = data.get("person", data)  # accept full response or bare person object

    result = score_apollo_person(person, framing=args.framing)

    s = result["summary"]
    p = result["person"]
    print(f"Person : {p['name']} — {p['current_title']} @ {p['current_company']}")
    print(f"Stints : {len(result['stints'])}")
    print(f"Summary: {s['headline_statement']}")
    if result["founder_impact"]:
        print(f"Founder: {result['founder_impact']['headline_statement']}")
    print("\n--- full JSON ---")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
