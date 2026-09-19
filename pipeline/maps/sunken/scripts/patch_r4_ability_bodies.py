#!/usr/bin/env python3
"""Rebuild Sunken City zhCN r4: WTS ability bodies + safe JASS UI literals.

- WTS-only replace from original English map (r3 Chinese WTS as base, fill remaining EN bodies from packy cache)
- Optional safe JASS string literal patches (multiboard, DPS, secondary-stat tooltips, hints)
- NEVER CompactArchive. No GitHub release.
- war3map.wts: UTF-8 BOM + CRLF
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/w3x_replace_nocompact"
ORIG = ROOT / "maps/Sunken_City_v2.5.2a.w3x"
R3_WTS = ROOT / "sunken/build/war3map_r3_bom.wts"
CACHE = ROOT / "sunken/cache/packy_zh.json"
JASS_REPL = ROOT / "sunken/cache/r4_jass_replacements.json"
BUILD = ROOT / "sunken/build"
OUT = ROOT / "sunken/out/Sunken_City_v2.5.2a_zhCN_r4.w3x"
LOCALE_WTS = r"_Locales\zhCN.w3mod\war3map.wts"
JASS_PATH = r"scripts\war3map.j"

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
WTS_PAT = re.compile(r"(STRING\s+(\d+)\s*(?://[^\n]*)?\s*\{)(.*?)(\})", re.S)
KW = re.compile(
    r"(Type:|Damage:|Mana|Cooldown|chance|Passive:|Active:|Learns?\s|Requires\s|"
    r"Level\s|Ability|Cast|Duration|Radius|Range|Health|Armor|Mastery|"
    r"Specialization|Summoning|Magical|Physical|Healing|increases?|reduces?|"
    r"deals?|restores?|grants?|spawns?)",
    re.I,
)


def run_tool(args: list[str]) -> None:
    cmd = [str(TOOL), *args]
    print("RUN:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"tool failed rc={r.returncode}: {cmd}")


def mostly_en(body: str) -> bool:
    s = re.sub(r"\|c[0-9A-Fa-f]{8}", "", body)
    s = re.sub(r"\|[rRnN]", "", s).strip()
    if not s:
        return False
    cjk = len(CJK_RE.findall(s))
    latin = len(LATIN_RE.findall(s))
    if latin < 8:
        return False
    if cjk == 0 and latin >= 8:
        return True
    if latin > 0 and cjk / max(latin, 1) < 0.15 and latin >= 20:
        return True
    if cjk < 5 and latin >= 30:
        return True
    return False


def should_translate(body: str) -> bool:
    if not mostly_en(body):
        return False
    src = body.strip()
    if len(src) < 40 and not KW.search(src):
        if re.search(r"[+%]\d|Mana|Health|Armor|Speed|Damage", src, re.I):
            return True
        return False
    return True


def lookup_zh(cache: dict[str, str], body: str) -> str | None:
    cands = [
        body.strip(),
        body.replace("\r\n", "\n").strip("\n").strip(),
        body.replace("\r\n", "\n").strip(),
        body.strip("\r\n"),
    ]
    for c in cands:
        if c in cache and CJK_RE.search(cache[c]):
            zh = cache[c].replace("\r\n", "\n").replace("\r", "\n")
            lead = "\n" if body.startswith("\n") or body.startswith("\r\n") else ""
            trail = "\n" if body.endswith("\n") or body.endswith("\r\n") else ""
            if lead and not zh.startswith("\n"):
                zh = lead + zh
            if trail and not zh.endswith("\n"):
                zh = zh + trail
            return zh
    return None


def to_bom_crlf(text: str) -> bytes:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    return b"\xef\xbb\xbf" + text.encode("utf-8")


def patch_wts(r3_text: str, cache: dict[str, str]) -> tuple[str, dict]:
    stats = {
        "total": 0,
        "candidates": 0,
        "replaced": 0,
        "miss": 0,
        "before_en": 0,
        "after_en": 0,
    }
    parts: list[str] = []
    last = 0
    entries: list[str] = []

    for m in WTS_PAT.finditer(r3_text):
        stats["total"] += 1
        body = m.group(3)
        if mostly_en(body):
            stats["before_en"] += 1
        new_body = body
        if should_translate(body):
            stats["candidates"] += 1
            zh = lookup_zh(cache, body)
            if zh is not None and zh.replace("\r\n", "\n") != body.replace("\r\n", "\n"):
                new_body = zh
                stats["replaced"] += 1
            else:
                stats["miss"] += 1
        entries.append(new_body)
        parts.append(r3_text[last : m.start(3)])
        parts.append(new_body)
        last = m.end(3)
    parts.append(r3_text[last:])
    out = "".join(parts)
    for b in entries:
        if mostly_en(b):
            stats["after_en"] += 1
    return out, stats


def patch_jass(orig_j: bytes, repl: dict) -> tuple[bytes, dict]:
    """Apply only known EN→ZH literal replacements; verify reverse-diff."""
    text = orig_j.decode("utf-8")
    info = {"replacements": 0, "kinds": {}}

    def do_replace(en: str, zh: str, kind: str) -> None:
        nonlocal text
        c = text.count(en)
        if c == 0:
            print(f"WARN missing {kind}: {en[:60]!r}")
            return
        text = text.replace(en, zh)
        info["replacements"] += c
        info["kinds"][kind] = info["kinds"].get(kind, 0) + c
        print(f"JASS {kind}: x{c} {en[:50]!r} -> {zh[:50]!r}")

    for en, zh in repl.get("simple_ui", []):
        do_replace(en, zh, "ui")

    for en_full, zh_full in repl.get("title_assignments", []):
        do_replace(en_full, zh_full, "title")

    for en, zh in repl.get("tooltip_texts", []):
        do_replace(en, zh, "tooltip_text")

    as_en, as_zh = repl.get("as_fragment", [None, None])
    if as_en and as_zh:
        do_replace(as_en, as_zh, "as_fragment")

    for en, zh in repl.get("hints", []):
        do_replace(en, zh, "hint")

    new_b = text.encode("utf-8")
    delta = len(new_b) - len(orig_j)
    info["delta_bytes"] = delta
    print(f"JASS delta_bytes={delta} total_repl={info['replacements']}")
    return new_b, info


def verify_jass_only_intended(orig: bytes, new: bytes, repl: dict) -> None:
    """Ensure applying the same replacements to orig yields new (no extras)."""
    text = orig.decode("utf-8")
    for en, zh in repl.get("simple_ui", []):
        text = text.replace(en, zh)
    for en_full, zh_full in repl.get("title_assignments", []):
        text = text.replace(en_full, zh_full)
    for en, zh in repl.get("tooltip_texts", []):
        text = text.replace(en, zh)
    as_en, as_zh = repl.get("as_fragment", [None, None])
    if as_en and as_zh:
        text = text.replace(as_en, as_zh)
    for en, zh in repl.get("hints", []):
        text = text.replace(en, zh)
    if text.encode("utf-8") != new:
        raise SystemExit("FAIL: JASS has unexpected diffs beyond intended replacements")


def main() -> None:
    if not TOOL.exists():
        raise SystemExit(f"missing tool: {TOOL}")
    if not ORIG.exists():
        raise SystemExit(f"missing original: {ORIG}")
    if not R3_WTS.exists():
        raise SystemExit(f"missing r3 WTS: {R3_WTS}")
    if not CACHE.exists():
        raise SystemExit(f"missing cache: {CACHE}")
    if not JASS_REPL.exists():
        raise SystemExit(f"missing jass replacements: {JASS_REPL}")

    BUILD.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    repl = json.loads(JASS_REPL.read_text(encoding="utf-8"))
    r3_text = R3_WTS.read_bytes().decode("utf-8-sig")

    new_text, stats = patch_wts(r3_text, cache)
    print("WTS stats:", stats)

    fixed = to_bom_crlf(new_text)
    wts_out = BUILD / "war3map_r4_bom.wts"
    wts_out.write_bytes(fixed)

    m1 = re.search(r"STRING\s+1\s*(?://[^\n]*)?\s*\{(.*?)\}", fixed.decode("utf-8-sig"), re.S)
    if not m1 or "【汉化】" not in m1.group(1):
        raise SystemExit("STRING 1 missing 【汉化】")
    if fixed[:3] != b"\xef\xbb\xbf":
        raise SystemExit("BOM missing")
    if fixed.count(b"\n") != fixed.count(b"\r\n"):
        raise SystemExit("CRLF incomplete")

    check = fixed.decode("utf-8-sig")
    m11133 = re.search(r"STRING\s+11133\s*(?://[^\n]*)?\s*\{(.*?)\}", check, re.S)
    if m11133:
        b = m11133.group(1)
        print(
            f"STRING 11133 cjk={bool(CJK_RE.search(b))} "
            f"still_en={('Surrounds an ally' in b)}"
        )

    print(
        f"WTS: size={len(fixed)} md5={hashlib.md5(fixed).hexdigest()} "
        f"before_en={stats['before_en']} after_en={stats['after_en']}"
    )

    # JASS from original
    j_orig_path = BUILD / "r4_orig_scripts_war3map.j"
    run_tool(["extract", str(ORIG), JASS_PATH, str(j_orig_path)])
    j_orig = j_orig_path.read_bytes()
    j_new, jinfo = patch_jass(j_orig, repl)
    j_out = BUILD / "war3map_r4.j"
    j_out.write_bytes(j_new)
    verify_jass_only_intended(j_orig, j_new, repl)
    print("OK: JASS only intended literals patched")

    shutil.copy2(ORIG, OUT)
    run_tool(["replace", str(OUT), "war3map.wts", str(wts_out)])
    run_tool(["replace", str(OUT), LOCALE_WTS, str(wts_out)])
    run_tool(["replace", str(OUT), JASS_PATH, str(j_out)])

    j_check = BUILD / "r4_out_scripts_war3map.j"
    run_tool(["extract", str(OUT), JASS_PATH, str(j_check)])
    if j_check.read_bytes() != j_new:
        raise SystemExit("FAIL: output JASS != patched")

    # quick content checks
    jt = j_check.read_text(encoding="utf-8")
    for needle in ["玩家信息", "时间：", "DPS统计", "生命回复", "法力回复", "急速", "多面板"]:
        print(f"JASS has {needle!r}: {needle in jt}")

    print(f"OUT {OUT} size={OUT.stat().st_size}")
    print(f"STATS {json.dumps(stats, ensure_ascii=False)}")
    print(f"JASS_INFO {json.dumps(jinfo, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
