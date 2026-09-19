#!/usr/bin/env python3
"""Apply Packy cache to Gaia WTS+JASS and build zhCN .w3x via w3x_replace_nocompact."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTRACT = ROOT / "gaias/extract"
BUILD = ROOT / "gaias/build"
OUT_DIR = ROOT / "gaias/out"
DEFAULT_CACHE = ROOT / "gaias/cache/packy_zh.json"
DEFAULT_MAP = ROOT / "maps/GaiasORPG_v1_3A_12.w3x"
DEFAULT_OUT = OUT_DIR / "GaiasORPG_v1_3A_12_zhCN.w3x"
TOOL = ROOT / "tools/w3x_replace_nocompact"

WTS_PAT = re.compile(r"(STRING\s+\d+\s*(?://[^\n]*)?\s*\{)(.*?)(\})", re.S)
JASS_STR = re.compile(r'"((?:\\.|[^"\\])*)"')


def load_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items()}


def unescape_jass(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in '"\\':
                out.append(nxt)
                i += 2
                continue
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt == "t":
                out.append("\t")
                i += 2
                continue
            out.append(nxt)
            i += 2
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def escape_jass(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "")
    )


def apply_wts(en_text: str, cache: dict[str, str]) -> tuple[str, int, int]:
    if en_text.startswith("\ufeff"):
        en_text = en_text[1:]
    out = []
    last = 0
    hit = 0
    total = 0
    for m in WTS_PAT.finditer(en_text):
        out.append(en_text[last : m.start()])
        header, body, close = m.group(1), m.group(2), m.group(3)
        lines = body.split("\n")
        prefix = []
        vals = []
        for line in lines:
            if not vals and (line.strip() == "" or line.strip().startswith("//")):
                prefix.append(line)
            else:
                vals.append(line)
        raw = "\n".join(vals).strip("\n").strip()
        total += 1
        zh = cache.get(raw, raw)
        if zh != raw:
            hit += 1
        new_body = "\n".join(prefix)
        if prefix and not new_body.endswith("\n"):
            new_body += "\n"
        if not prefix:
            new_body = "\n"
        new_body += zh + "\n"
        out.append(header + new_body + close)
        last = m.end()
    out.append(en_text[last:])
    return "".join(out), hit, total


def apply_jass(en_text: str, cache: dict[str, str]) -> tuple[str, int, int]:
    """Replace string literals whose unescaped content is in cache. Longest-first safe via exact match only."""
    # Build set of sources present; replace by scanning literals
    hit = 0
    total = 0
    parts: list[str] = []
    last = 0
    # Sort cache keys by length desc for any bulk ops — here we match exact unescaped
    for m in JASS_STR.finditer(en_text):
        parts.append(en_text[last : m.start()])
        raw_esc = m.group(1)
        raw = unescape_jass(raw_esc)
        if raw in cache and cache[raw] != raw:
            total += 1
            hit += 1
            zh = cache[raw]
            parts.append('"' + escape_jass(zh) + '"')
        else:
            if raw in cache:
                total += 1  # counted as attempted known string but same
            parts.append(m.group(0))
        last = m.end()
    parts.append(en_text[last:])
    return "".join(parts), hit, total


def apply_jass_known(en_text: str, cache: dict[str, str], known: set[str]) -> tuple[str, int, int]:
    """Only replace literals that were extracted (known set)."""
    hit = 0
    total = 0
    parts: list[str] = []
    last = 0
    for m in JASS_STR.finditer(en_text):
        parts.append(en_text[last : m.start()])
        raw_esc = m.group(1)
        raw = unescape_jass(raw_esc)
        if raw in known:
            total += 1
            zh = cache.get(raw, raw)
            if zh != raw:
                hit += 1
                parts.append('"' + escape_jass(zh) + '"')
            else:
                parts.append(m.group(0))
        else:
            parts.append(m.group(0))
        last = m.end()
    parts.append(en_text[last:])
    return "".join(parts), hit, total


def load_known_sources(jsonl: Path) -> set[str]:
    known: set[str] = set()
    if not jsonl.exists():
        return known
    with jsonl.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            known.add(obj["source"])
    return known


def run_tool(args: list[str]) -> None:
    cmd = [str(TOOL)] + args
    print("RUN:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"tool failed: {cmd} rc={r.returncode}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--map", type=Path, default=DEFAULT_MAP)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--jsonl", type=Path, default=ROOT / "gaias/cache/en_strings.jsonl")
    ap.add_argument("--skip-build", action="store_true")
    args = ap.parse_args()

    if not TOOL.exists():
        raise SystemExit(f"missing tool: {TOOL}")
    if not args.map.exists():
        raise SystemExit(f"missing map: {args.map}")

    cache = load_cache(args.cache)
    known = load_known_sources(args.jsonl)
    print(f"cache={len(cache)} known_sources={len(known)}")

    BUILD.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    en_wts = (EXTRACT / "war3map.wts").read_text(encoding="utf-8", errors="replace")
    zh_wts, wh, wt = apply_wts(en_wts, cache)
    wts_out = BUILD / "war3map.wts"
    wts_out.write_text(zh_wts, encoding="utf-8")
    print(f"WTS: translated_blocks={wh}/{wt} -> {wts_out}")

    en_j = (EXTRACT / "war3map.j").read_text(encoding="utf-8", errors="replace")
    if known:
        zh_j, jh, jt = apply_jass_known(en_j, cache, known)
    else:
        zh_j, jh, jt = apply_jass(en_j, cache)
    j_out = BUILD / "war3map.j"
    j_out.write_text(zh_j, encoding="utf-8")
    print(f"JASS: replaced_literals={jh}/{jt} -> {j_out}")

    if args.skip_build:
        print("skip-build: done")
        return

    shutil.copy2(args.map, args.out)
    # Gaia/Sunken-style protected maps scramble MPQ headerSize; StormLib can read
    # but refuses writes (add/remove fail with err=1). Restore classic headerSize=32.
    import struct
    raw = bytearray(args.out.read_bytes())
    if raw[:4] == b"MPQ\x1a":
        old_hs = struct.unpack_from("<I", raw, 4)[0]
        if old_hs != 32:
            struct.pack_into("<I", raw, 4, 32)
            args.out.write_bytes(raw)
            print(f"fixed MPQ headerSize {old_hs} -> 32")
    # Prefer locale path for wts; root war3map.j for script
    # Try inject locale wts; also replace root wts as fallback safety
    locale_wts = r"_Locales\zhCN.w3mod\war3map.wts"
    try:
        run_tool(["replace", str(args.out), locale_wts, str(wts_out)])
    except SystemExit as e:
        print(f"WARN locale wts inject failed ({e}), will still replace root war3map.wts")
    run_tool(["replace", str(args.out), "war3map.wts", str(wts_out)])
    run_tool(["replace", str(args.out), "war3map.j", str(j_out)])

    sz = args.out.stat().st_size
    print(f"OUT {args.out} size={sz}")


if __name__ == "__main__":
    main()
