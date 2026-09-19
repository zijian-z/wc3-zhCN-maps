#!/usr/bin/env python3
"""Gaias zhCN r9: same tip quality as r8, no periodic timers (fix stutter).

Same as r8 tip generation (level 0/1 expand, ResearchTooltip mirror, A050 Attack
override), but timer policy is one-shot only:
- ZhCN_RenameAll at 0.5 / 2.0 / 8.0 / 20.0s (false) — covers late class select
- AbilityTips only piggybacked via RenameAll (no separate / repeating tips timer)
- Removed r8's TimerStart(...,5.,true,RenameAll) and (...,10.,true,AbilityTips)

Hard rules (unchanged):
- NEVER CompactArchive
- NEVER rewrite war3mapSkin.w3u/w3t/w3a binary
- ONLY patch war3map.j via tools/w3x_replace_nocompact
- Valid natives only — NEVER BlzSetUnitProperName
"""
from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path("/workspace/wc3-map-l10n")
OUT = ROOT / "gaias/out/GaiasORPG_v1_3A_12_zhCN.w3x"
BACKUP_R6 = ROOT / "gaias/out/GaiasORPG_v1_3A_12_zhCN.r6-base.w3x"
BACKUP_R7 = ROOT / "gaias/out/GaiasORPG_v1_3A_12_zhCN-r7.w3x"
BACKUP_R8 = ROOT / "gaias/out/GaiasORPG_v1_3A_12_zhCN-r8.w3x"
BUILD = ROOT / "gaias/build"
EXTRACT = ROOT / "gaias/extract"
TOOL = ROOT / "tools/w3x_replace_nocompact"
CACHE_PATH = ROOT / "gaias/cache/packy_zh.json"
GLOSSARY_PATH = ROOT / "scripts/glossary.tsv"
SKIN_W3A = EXTRACT / "war3mapSkin.w3a"
WTS_PATH = EXTRACT / "war3map.wts"
J_OUT = BUILD / "war3map.j.r9"

TIP_FIELDS = {"atp1", "aub1", "aret", "arut"}
FIELD_NATIVE = {
    "atp1": "BlzSetAbilityTooltip",
    "aub1": "BlzSetAbilityExtendedTooltip",
    "aret": "BlzSetAbilityResearchTooltip",
    "arut": "BlzSetAbilityResearchExtendedTooltip",
}

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
    "Servant of Nature": "自然仆从",
    "Servant of the Skies": "天空仆从",
}

