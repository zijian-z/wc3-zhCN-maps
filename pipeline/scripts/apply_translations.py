#!/usr/bin/env python3
"""Apply cache translations onto zhCN.w3mod files (EN fallback for misses)."""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN_ROOT = ROOT / "wowr/wowr.w3x"
ZH_ROOT = ROOT / "wowr/wowr.w3x/_Locales/zhCN.w3mod"
DEFAULT_CACHE = ROOT / "cache/packy_zh.json"

WTS_PAT = re.compile(r"(STRING\s+\d+\s*(?://[^\n]*)?\s*\{)(.*?)(\})", re.S)
FDF_PAT = re.compile(
    r"^(\s*)([A-Za-z0-9_]+)(\s*)\"(.*)\"(\s*,?\s*)$", re.M
)


def load_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items()}


def ensure_scaffold() -> None:
    ZH_ROOT.mkdir(parents=True, exist_ok=True)
    (ZH_ROOT / "wowr").mkdir(parents=True, exist_ok=True)
    pairs = [
        (EN_ROOT / "war3map.wts", ZH_ROOT / "war3map.wts"),
        (EN_ROOT / "war3mapMisc.txt", ZH_ROOT / "war3mapMisc.txt"),
        (
            EN_ROOT / "wowr/WoWReforgedStrings.fdf",
            ZH_ROOT / "wowr/WoWReforgedStrings.fdf",
        ),
    ]
    for src, dst in pairs:
        if not dst.exists():
            shutil.copy2(src, dst)


def wts_body_raw(body: str) -> str:
    lines = body.split("\n")
    vals = []
    for line in lines:
        if not vals and (line.strip() == "" or line.strip().startswith("//")):
            continue
        vals.append(line)
    return "\n".join(vals).strip("\n").strip()


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


def apply_fdf(en_text: str, cache: dict[str, str]) -> tuple[str, int, int]:
    if en_text.startswith("\ufeff"):
        en_text = en_text[1:]
    hit = 0
    total = 0

    def repl(m: re.Match) -> str:
        nonlocal hit, total
        indent, key, sp, val, trailing = m.groups()
        total += 1
        # source may have had missing space: normalize to "KEY  \"val\","
        zh = cache.get(val, val)
        if zh != val:
            hit += 1
        # escape quotes in translation if any
        zh_esc = zh.replace('"', '\\"')
        # keep original spacing style when present; else single spaces
        if not sp:
            sp = " "
        return f'{indent}{key}{sp}"{zh_esc}"{trailing}'

    # Also handle missing-space form: KEY"value",
    text = FDF_PAT.sub(repl, en_text)
    # Fix rare KEY"val" without space already covered by \s*
    return text, hit, total


def apply_misc(en_text: str, cache: dict[str, str]) -> tuple[str, int, int]:
    hit = 0
    total = 0
    out_lines = []
    for line in en_text.splitlines():
        if "=" in line and not line.strip().startswith("["):
            k, v = line.split("=", 1)
            if k.strip().lower() == "name":
                total += 1
                zh = cache.get(v.strip(), v.strip())
                if zh != v.strip():
                    hit += 1
                out_lines.append(f"{k}={zh}")
                continue
        out_lines.append(line)
    # preserve final newline if original had one
    result = "\n".join(out_lines)
    if en_text.endswith("\n"):
        result += "\n"
    return result, hit, total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--from-en", action="store_true",
                    help="Rebuild zh files from EN sources + cache (default)")
    args = ap.parse_args()

    ensure_scaffold()
    cache = load_cache(args.cache)
    print(f"cache entries: {len(cache)}")

    # Always start from EN sources so partial cache safely leaves EN
    en_wts = (EN_ROOT / "war3map.wts").read_text(encoding="utf-8", errors="replace")
    zh_wts, wh, wt = apply_wts(en_wts, cache)
    (ZH_ROOT / "war3map.wts").write_text(zh_wts, encoding="utf-8")
    print(f"WTS: translated {wh}/{wt} blocks -> {ZH_ROOT / 'war3map.wts'}")

    en_fdf = (EN_ROOT / "wowr/WoWReforgedStrings.fdf").read_text(
        encoding="utf-8", errors="replace"
    )
    zh_fdf, fh, ft = apply_fdf(en_fdf, cache)
    (ZH_ROOT / "wowr/WoWReforgedStrings.fdf").write_text(zh_fdf, encoding="utf-8")
    print(f"FDF: translated {fh}/{ft} entries -> {ZH_ROOT / 'wowr/WoWReforgedStrings.fdf'}")

    en_misc = (EN_ROOT / "war3mapMisc.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    zh_misc, mh, mt = apply_misc(en_misc, cache)
    (ZH_ROOT / "war3mapMisc.txt").write_text(zh_misc, encoding="utf-8")
    print(f"Misc: translated {mh}/{mt} Name fields -> {ZH_ROOT / 'war3mapMisc.txt'}")


if __name__ == "__main__":
    main()
