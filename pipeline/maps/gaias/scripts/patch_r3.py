#!/usr/bin/env python3
"""Gaias zhCN r3: patch war3mapSkin object strings + jass leftovers + rebuild (no Compact)."""
from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path("/workspace/wc3-map-l10n")
EXTRACT = ROOT / "gaias/extract"
BUILD = ROOT / "gaias/build"
OUT = ROOT / "gaias/out/GaiasORPG_v1_3A_12_zhCN.w3x"
SRC_MAP = ROOT / "maps/GaiasORPG_v1_3A_12.w3x"
TOOL = ROOT / "tools/w3x_replace_nocompact"
CACHE_PATH = ROOT / "gaias/cache/packy_zh.json"
GLOSSARY_PATH = ROOT / "scripts/glossary.tsv"

CLASS_EXACT = {
    "Thief": "盗贼",
    "Valkyrie": "瓦尔基里",
    "Ranger": "游侠",
    "Squire": "侍从",
    "Cleric": "牧师",
    "Magician": "魔术师",
    "Berserker": "狂战士",
    "Crusader": "十字军",
    "Assassin": "刺客",
    "Bard": "吟游诗人",
    "Sorcerer": "巫师",
    "Necromancer": "死灵法师",
    "Monk": "武僧",
    "Bishop": "主教",
    "Druid": "德鲁伊",
    "Hunter": "猎人",
    "Mystic": "秘术师",
    "Psion": "灵能者",
    "Hexblade": "咒刃",
    "Farmer": "农夫",
    "Farmer Greavus": "农夫格里瓦斯",
    "Training Dagger": "训练匕首",
}

LABEL_REPLACEMENTS = [
    ("Armor type:", "护甲类型："),
    ("Weapon type:", "武器类型："),
    ("Misc Item type:", "杂项物品类型："),
    ("Requirement:", "需求："),
]

JASS_EXACT = {
    "Recipe": "配方",
    "Mount": "坐骑",
}

TEXT_FIELDS = {
    "w3u": {"unam", "upro", "utip", "utub", "unsf"},
    "w3t": {"unam", "utip", "utub", "ides", "unsf"},
    "w3a": {"anam", "aub1", "atp1", "ansf", "aret", "arut"},
    "w3b": {"fnam", "ftip", "fube", "fnsf"},
}

JASS_STR = re.compile(r'"((?:\\.|[^"\\])*)"')


def load_glossary() -> dict[str, str]:
    g = dict(CLASS_EXACT)
    if GLOSSARY_PATH.exists():
        for line in GLOSSARY_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "\t" not in line:
                continue
            a, b = line.split("\t", 1)
            g.setdefault(a.strip(), b.strip())
    return g


def load_cache() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    return {str(k): str(v) for k, v in json.loads(CACHE_PATH.read_text(encoding="utf-8")).items()}


