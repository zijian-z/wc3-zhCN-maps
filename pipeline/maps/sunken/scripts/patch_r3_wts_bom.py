#!/usr/bin/env python3
"""Rebuild Sunken City zhCN r3: WTS-only with UTF-8 BOM + CRLF (lobby metadata fix).

Does NOT touch war3map.j or skin binaries. NEVER CompactArchive.
No GitHub release.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/w3x_replace_nocompact"
ORIG = ROOT / "maps/Sunken_City_v2.5.2a.w3x"
R2 = ROOT / "sunken/out/Sunken_City_v2.5.2a_zhCN_r2.w3x"
OUT = ROOT / "sunken/out/Sunken_City_v2.5.2a_zhCN_r3.w3x"
BUILD = ROOT / "sunken/build"
LOCALE_WTS = r"_Locales\zhCN.w3mod\war3map.wts"


def run_tool(args: list[str]) -> None:
    cmd = [str(TOOL), *args]
    print("RUN:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"tool failed rc={r.returncode}: {cmd}")


def extract_wts_bytes(map_path: Path, archive_path: str, dest: Path) -> bytes:
    run_tool(["extract", str(map_path), archive_path, str(dest)])
    return dest.read_bytes()


def to_bom_crlf(raw: bytes) -> bytes:
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    text = raw.decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    return b"\xef\xbb\xbf" + text.encode("utf-8")


def main() -> None:
    if not TOOL.exists():
        raise SystemExit(f"missing tool: {TOOL}")
    if not ORIG.exists():
        raise SystemExit(f"missing original map: {ORIG}")
    if not R2.exists():
        raise SystemExit(f"missing r2 map (zh WTS source): {R2}")

    BUILD.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    tmp = BUILD / "r3_src_war3map.wts"
    zh_raw = extract_wts_bytes(R2, "war3map.wts", tmp)
    fixed = to_bom_crlf(zh_raw)
    wts_out = BUILD / "war3map_r3_bom.wts"
    wts_out.write_bytes(fixed)

    # Sanity on Chinese metadata strings
    text = fixed.decode("utf-8-sig")
    for n in (1, 3):
        m = re.search(rf"STRING\s+{n}\s*(?://[^\n]*)?\s*\{{(.*?)}}", text, re.S)
        if not m or "【汉化】" not in m.group(1):
            raise SystemExit(f"STRING {n} missing 【汉化】 tag")
    if fixed[:3] != b"\xef\xbb\xbf":
        raise SystemExit("BOM missing after rewrite")
    if b"\r\n" not in fixed or fixed.count(b"\n") != fixed.count(b"\r\n"):
        raise SystemExit("CRLF rewrite incomplete")

    crlf_n = fixed.count(bytes([13, 10]))
    print(
        f"WTS fixed: size={len(fixed)} bom=True crlf={crlf_n} "
        f"md5={hashlib.md5(fixed).hexdigest()}"
    )

    shutil.copy2(ORIG, OUT)
    run_tool(["replace", str(OUT), "war3map.wts", str(wts_out)])
    run_tool(["replace", str(OUT), LOCALE_WTS, str(wts_out)])

    # Verify JASS unchanged vs original
    j_orig = BUILD / "r3_orig_scripts_war3map.j"
    j_new = BUILD / "r3_out_scripts_war3map.j"
    extract_wts_bytes(ORIG, r"scripts\war3map.j", j_orig)
    extract_wts_bytes(OUT, r"scripts\war3map.j", j_new)
    if j_orig.read_bytes() != j_new.read_bytes():
        raise SystemExit("FAIL: scripts\\war3map.j changed vs original")
    print("OK: scripts\\war3map.j byte-identical to original")
    print(f"OUT {OUT} size={OUT.stat().st_size}")


if __name__ == "__main__":
    main()
