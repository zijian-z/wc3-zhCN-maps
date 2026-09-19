#!/usr/bin/env python3
"""Apply Packy cache to Sunken WTS+JASS and build zhCN .w3x via w3x_replace_nocompact."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTRACT = ROOT / "sunken/extract"
BUILD = ROOT / "sunken/build"
OUT_DIR = ROOT / "sunken/out"
DEFAULT_CACHE = ROOT / "sunken/cache/packy_zh.json"
DEFAULT_MAP = ROOT / "maps/Sunken_City_v2.5.2a.w3x"
DEFAULT_OUT = OUT_DIR / "Sunken_City_v2.5.2a_zhCN.w3x"
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


def tag_metadata_wts(text: str) -> tuple[str, int]:
    """Mark the map-list title and description so zhCN builds are obvious."""
    changed = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal changed
        body = m.group(2)
        stripped = body.strip()
        if not stripped or stripped.startswith("【汉化】"):
            return m.group(0)
        lead = body[: len(body) - len(body.lstrip())]
        trail = body[len(body.rstrip()) :]
        changed += 1
        return m.group(1) + lead + "【汉化】" + stripped + trail + m.group(3)

    out = re.sub(r"(STRING\s+(?:1|3)\s*(?://[^\n]*)?\s*\{)(.*?)(\})", repl, text, flags=re.S)
    return out, changed


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
    ap.add_argument("--jsonl", type=Path, default=ROOT / "sunken/cache/en_strings.jsonl")
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
    zh_wts, metadata_hits = tag_metadata_wts(zh_wts)
    wts_out = BUILD / "war3map.wts"
    wts_out.write_text(zh_wts, encoding="utf-8")
    print(f"WTS: translated_blocks={wh}/{wt}, metadata_tags={metadata_hits} -> {wts_out}")

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
    # Prefer locale path for wts; root war3map.j for script
    # Try inject locale wts; also replace root wts as fallback safety
    locale_wts = r"_Locales\zhCN.w3mod\war3map.wts"
    try:
        run_tool(["replace", str(args.out), locale_wts, str(wts_out)])
    except SystemExit as e:
        print(f"WARN locale wts inject failed ({e}), will still replace root war3map.wts")
    run_tool(["replace", str(args.out), "war3map.wts", str(wts_out)])
    # Reforged maps store script under scripts\\war3map.j
    try:
        run_tool(["replace", str(args.out), "scripts\\war3map.j", str(j_out)])
    except SystemExit as e:
        print(f"WARN scripts\\war3map.j replace failed ({e}), trying root war3map.j")
        run_tool(["replace", str(args.out), "war3map.j", str(j_out)])

    # Sunken City ships custom object tables in the Skin files. Most display
    # values are TRIGSTR references resolved by the translated WTS; preserve
    # and explicitly replace each table so the zhCN archive carries the full
    # matching object set.
    for skin_name in ("war3mapSkin.w3u", "war3mapSkin.w3t", "war3mapSkin.w3a", "war3mapSkin.w3b"):
        skin_src = EXTRACT / skin_name
        if not skin_src.exists():
            continue
        skin_dst = BUILD / skin_name
        shutil.copy2(skin_src, skin_dst)
        run_tool(["replace", str(args.out), skin_name, str(skin_dst)])
        print(f"SKIN: applied {skin_name} (display refs resolve through WTS)")

    sz = args.out.stat().st_size
    print(f"OUT {args.out} size={sz}")


if __name__ == "__main__":
    main()