def unescape_jass(s: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            mapping = {'"': '"', "\\": "\\", "n": "\n", "t": "\t"}
            out.append(mapping.get(nxt, nxt))
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


def is_path_like(s: str) -> bool:
    return any(x in s for x in ("\\", ".mdl", ".mdx", ".blp", ".tga", ".wav", ".mp3"))


def translate_text(s: str, cache: dict[str, str], gloss: dict[str, str]) -> str:
    if not s or not s.strip() or is_path_like(s):
        return s
    if len(re.findall(r"[\u4e00-\u9fff]", s)) > len(re.findall(r"[A-Za-z]", s)):
        return s

    if s in gloss:
        return gloss[s]
    if s in cache:
        return cache[s]

    # |cffXXXXXXName|r exact
    m = re.fullmatch(r"(\|c[0-9A-Fa-f]{8})(.+)(\|r)", s)
    if m:
        inner = m.group(2)
        if inner in gloss:
            return m.group(1) + gloss[inner] + m.group(3)
        if inner in cache:
            return m.group(1) + cache[inner] + m.group(3)

    # Keep English Recipe:/Collection: prefix for GetObjectName logic
    for prefix in ("Recipe: ", "Recipe:", "Collection: ", "Collection:"):
        if s.startswith(prefix):
            rest = s[len(prefix) :]
            if rest in gloss:
                return prefix + gloss[rest]
            if rest in cache:
                return prefix + cache[rest]
            full = cache.get(s)
            if full:
                rest_zh = re.sub(r"^配方[:：]\s*", "", full)
                return prefix + rest_zh
            return s

    out = s
    for en, zh in LABEL_REPLACEMENTS:
        out = out.replace(en, zh)
    for en, zh in sorted(CLASS_EXACT.items(), key=lambda x: -len(x[0])):
        out = re.sub(rf"(?<![A-Za-z]){re.escape(en)}(?![A-Za-z])", zh, out)

    if out != s:
        return out
    return cache.get(s, s)


def patch_object_file(
    src: Path,
    dst: Path,
    fields: set[str],
    cache: dict[str, str],
    gloss: dict[str, str],
    has_level: bool,
) -> dict[str, int]:
    data = memoryview(src.read_bytes())
    off = 0
    ver = struct.unpack_from("<I", data, off)[0]
    off += 4
    out = bytearray()
    out += struct.pack("<I", ver)
    stats = {"fields": 0, "changed": 0}

    for _table in range(2):
        count = struct.unpack_from("<I", data, off)[0]
        out += struct.pack("<I", count)
        off += 4
        for _ in range(count):
            out += bytes(data[off : off + 4]); off += 4  # oid
            out += bytes(data[off : off + 4]); off += 4  # nid
            if ver >= 3:
                out += bytes(data[off : off + 8]); off += 8
            nmod = struct.unpack_from("<I", data, off)[0]
            out += struct.pack("<I", nmod)
            off += 4
            for __ in range(nmod):
                mid_b = bytes(data[off : off + 4]); off += 4
                out += mid_b
                mid = mid_b.decode("latin1")
                vtype = struct.unpack_from("<I", data, off)[0]
                out += struct.pack("<I", vtype)
                off += 4
                if has_level:
                    out += bytes(data[off : off + 8]); off += 8
                if vtype == 0:
                    out += bytes(data[off : off + 4]); off += 4
                elif vtype in (1, 2):
                    out += bytes(data[off : off + 4]); off += 4
                elif vtype == 3:
                    end = bytes(data).find(b"\x00", off)
                    raw = bytes(data[off:end])
                    off = end + 1
                    val = raw.decode("utf-8", "replace")
                    if mid in fields and not is_path_like(val):
                        stats["fields"] += 1
                        new_val = translate_text(val, cache, gloss)
                        if new_val != val:
                            stats["changed"] += 1
                            val = new_val
                    out += val.encode("utf-8") + b"\x00"
                else:
                    raise ValueError(f"bad vtype {vtype} at {off}")
                out += bytes(data[off : off + 4]); off += 4
    if off != len(data):
        raise RuntimeError(f"parse incomplete {src}: {off}/{len(data)}")
    dst.write_bytes(out)
    return stats


def decode_mdk(edk: str) -> str:
    out = []
    for i in range(0, len(edk), 3):
        try:
            q = int(edk[i : i + 3]) - 66
        except ValueError:
            continue
        if 32 <= q <= 126:
            out.append(chr(q))
    return "".join(out)


def encode_mdk(s: str) -> str:
    return "".join(f"{ord(c) + 66:03d}" for c in s)


def patch_jass(text: str, cache: dict[str, str], gloss: dict[str, str]) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {"Recipe": 0, "Mount": 0, "mDK": 0, "Farmer_hook": 0}

    # Only translate OiH("Recipe"/"Mount") display categories; keep GetObjectName
    # prefix checks (oiH=="Recipe") in English so object-name logic still works.
    out = text
    for en, zh in JASS_EXACT.items():
        out, n1 = re.subn(rf'OiH\("{en}"', f'OiH("{zh}"', out)
        counts[en] = n1

    def repl_mdk(m: re.Match) -> str:
        en = decode_mdk(m.group(1))
        if not en:
            return m.group(0)
        zh = translate_text(en, cache, gloss)
        if zh == en:
            zh = cache.get(en, gloss.get(en, en))
        # mDK only supports ASCII 32-126; skip if Chinese produced
        if any(ord(c) > 126 for c in zh):
            # Keep English for mDK (encoding limitation) — will rely on other channels
            return m.group(0)
        if zh != en:
            counts["mDK"] += 1
            return f'mDK("{encode_mdk(zh)}")'
        return m.group(0)

    out = re.sub(r'mDK\("([0-9]+)"\)', repl_mdk, out)

    helper = """
function ZhCN_RenameUnits takes nothing returns nothing
local group zg=CreateGroup()
local unit zu
local string zn
call GroupEnumUnitsInRect(zg,bj_mapInitialPlayableArea,null)
loop
set zu=FirstOfGroup(zg)
exitwhen zu==null
set zn=GetUnitName(zu)
if zn=="Farmer" or zn=="Farmer Greavus" or zn=="Farmer Greavus" or zn=="农夫格里瓦斯" then
call BlzSetUnitName(zu,"农夫")
call BlzSetUnitProperName(zu,"格里瓦斯")
elseif zn=="农夫" then
call BlzSetUnitProperName(zu,"格里瓦斯")
endif
call GroupRemoveUnit(zg,zu)
endloop
call DestroyGroup(zg)
set zg=null
set zu=null
endfunction
"""

    if "function ZhCN_RenameUnits" in out:
        out = re.sub(
            r"function ZhCN_RenameUnits takes nothing returns nothing.*?endfunction\n",
            helper.lstrip() + "\n",
            out,
            count=1,
            flags=re.S,
        )
    else:
        out = out.replace(
            "function main takes nothing returns nothing",
            helper.lstrip() + "\nfunction main takes nothing returns nothing",
            1,
        )
    counts["Farmer_hook"] = 1

    # Remove prior one-shot only; install one-shot + periodic
    out = out.replace("call TimerStart(CreateTimer(),1.,false,function ZhCN_RenameUnits)\n", "")
    out = out.replace("call TimerStart(CreateTimer(),0.5,false,function ZhCN_RenameUnits)\n", "")
    out = out.replace("call TimerStart(CreateTimer(),5.,true,function ZhCN_RenameUnits)\n", "")
    inject = (
        "call TimerStart(CreateTimer(),0.5,false,function ZhCN_RenameUnits)\n"
        "call TimerStart(CreateTimer(),5.,true,function ZhCN_RenameUnits)\n"
    )
    if "call ubK()\n" in out:
        out = out.replace("call ubK()\n", "call ubK()\n" + inject, 1)
    else:
        out = out.replace(
            "function main takes nothing returns nothing\n",
            "function main takes nothing returns nothing\n" + inject,
            1,
        )
    return out, counts


def run_tool(args: list[str]) -> None:
    cmd = [str(TOOL)] + args
    print("RUN:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"tool failed rc={r.returncode}")


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    cache = load_cache()
    gloss = load_glossary()
    print(f"cache={len(cache)} gloss={len(gloss)}")

    for kind, fields in TEXT_FIELDS.items():
        src = EXTRACT / f"war3mapSkin.{kind}"
        if not src.exists():
            run_tool(["extract", str(SRC_MAP), f"war3mapSkin.{kind}", str(src)])
        dst = BUILD / f"war3mapSkin.{kind}"
        st = patch_object_file(src, dst, fields, cache, gloss, has_level=(kind == "w3a"))
        print(f"SKIN {kind}: scanned={st['fields']} changed={st['changed']} -> {dst.stat().st_size}")

    j_path = BUILD / "war3map.j"
    j_text = j_path.read_text(encoding="utf-8", errors="replace")
    j_new, j_counts = patch_jass(j_text, cache, gloss)
    j_path.write_text(j_new, encoding="utf-8")
    print(f"JASS: {j_counts}")

    # Rebuild from EN source
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_MAP, OUT)
    raw = bytearray(OUT.read_bytes())
    if raw[:4] == b"MPQ\x1a":
        old_hs = struct.unpack_from("<I", raw, 4)[0]
        if old_hs != 32:
            struct.pack_into("<I", raw, 4, 32)
            OUT.write_bytes(raw)
            print(f"fixed MPQ headerSize {old_hs} -> 32")

    wts = BUILD / "war3map.wts"
    w3i = BUILD / "war3map.w3i"
    skin_txt = BUILD / "war3mapSkin.txt"
    if not skin_txt.exists():
        skin_txt = EXTRACT / "war3mapSkin.txt"

    try:
        run_tool(["replace", str(OUT), r"_Locales\zhCN.w3mod\war3map.wts", str(wts)])
    except SystemExit as e:
        print(f"WARN locale wts: {e}")

    for arc, path in [
        ("war3map.wts", wts),
        ("war3map.j", j_path),
        ("war3map.w3i", w3i),
        ("war3mapSkin.txt", skin_txt),
        ("war3mapSkin.w3u", BUILD / "war3mapSkin.w3u"),
        ("war3mapSkin.w3t", BUILD / "war3mapSkin.w3t"),
        ("war3mapSkin.w3a", BUILD / "war3mapSkin.w3a"),
        ("war3mapSkin.w3b", BUILD / "war3mapSkin.w3b"),
    ]:
        if not path.exists():
            print(f"SKIP missing {path}")
            continue
        run_tool(["replace", str(OUT), arc, str(path)])

    print(f"OUT {OUT} size={OUT.stat().st_size}")


if __name__ == "__main__":
    main()
