#!/usr/bin/env python3
"""Extract unique EN strings from WTS / FDF / Misc into JSONL for translation."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WTS = ROOT / "wowr/wowr.w3x/war3map.wts"
DEFAULT_FDF = ROOT / "wowr/wowr.w3x/wowr/WoWReforgedStrings.fdf"
DEFAULT_MISC = ROOT / "wowr/wowr.w3x/war3mapMisc.txt"
DEFAULT_OUT = ROOT / "data/en_strings.jsonl"

WTS_PAT = re.compile(r"(STRING\s+(\d+)\s*(?://[^\n]*)?\s*\{)(.*?)(\})", re.S)
# KEY "value",  — allow missing space before quote (seen once in source)
FDF_PAT = re.compile(
    r"^(\s*)([A-Za-z0-9_]+)\s*\"(.*)\"\s*,?\s*$", re.M
)
URLISH = re.compile(
    r"^(https?://\S+|discord\.gg/\S+|www\.\S+)$", re.I
)
PURE_NUM = re.compile(r"^-?\d+(\.\d+)?$")
PLACEHOLDER_ONLY = re.compile(
    r"^(%\d+%|%s|%d|\|n|\|r|\|c[0-9A-Fa-f]{8})+$"
)


def should_skip(text: str) -> bool:
    s = text.strip()
    if not s:
        return True
    if PURE_NUM.match(s):
        return True
    if URLISH.match(s):
        return True
    # Skip pure WC3 color/format tokens with no real words
    if PLACEHOLDER_ONLY.match(s.replace(" ", "")):
        return True
    return False


def extract_wts(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    rows = []
    for m in WTS_PAT.finditer(text):
        sid = m.group(2)
        body = m.group(3)
        lines = body.split("\n")
        vals = []
        for line in lines:
            if not vals and (line.strip() == "" or line.strip().startswith("//")):
                continue
            vals.append(line)
        raw = "\n".join(vals).strip("\n")
        # strip trailing blank lines only; keep leading content as-is after strip
        raw = raw.strip("\n")
        if raw.endswith("\r"):
            raw = raw[:-1]
        # WTS bodies are typically without leading/trailing blank; strip outer whitespace
        # but preserve internal |n etc. Strip only wrapping newlines already done.
        raw_stripped = raw.strip()
        if should_skip(raw_stripped):
            continue
        rows.append(
            {
                "id": f"wts:{sid}",
                "source": raw_stripped,
                "kind": "wts",
                "key": sid,
            }
        )
    return rows


def extract_fdf(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    rows = []
    for m in FDF_PAT.finditer(text):
        key = m.group(2)
        val = m.group(3)
        # unescape \" if present (rare)
        val = val.replace('\\"', '"')
        if should_skip(val):
            continue
        rows.append(
            {
                "id": f"fdf:{key}",
                "source": val,
                "kind": "fdf",
                "key": key,
            }
        )
    return rows


def extract_misc(path: Path) -> list[dict]:
    """Only translate Name= and similar human-readable value sides."""
    text = path.read_text(encoding="utf-8", errors="replace")
    rows = []
    for i, line in enumerate(text.splitlines(), 1):
        if "=" not in line or line.strip().startswith("["):
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        # Only stringy Name fields (gameplay numbers stay EN)
        if k.lower() != "name":
            continue
        if should_skip(v):
            continue
        rows.append(
            {
                "id": f"misc:{i}:{k}",
                "source": v,
                "kind": "misc",
                "key": k,
            }
        )
    return rows


def dedupe_keep_order(rows: list[dict]) -> list[dict]:
    """One JSONL row per unique source text; first occurrence wins metadata."""
    seen: dict[str, dict] = {}
    for r in rows:
        src = r["source"]
        if src in seen:
            # track all ids that share this source
            seen[src].setdefault("also_ids", []).append(r["id"])
            continue
        seen[src] = dict(r)
    return list(seen.values())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wts", type=Path, default=DEFAULT_WTS)
    ap.add_argument("--fdf", type=Path, default=DEFAULT_FDF)
    ap.add_argument("--misc", type=Path, default=DEFAULT_MISC)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--kinds",
        default="wts,fdf,misc",
        help="Comma list: wts,fdf,misc",
    )
    args = ap.parse_args()
    kinds = {k.strip() for k in args.kinds.split(",") if k.strip()}

    rows: list[dict] = []
    if "wts" in kinds and args.wts.exists():
        rows.extend(extract_wts(args.wts))
    if "fdf" in kinds and args.fdf.exists():
        rows.extend(extract_fdf(args.fdf))
    if "misc" in kinds and args.misc.exists():
        rows.extend(extract_misc(args.misc))

    unique = dedupe_keep_order(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for r in unique:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_kind: dict[str, int] = {}
    for r in rows:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
    print(
        f"extracted raw={len(rows)} unique={len(unique)} "
        f"by_kind={by_kind} -> {args.out}"
    )


if __name__ == "__main__":
    main()
