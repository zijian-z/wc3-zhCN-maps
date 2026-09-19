#!/usr/bin/env python3
"""Extract unique EN player-facing strings from Gaia WTS + JASS into JSONL."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WTS = ROOT / "gaias/extract/war3map.wts"
DEFAULT_JASS = ROOT / "gaias/extract/war3map.j"
DEFAULT_OUT = ROOT / "gaias/cache/en_strings.jsonl"

WTS_PAT = re.compile(r"(STRING\s+(\d+)\s*(?://[^\n]*)?\s*\{)(.*?)(\})", re.S)
# JASS string literals (handles \" and \\)
JASS_STR = re.compile(r'"((?:\\.|[^"\\])*)"')

URLISH = re.compile(r"^(https?://\S+|discord\.gg/\S+|www\.\S+)$", re.I)
PURE_NUM = re.compile(r"^-?\d+(\.\d+)?$")
PLACEHOLDER_ONLY = re.compile(
    r"^(%\d+%|%s|%d|\|n|\|r|\|c[0-9A-Fa-f]{8})+$", re.I
)
# 4-char WC3 rawcodes like hfoo, A000, B00A (letters+digits)
RAWCODE = re.compile(r"^[A-Za-z0-9]{4}$")
# file/asset paths
ASSET_EXT = re.compile(
    r"\.(mdx|mdl|blp|tga|wav|mp3|ogg|slk|txt|fdf|w3[a-z]|jpg|png|dds)$",
    re.I,
)
PATHISH = re.compile(r"^[A-Za-z0-9_./\\-]+\.(mdx|mdl|blp|tga|wav|mp3|ogg|slk)$", re.I)
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
UDG = re.compile(r"^udg_", re.I)
TRIGSTR = re.compile(r"^TRIGSTR_\d+$", re.I)
# mostly code-like: no spaces, no |c, short, looks like identifier path
CODELIKE = re.compile(r"^[A-Za-z0-9_.:\\/-]+$")

# Must look human: has space OR color code OR punctuation prose
HAS_LETTER = re.compile(r"[A-Za-z]")


def unescape_jass(s: str) -> str:
    # JASS uses \\ and \"
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


def should_skip_wts(text: str) -> bool:
    s = text.strip()
    if not s:
        return True
    if PURE_NUM.match(s):
        return True
    if URLISH.match(s):
        return True
    if PLACEHOLDER_ONLY.match(s.replace(" ", "")):
        return True
    return False


def should_skip_jass(text: str) -> bool:
    s = text.strip()
    if not s:
        return True
    if PURE_NUM.match(s):
        return True
    if URLISH.match(s):
        return True
    if TRIGSTR.match(s):
        return True
    if UDG.match(s):
        return True
    if RAWCODE.match(s):
        return True
    if PATHISH.match(s):
        return True
    # asset / path / font / sound / model fragments
    low = s.lower()
    if any(low.endswith(ext) for ext in (
        ".mdx", ".mdl", ".blp", ".tga", ".wav", ".mp3", ".ogg", ".slk",
        ".fdf", ".toc", ".ttf", ".flac", ".pld", ".jpg", ".png", ".dds",
    )):
        return True
    if "fonts\\" in low or "fonts/" in low or "war3mapimported" in low:
        return True
    if ".mdl$" in low or ".mdx$" in low:
        return True
    if ASSET_EXT.search(s) and ("\\" in s or "/" in s or "$" in s):
        return True
    # JASS/code injection fragments (not English "call")
    if "endfunction" in low or "blzset" in low or "takes nothing" in low:
        return True
    if "\ncall " in s or "\nfunction " in s or s.lstrip().startswith("call "):
        return True
    if PLACEHOLDER_ONLY.match(s.replace(" ", "")):
        return True
    # tiny color/punctuation leftovers
    if re.fullmatch(r"[\]|r.%()\s]+", s, re.I):
        return True
    if s in {"|r.", "%|r", "]|r", ")|r", "|r"}:
        return True
    if s.strip() in {".txt", ":|r"} or s.strip().startswith(":|r"):
        return True
    if s.endswith(".txt") and " " not in s and len(s) < 40:
        return True
    # charset dumps
    if "ABCDEFGHIJKLMNOPQRSTUVWXYZ" in s and "abcdefghijklmnopqrstuvwxyz" in s.replace("`", ""):
        return True
    if s.startswith(" !#$%&") or "0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ" in s:
        return True
    if re.fullmatch(r"[0-9A-Fa-f]+", s) and len(s) <= 16:
        return True
    # pure identifiers (event names, frame names without spaces)
    if IDENT.match(s) and " " not in s and "|c" not in low and "|n" not in low:
        return True
    # skip code-like no-space strings that aren't prose
    if " " not in s and "|c" not in low and "|n" not in low:
        if CODELIKE.match(s) and not any(ch in s for ch in "!?.,:;'\""):
            if "-" not in s and "_" not in s and len(s) <= 3:
                return True
            if "_" in s or (
                s[:1].isupper()
                and any(c.isupper() for c in s[1:])
                and any(c.islower() for c in s)
            ):
                return True
            if not (s.isupper() and len(s) <= 12 and "_" not in s):
                if CODELIKE.match(s):
                    return True
    if not HAS_LETTER.search(s):
        return True
    # garbage tokens
    if re.search(r"[*]{1,}|&\^|sd\d{2,}", s) and " " not in s and len(s) < 40:
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
        raw = "\n".join(vals).strip("\n").strip()
        if should_skip_wts(raw):
            continue
        rows.append({"id": f"wts:{sid}", "source": raw, "kind": "wts", "key": sid})
    return rows


def extract_jass(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    rows = []
    seen_pos = 0
    idx = 0
    for m in JASS_STR.finditer(text):
        raw_esc = m.group(1)
        raw = unescape_jass(raw_esc)
        if should_skip_jass(raw):
            continue
        idx += 1
        rows.append(
            {
                "id": f"jass:{idx}",
                "source": raw,
                "kind": "jass",
                "key": f"{m.start()}",
            }
        )
    return rows


def dedupe_keep_order(rows: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for r in rows:
        src = r["source"]
        if src in seen:
            seen[src].setdefault("also_ids", []).append(r["id"])
            continue
        seen[src] = dict(r)
    return list(seen.values())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wts", type=Path, default=DEFAULT_WTS)
    ap.add_argument("--jass", type=Path, default=DEFAULT_JASS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--kinds", default="wts,jass")
    args = ap.parse_args()
    kinds = {k.strip() for k in args.kinds.split(",") if k.strip()}

    rows: list[dict] = []
    if "wts" in kinds and args.wts.exists():
        rows.extend(extract_wts(args.wts))
    if "jass" in kinds and args.jass.exists():
        rows.extend(extract_jass(args.jass))

    unique = dedupe_keep_order(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for r in unique:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_kind_raw: dict[str, int] = {}
    by_kind_uniq: dict[str, int] = {}
    for r in rows:
        by_kind_raw[r["kind"]] = by_kind_raw.get(r["kind"], 0) + 1
    for r in unique:
        by_kind_uniq[r["kind"]] = by_kind_uniq.get(r["kind"], 0) + 1
    chars = sum(len(r["source"]) for r in unique)
    print(
        f"extracted raw={len(rows)} unique={len(unique)} chars={chars} "
        f"raw_by_kind={by_kind_raw} uniq_by_kind={by_kind_uniq} -> {args.out}"
    )


if __name__ == "__main__":
    main()