RENAME_HELPER = r'''
function ZhCN_RenameUnits takes nothing returns nothing
local group zg=CreateGroup()
local unit zu
local string zn
call GroupEnumUnitsInRect(zg,bj_mapInitialPlayableArea,null)
loop
set zu=FirstOfGroup(zg)
exitwhen zu==null
set zn=GetUnitName(zu)
if zn=="Farmer Greavus" then
call BlzSetUnitName(zu,"农夫")
call BlzSetHeroProperName(zu,"格里瓦斯")
elseif zn=="Farmer" then
call BlzSetUnitName(zu,"农夫")
elseif zn=="Thief" then
call BlzSetUnitName(zu,"盗贼")
call BlzSetHeroProperName(zu,"盗贼")
elseif zn=="Valkyrie" then
call BlzSetUnitName(zu,"瓦尔基里")
call BlzSetHeroProperName(zu,"瓦尔基里")
elseif zn=="Ranger" then
call BlzSetUnitName(zu,"游侠")
call BlzSetHeroProperName(zu,"游侠")
elseif zn=="Squire" then
call BlzSetUnitName(zu,"侍从")
call BlzSetHeroProperName(zu,"侍从")
elseif zn=="Cleric" then
call BlzSetUnitName(zu,"牧师")
call BlzSetHeroProperName(zu,"牧师")
elseif zn=="Magician" then
call BlzSetUnitName(zu,"魔术师")
call BlzSetHeroProperName(zu,"魔术师")
elseif zn=="Berserker" then
call BlzSetUnitName(zu,"狂战士")
call BlzSetHeroProperName(zu,"狂战士")
elseif zn=="Crusader" then
call BlzSetUnitName(zu,"十字军")
call BlzSetHeroProperName(zu,"十字军")
elseif zn=="Assassin" then
call BlzSetUnitName(zu,"刺客")
call BlzSetHeroProperName(zu,"刺客")
elseif zn=="Bard" then
call BlzSetUnitName(zu,"吟游诗人")
call BlzSetHeroProperName(zu,"吟游诗人")
elseif zn=="Sorcerer" then
call BlzSetUnitName(zu,"巫师")
call BlzSetHeroProperName(zu,"巫师")
elseif zn=="Necromancer" then
call BlzSetUnitName(zu,"死灵法师")
call BlzSetHeroProperName(zu,"死灵法师")
elseif zn=="Monk" then
call BlzSetUnitName(zu,"武僧")
call BlzSetHeroProperName(zu,"武僧")
elseif zn=="Bishop" then
call BlzSetUnitName(zu,"主教")
call BlzSetHeroProperName(zu,"主教")
elseif zn=="Druid" then
call BlzSetUnitName(zu,"德鲁伊")
call BlzSetHeroProperName(zu,"德鲁伊")
elseif zn=="Hunter" then
call BlzSetUnitName(zu,"猎人")
call BlzSetHeroProperName(zu,"猎人")
elseif zn=="Mystic" then
call BlzSetUnitName(zu,"秘术师")
call BlzSetHeroProperName(zu,"秘术师")
elseif zn=="Psion" then
call BlzSetUnitName(zu,"灵能者")
call BlzSetHeroProperName(zu,"灵能者")
elseif zn=="Hexblade" then
call BlzSetUnitName(zu,"咒刃")
call BlzSetHeroProperName(zu,"咒刃")
endif
call GroupRemoveUnit(zg,zu)
endloop
call DestroyGroup(zg)
set zg=null
set zu=null
endfunction

function ZhCN_RenameItems_Enum takes nothing returns nothing
local item zi=GetEnumItem()
local string zn
if zi!=null then
set zn=GetItemName(zi)
if zn=="Training Dagger" then
call BlzSetItemName(zi,"训练匕首")
endif
endif
set zi=null
endfunction

function ZhCN_RenameItems takes nothing returns nothing
call EnumItemsInRect(bj_mapInitialPlayableArea,null,function ZhCN_RenameItems_Enum)
endfunction

function ZhCN_RenameAll takes nothing returns nothing
call ZhCN_RenameUnits()
call ZhCN_RenameItems()
call ZhCN_AbilityTips()
endfunction
'''


def run_tool(args: list[str]) -> None:
    cmd = [str(TOOL)] + args
    print("RUN:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"tool failed rc={r.returncode}")


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


def parse_wts(path: Path) -> dict[int, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"(?m)^STRING\s+(\d+)\s*$", text)
    wts: dict[int, str] = {}
    for i in range(1, len(parts), 2):
        sid = int(parts[i])
        body = parts[i + 1].strip()
        if body.startswith("{"):
            body = body[1:]
        if body.endswith("}"):
            body = body[:-1]
        if body.startswith("\n"):
            body = body[1:]
        if body.endswith("\n"):
            body = body[:-1]
        wts[sid] = body
    return wts


def parse_w3a(path: Path) -> list[tuple[str, list[tuple[str, int, int, object]]]]:
    """Parse ability object file. ver>=3 has +8 bytes per object."""
    data = memoryview(path.read_bytes())
    off = 0
    ver = struct.unpack_from("<I", data, off)[0]
    off += 4
    objects: list[tuple[str, list[tuple[str, int, int, object]]]] = []
    for _table in range(2):
        count = struct.unpack_from("<I", data, off)[0]
        off += 4
        for _ in range(count):
            oid = bytes(data[off : off + 4])
            off += 4
            nid = bytes(data[off : off + 4])
            off += 4
            if ver >= 3:
                off += 8
            nmod = struct.unpack_from("<I", data, off)[0]
            off += 4
            mods: list[tuple[str, int, int, object]] = []
            for __ in range(nmod):
                mid = bytes(data[off : off + 4]).decode("latin1")
                off += 4
                vtype = struct.unpack_from("<I", data, off)[0]
                off += 4
                level = struct.unpack_from("<I", data, off)[0]
                off += 4
                off += 4  # data pointer
                if vtype == 0:
                    val: object = struct.unpack_from("<I", data, off)[0]
                    off += 4
                elif vtype in (1, 2):
                    val = struct.unpack_from("<f", data, off)[0]
                    off += 4
                elif vtype == 3:
                    end = off
                    while data[end] != 0:
                        end += 1
                    val = bytes(data[off:end]).decode("utf-8", errors="replace")
                    off = end + 1
                else:
                    raise ValueError(f"unknown vtype {vtype} at {off}")
                off += 4  # end mark
                mods.append((mid, vtype, level, val))
            code = (nid if nid != b"\x00\x00\x00\x00" else oid).decode("latin1")
            objects.append((code, mods))
    if off != len(data):
        raise RuntimeError(f"w3a parse incomplete: off={off} size={len(data)}")
    return objects


def resolve_text(s: str, wts: dict[int, str]) -> str:
    if s.startswith("TRIGSTR_"):
        try:
            return wts.get(int(s.split("_", 1)[1]), s)
        except ValueError:
            return s
    return s


def looks_en(s: str) -> bool:
    if not s or not s.strip():
        return False
    if any(x in s for x in ("\\", ".mdl", ".mdx", ".blp", ".tga", ".wav", ".mp3")):
        return False
    zh = len(re.findall(r"[\u4e00-\u9fff]", s))
    en = len(re.findall(r"[A-Za-z]", s))
    return en > zh and en > 2


def looks_zh(s: str) -> bool:
    zh = len(re.findall(r"[\u4e00-\u9fff]", s))
    en = len(re.findall(r"[A-Za-z]", s))
    return zh > 0 and zh >= en * 0.3


def escape_jass(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace("\t", "\\t")
    )


def rawcode_hex(code: str) -> str:
    if len(code) != 4:
        raise ValueError(code)
    n = (ord(code[0]) << 24) | (ord(code[1]) << 16) | (ord(code[2]) << 8) | ord(code[3])
    return f"${n:08X}"


def translate_text(s: str, cache: dict[str, str], gloss: dict[str, str], name_map: dict[str, str]) -> str | None:
    """Return zh string, or None if still English / untranslated (skip emit)."""
    if not looks_en(s):
        return s if s.strip() else None
    if s in gloss:
        return gloss[s]
    if s in cache and looks_zh(cache[s]):
        return cache[s]
    if s in name_map:
        return name_map[s]

    # Learn |cffName|r
    m = re.fullmatch(r"(Learn\s+)(\|c[0-9A-Fa-f]{8})(.+?)(\|r)", s)
    if m:
        inner = m.group(3)
        zh = name_map.get(inner) or gloss.get(inner) or cache.get(inner)
        if zh and looks_zh(zh):
            return f"学习 {m.group(2)}{zh}{m.group(4)}"

    # |cffName|r (|cffHotkey|r)
    m = re.fullmatch(
        r"(\|c[0-9A-Fa-f]{8})(.+?)(\|r)\s*(\(\|c[0-9A-Fa-f]{8})(.+?)(\|r\))",
        s,
    )
    if m:
        inner = m.group(2)
        zh = name_map.get(inner) or gloss.get(inner) or cache.get(inner)
        if zh and (looks_zh(zh) or zh != inner):
            return f"{m.group(1)}{zh}{m.group(3)} {m.group(4)}{m.group(5)}{m.group(6)}"

    # Learn Name [|cff Level %d|r]
    m = re.fullmatch(r"Learn (.+?) (\[\|c[0-9A-Fa-f]{8}Level %d\|r\])", s)
    if m:
        inner = m.group(1)
        zh = name_map.get(inner) or gloss.get(inner) or cache.get(inner)
        if zh:
            return f"学习 {zh} {m.group(2).replace('Level ', '等级 ')}"

    # Learn Talent: |cff...|r
    m = re.fullmatch(r"Learn Talent: (\|c[0-9A-Fa-f]{8})(.+?)(\|r)", s)
    if m:
        inner = m.group(2)
        zh_inner = inner.replace("Level ", "等级 ") if inner.startswith("Level ") else (
            name_map.get(inner) or gloss.get(inner) or cache.get(inner) or inner
        )
        return f"学习天赋：{m.group(1)}{zh_inner}{m.group(3)}"

    m = re.fullmatch(r"Learn Ability \((\|c[0-9A-Fa-f]{8})Rank (\d+)(\|r)\)", s)
    if m:
        return f"学习技能 ({m.group(1)}等级 {m.group(2)}{m.group(3)})"

    if s in cache:
        # cache hit but may still be EN copy — only use if improved
        if cache[s] != s:
            return cache[s]
    return None


def build_name_map(objects, wts, cache, gloss) -> dict[str, str]:
    nm = dict(gloss)
    for code, mods in objects:
        for mid, vtype, level, val in mods:
            if mid != "anam" or not isinstance(val, str):
                continue
            raw = resolve_text(val, wts).strip()
            if not raw or raw.startswith("Dummy") or raw.startswith("+"):
                continue
            if raw in gloss:
                nm[raw] = gloss[raw]
            elif raw in cache and looks_zh(cache[raw]):
                nm[raw] = cache[raw]
    return nm


def collect_tip_calls(
    objects,
    wts: dict[int, str],
    cache: dict[str, str],
    gloss: dict[str, str],
    name_map: dict[str, str],
) -> tuple[list[tuple[str, str, int, str]], dict[str, int]]:
    """Return list of (abil_hex, native, level, zh_text) and stats."""
    stats = {
        "mods": 0,
        "emitted": 0,
        "skipped_en": 0,
        "skipped_same": 0,
        "by_field": {f: 0 for f in TIP_FIELDS},
    }
    seen: set[tuple[str, str, int]] = set()
    out: list[tuple[str, str, int, str]] = []

    for code, mods in objects:
        # skip pure editor dummies with no useful tips? still allow learn/cast tips
        anam = ""
        for mid, vtype, level, val in mods:
            if mid == "anam" and isinstance(val, str):
                anam = resolve_text(val, wts)
                break
        if anam.startswith("Dummy") and not any(
            mid in TIP_FIELDS and isinstance(val, str) and "Learn" in str(val)
            for mid, _, _, val in mods
        ):
            # still process if has real atp1/aub1 that aren't dummy
            pass

        for mid, vtype, level, val in mods:
            if mid not in TIP_FIELDS or not isinstance(val, str) or not val.strip():
                continue
            stats["mods"] += 1
            text = resolve_text(val, wts)
            if not text.strip():
                continue
            zh = translate_text(text, cache, gloss, name_map)
            if zh is None:
                stats["skipped_en"] += 1
                continue
            if zh == text and looks_en(text):
                stats["skipped_same"] += 1
                continue
            key = (code, mid, level)
            if key in seen:
                continue
            seen.add(key)
            try:
                hx = rawcode_hex(code)
            except ValueError:
                continue
            native = FIELD_NATIVE[mid]
            out.append((hx, native, int(level), zh))
            stats["emitted"] += 1
            stats["by_field"][mid] += 1
    return out, stats



def expand_levels(calls: list[tuple[str, str, int, str]]) -> list[tuple[str, str, int, str]]:
    """Reforged quirk: ensure level 0 and 1 exist without overwriting real tips.

    Original (abil, native, level) entries always win. Missing 0/1 are filled
    from the other (prefer 1 for filling 0, prefer 0 for filling 1, else lowest).
    """
    by: dict[tuple[str, str], dict[int, str]] = {}
    for hx, native, level, zh in calls:
        slot = by.setdefault((hx, native), {})
        if level not in slot:
            slot[level] = zh
    out: list[tuple[str, str, int, str]] = []
    for (hx, native), lvmap in by.items():
        if 0 not in lvmap:
            lvmap[0] = lvmap.get(1) or lvmap[min(lvmap)]
        if 1 not in lvmap:
            lvmap[1] = lvmap.get(0) or lvmap[min(lvmap)]
        for level, zh in sorted(lvmap.items()):
            out.append((hx, native, level, zh))
    return out


def mirror_learn_to_research(
    calls: list[tuple[str, str, int, str]],
) -> list[tuple[str, str, int, str]]:
    """Learn cards (AZ*) often store Learn text in atp1/aub1 only.

    Command-card Learn hover uses ResearchTooltip/ResearchExtendedTooltip.
    Mirror Tooltip->ResearchTooltip and Extended->ResearchExtended when the
    tip text looks like a Learn string, or when Research* is missing for that
    ability but we have Learn Tooltip + Extended.
    """
    by_abil: dict[str, list[tuple[str, int, str]]] = {}
    existing_research: set[tuple[str, str, int]] = set()
    for hx, native, level, zh in calls:
        by_abil.setdefault(hx, []).append((native, level, zh))
        if native in (
            "BlzSetAbilityResearchTooltip",
            "BlzSetAbilityResearchExtendedTooltip",
        ):
            existing_research.add((hx, native, level))

    extra: list[tuple[str, str, int, str]] = []
    for hx, entries in by_abil.items():
        tips = [(lv, zh) for n, lv, zh in entries if n == "BlzSetAbilityTooltip"]
        exts = [(lv, zh) for n, lv, zh in entries if n == "BlzSetAbilityExtendedTooltip"]
        learn_tips = [(lv, zh) for lv, zh in tips if ("学习" in zh) or ("Learn" in zh)]
        if not learn_tips:
            continue
        for lv, zh in learn_tips:
            key = (hx, "BlzSetAbilityResearchTooltip", lv)
            if key not in existing_research:
                extra.append((hx, "BlzSetAbilityResearchTooltip", lv, zh))
                existing_research.add(key)
        # Prefer matching-level extended; else any extended for this abil
        for lv, zh in learn_tips:
            ext_zh = None
            for elv, ezh in exts:
                if elv == lv:
                    ext_zh = ezh
                    break
            if ext_zh is None and exts:
                ext_zh = exts[0][1]
            if ext_zh is None:
                continue
            key = (hx, "BlzSetAbilityResearchExtendedTooltip", lv)
            if key not in existing_research:
                extra.append((hx, "BlzSetAbilityResearchExtendedTooltip", lv, ext_zh))
                existing_research.add(key)
    return calls + extra



# Skin.w3a reuses multilevel slots: A050 L1 title is Attack but aub1 is pet-release text.
# Override command-card extended tips for known EN command abilities.
COMMAND_CARD_EXT = {
    # A050 Attack (|cffffcc00X|r) — parent-suggested command description
    "$41303530": "命令单位攻击目标单位或建筑。|n也可指定地面：单位将移动到目标区域并沿途攻击敌人。",
}


def apply_command_card_overrides(
    calls: list[tuple[str, str, int, str]],
) -> list[tuple[str, str, int, str]]:
    """Fix wrong multilevel-reused ExtendedTooltip on Attack etc. for levels 0/1."""
    out: list[tuple[str, str, int, str]] = []
    overridden: set[tuple[str, int]] = set()
    for hx, native, level, zh in calls:
        if (
            hx in COMMAND_CARD_EXT
            and native == "BlzSetAbilityExtendedTooltip"
            and level in (0, 1)
        ):
            zh = COMMAND_CARD_EXT[hx]
            overridden.add((hx, level))
        out.append((hx, native, level, zh))
    # Ensure override exists even if aub1 missing
    for hx, tip in COMMAND_CARD_EXT.items():
        for lv in (0, 1):
            if (hx, lv) not in overridden:
                out.append((hx, "BlzSetAbilityExtendedTooltip", lv, tip))
    return out


def chunk_functions(calls: list[tuple[str, str, int, str]], chunk_size: int = 400) -> str:
    """Split into ZhCN_AbilityTips_N helpers + dispatcher to avoid huge single fn."""
    parts: list[str] = []
    nchunks = max(1, (len(calls) + chunk_size - 1) // chunk_size) if calls else 1
    if not calls:
        parts.append(
            "function ZhCN_AbilityTips takes nothing returns nothing\nendfunction\n"
        )
        return "".join(parts)

    for ci in range(nchunks):
        batch = calls[ci * chunk_size : (ci + 1) * chunk_size]
        name = f"ZhCN_AbilityTips_{ci}" if nchunks > 1 else "ZhCN_AbilityTips"
        lines = [f"function {name} takes nothing returns nothing"]
        for hx, native, level, zh in batch:
            lines.append(f'call {native}({hx},"{escape_jass(zh)}",{level})')
        lines.append("endfunction")
        parts.append("\n".join(lines) + "\n\n")

    if nchunks > 1:
        lines = ["function ZhCN_AbilityTips takes nothing returns nothing"]
        for ci in range(nchunks):
            lines.append(f"call ZhCN_AbilityTips_{ci}()")
        lines.append("endfunction")
        parts.append("\n".join(lines) + "\n")
    return "".join(parts)


def strip_old_zhcn(text: str) -> str:
    # Remove prior ZhCN helpers (rename + ability tips variants)
    text = re.sub(
        r"function ZhCN_(?:Rename(?:Units|Items|Items_Enum|All)|AbilityTips(?:_\d+)?) takes nothing returns nothing.*?endfunction\n+",
        "",
        text,
        flags=re.S,
    )
    for old in (
        "call TimerStart(CreateTimer(),1.,false,function ZhCN_RenameUnits)\n",
        "call TimerStart(CreateTimer(),0.5,false,function ZhCN_RenameUnits)\n",
        "call TimerStart(CreateTimer(),5.,true,function ZhCN_RenameUnits)\n",
        "call TimerStart(CreateTimer(),0.5,false,function ZhCN_RenameAll)\n",
        "call TimerStart(CreateTimer(),2.,false,function ZhCN_RenameAll)\n",
        "call TimerStart(CreateTimer(),5.,true,function ZhCN_RenameAll)\n",
        "call TimerStart(CreateTimer(),8.,false,function ZhCN_RenameAll)\n",
        "call TimerStart(CreateTimer(),20.,false,function ZhCN_RenameAll)\n",
        "call TimerStart(CreateTimer(),0.5,false,function ZhCN_AbilityTips)\n",
        "call TimerStart(CreateTimer(),2.,false,function ZhCN_AbilityTips)\n",
        "call TimerStart(CreateTimer(),5.,false,function ZhCN_AbilityTips)\n",
        "call TimerStart(CreateTimer(),15.,false,function ZhCN_AbilityTips)\n",
        "call TimerStart(CreateTimer(),10.,true,function ZhCN_AbilityTips)\n",
        "call ZhCN_AbilityTips()\n",
    ):
        text = text.replace(old, "")
    return text


def verify_jass(text: str) -> None:
    if "BlzSetUnitProperName" in text:
        # only fail if we introduced it in ZhCN section
        zhcn = "\n".join(
            m.group(0)
            for m in re.finditer(
                r"function ZhCN_.*?endfunction", text, flags=re.S
            )
        )
        if "BlzSetUnitProperName" in zhcn:
            raise RuntimeError("ZhCN helpers contain forbidden BlzSetUnitProperName")
    # quote balance in ZhCN_AbilityTips bodies (rough)
    for m in re.finditer(
        r"function ZhCN_AbilityTips.*?(?=function |\Z)", text, flags=re.S
    ):
        block = m.group(0)
        # count unescaped quotes roughly via strip escapes
        tmp = re.sub(r'\\.', '', block)
        if tmp.count('"') % 2 != 0:
            raise RuntimeError("unbalanced quotes in ZhCN_AbilityTips block")


def patch_jass(text: str, tips_jass: str) -> tuple[str, dict[str, int]]:
    counts = {"Recipe": 0, "Mount": 0, "helper": 0, "timers": 0, "tips": 0}
    text, n = re.subn(r'OiH\("Recipe"', 'OiH("配方"', text)
    counts["Recipe"] = n
    text, n = re.subn(r'OiH\("Mount"', 'OiH("坐骑"', text)
    counts["Mount"] = n

    text = strip_old_zhcn(text)

    if "function main takes nothing returns nothing" not in text:
        raise RuntimeError("main() not found")

    inject_helpers = tips_jass.rstrip() + "\n\n" + RENAME_HELPER.lstrip() + "\n"
    text = text.replace(
        "function main takes nothing returns nothing",
        inject_helpers + "function main takes nothing returns nothing",
        1,
    )
    counts["helper"] = 1
    counts["tips"] = 1

    # One-shot only: RenameAll piggybacks AbilityTips (no repeating timers).
    inject = (
        "call TimerStart(CreateTimer(),0.5,false,function ZhCN_RenameAll)\n"
        "call TimerStart(CreateTimer(),2.,false,function ZhCN_RenameAll)\n"
        "call TimerStart(CreateTimer(),8.,false,function ZhCN_RenameAll)\n"
        "call TimerStart(CreateTimer(),20.,false,function ZhCN_RenameAll)\n"
    )
    if "call ubK()\n" in text:
        text = text.replace("call ubK()\n", "call ubK()\n" + inject, 1)
        counts["timers"] = 4
    else:
        text = text.replace(
            "function main takes nothing returns nothing\n",
            "function main takes nothing returns nothing\n" + inject,
            1,
        )
        counts["timers"] = 4
    return text, counts


def main() -> None:
    if not OUT.exists():
        raise SystemExit(f"missing map: {OUT}")
    if not SKIN_W3A.exists():
        raise SystemExit(f"missing {SKIN_W3A}")

    BUILD.mkdir(parents=True, exist_ok=True)
    cache = load_cache()
    gloss = load_glossary()
    wts = parse_wts(WTS_PATH)
    print(f"cache={len(cache)} gloss={len(gloss)} wts={len(wts)}")

    objects = parse_w3a(SKIN_W3A)
    print(f"Skin.w3a objects={len(objects)}")
    name_map = build_name_map(objects, wts, cache, gloss)
    print(f"name_map={len(name_map)}")

    calls, stats = collect_tip_calls(objects, wts, cache, gloss, name_map)
    print(f"tip stats: {stats}")
    print(f"calls raw: {len(calls)}")

    n_before_mirror = len(calls)
    calls = mirror_learn_to_research(calls)
    print(f"after learn->research mirror: {len(calls)} (+{len(calls)-n_before_mirror})")
    n_before_lvl = len(calls)
    calls = expand_levels(calls)
    print(f"after level 0/1 expand: {len(calls)} (+{len(calls)-n_before_lvl})")
    calls = apply_command_card_overrides(calls)
    print(f"after command-card overrides: {len(calls)}")

    # Prefer openable: require a minimum coverage of known strings
    servant_ok = any("自然仆从" in zh for *_, zh in calls)
    print(f"servant_zh_present={servant_ok}")
    if len(calls) < 50:
        raise SystemExit(f"too few tip calls ({len(calls)}); wait for Packy cache")

    tips_jass = chunk_functions(calls, chunk_size=450)
    verify_jass(tips_jass + RENAME_HELPER)

    # Prefer openable r6 base; fall back to current OUT (r7)
    base = BACKUP_R6 if BACKUP_R6.exists() else OUT
    print(f"base map: {base}")
    run_tool(["extract", str(base), "war3map.j", str(J_OUT)])
    j_text = J_OUT.read_text(encoding="utf-8", errors="replace")
    j_new, counts = patch_jass(j_text, tips_jass)
    verify_jass(j_new)
    zhcn_region = j_new[j_new.find("function ZhCN_") : j_new.find("function main takes")]
    if "BlzSetUnitProperName" in zhcn_region:
        raise SystemExit("forbidden BlzSetUnitProperName in ZhCN region")

    J_OUT.write_text(j_new, encoding="utf-8")
    print(f"JASS patch counts: {counts}")
    print(f"j size {len(j_text)} -> {len(j_new)} (+{len(j_new)-len(j_text)})")

    # Preserve prior artifacts if missing
    if OUT.exists() and not BACKUP_R7.exists():
        shutil.copy2(OUT, BACKUP_R7)
        print(f"backed up r7 -> {BACKUP_R7}")
    if base != OUT:
        shutil.copy2(base, OUT)
        print(f"copied base -> OUT for replace")

    run_tool(["replace", str(OUT), "war3map.j", str(J_OUT)])
    print(f"OUT {OUT} size={OUT.stat().st_size}")

    verify_path = BUILD / "war3map.j.r9.verify"
    run_tool(["extract", str(OUT), "war3map.j", str(verify_path)])
    v = verify_path.read_text(encoding="utf-8", errors="replace")
    assert "function ZhCN_AbilityTips" in v
    assert "function ZhCN_RenameAll" in v
    assert "自然仆从" in v
    # One-shot RenameAll schedule (tips piggybacked)
    assert "call TimerStart(CreateTimer(),0.5,false,function ZhCN_RenameAll)" in v
    assert "call TimerStart(CreateTimer(),2.,false,function ZhCN_RenameAll)" in v
    assert "call TimerStart(CreateTimer(),8.,false,function ZhCN_RenameAll)" in v
    assert "call TimerStart(CreateTimer(),20.,false,function ZhCN_RenameAll)" in v
    # NO repeating ZhCN timers
    assert "5.,true,function ZhCN_RenameAll" not in v
    assert "10.,true,function ZhCN_AbilityTips" not in v
    assert not re.search(r"TimerStart\([^)]*,\s*true\s*,\s*function ZhCN_", v)
    # RenameAll piggybacks AbilityTips
    assert "call ZhCN_AbilityTips()" in v
    assert ("学习|cffffff00自然仆从" in v) or ("学习 |cffffff00自然仆从" in v)
    # ResearchTooltip for Learn Servant (AZ2M = $415A324D)
    assert 'BlzSetAbilityResearchTooltip($415A324D,' in v
    # A050 Attack extended tip override
    assert "$41303530" in v
    zhcn_blocks = "\n".join(
        m.group(0)
        for m in re.finditer(
            r"function ZhCN_AbilityTips.*?(?=function ZhCN_Rename|function main)",
            v,
            flags=re.S,
        )
    )
    n_zhcn = zhcn_blocks.count("BlzSetAbility")
    n_research = zhcn_blocks.count("BlzSetAbilityResearchTooltip")
    has_lvl0 = ',"0)' in zhcn_blocks or '",0)' in zhcn_blocks
    print(f"verify: ZhCN BlzSet={n_zhcn} researchTips={n_research} lvl0={has_lvl0} servant=True")
    # Dexterous Shot / 灵巧射击
    assert "灵巧射击" in v
    timer_lines = [
        ln.strip()
        for ln in v.splitlines()
        if "TimerStart" in ln and "ZhCN_" in ln
    ]
    print("ZhCN TimerStart lines:")
    for ln in timer_lines:
        print(" ", ln)
    meta = {
        "release": "r9",
        "calls": len(calls),
        "stats": stats,
        "j_delta": len(j_new) - len(j_text),
        "servant_zh": True,
        "research_az2m": True,
        "out_size": OUT.stat().st_size,
        "n_zhcn_blz": n_zhcn,
        "n_research_tooltip": n_research,
        "timers": timer_lines,
        "no_repeating_zhcn_timers": True,
    }
    (BUILD / "r9_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    # r9 snapshot + keep pipeline default name in sync
    snap = ROOT / "gaias/out/GaiasORPG_v1_3A_12_zhCN-r9.w3x"
    shutil.copy2(OUT, snap)
    print(f"snap {snap} size={snap.stat().st_size}")
    print("OK r9 patch complete", meta)


if __name__ == "__main__":
    main()
