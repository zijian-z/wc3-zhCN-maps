#!/usr/bin/env python3
"""Gaias zhCN r5: JASS-only runtime renames on playable r4 base. NEVER touch Skin.w3u/w3t/w3a."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/workspace/wc3-map-l10n")
OUT = ROOT / "gaias/out/GaiasORPG_v1_3A_12_zhCN.w3x"
BUILD = ROOT / "gaias/build"
TOOL = ROOT / "tools/w3x_replace_nocompact"
BACKUP = ROOT / "gaias/out/GaiasORPG_v1_3A_12_zhCN.r4-base.w3x"

CLASS_NAMES: list[tuple[str, str]] = [
    ("Farmer Greavus", "农夫"),  # name; proper set separately
    ("Necromancer", "死灵法师"),
    ("Hexblade", "咒刃"),
    ("Valkyrie", "瓦尔基里"),
    ("Berserker", "狂战士"),
    ("Assassin", "刺客"),
    ("Magician", "魔术师"),
    ("Sorcerer", "巫师"),
    ("Crusader", "十字军"),
    ("Hunter", "猎人"),
    ("Bishop", "主教"),
    ("Cleric", "牧师"),
    ("Ranger", "游侠"),
    ("Mystic", "秘术师"),
    ("Psion", "灵能者"),
    ("Squire", "侍从"),
    ("Thief", "盗贼"),
    ("Druid", "德鲁伊"),
    ("Monk", "武僧"),
    ("Bard", "吟游诗人"),
    ("Farmer", "农夫"),
]

HELPER = r'''
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


def patch_jass(text: str) -> tuple[str, dict[str, int]]:
    counts = {"Recipe": 0, "Mount": 0, "helper": 0, "timers": 0}

    # Display category labels only; keep oiH=="Recipe" / GetObjectName prefix logic EN
    text, n = re.subn(r'OiH\("Recipe"', 'OiH("配方"', text)
    counts["Recipe"] = n
    text, n = re.subn(r'OiH\("Mount"', 'OiH("坐骑"', text)
    counts["Mount"] = n

    # Remove any prior ZhCN helpers (r2/r3 variants)
    text = re.sub(
        r"function ZhCN_Rename(?:Units|Items|Items_Enum|All) takes nothing returns nothing.*?endfunction\n",
        "",
        text,
        flags=re.S,
    )

    if "function main takes nothing returns nothing" not in text:
        raise RuntimeError("main() not found")
    text = text.replace(
        "function main takes nothing returns nothing",
        HELPER.lstrip() + "\nfunction main takes nothing returns nothing",
        1,
    )
    counts["helper"] = 1

    # Clean old timer injects; install one-shot + periodic on ZhCN_RenameAll
    for old in (
        "call TimerStart(CreateTimer(),1.,false,function ZhCN_RenameUnits)\n",
        "call TimerStart(CreateTimer(),0.5,false,function ZhCN_RenameUnits)\n",
        "call TimerStart(CreateTimer(),5.,true,function ZhCN_RenameUnits)\n",
        "call TimerStart(CreateTimer(),0.5,false,function ZhCN_RenameAll)\n",
        "call TimerStart(CreateTimer(),5.,true,function ZhCN_RenameAll)\n",
    ):
        text = text.replace(old, "")

    inject = (
        "call TimerStart(CreateTimer(),0.5,false,function ZhCN_RenameAll)\n"
        "call TimerStart(CreateTimer(),5.,true,function ZhCN_RenameAll)\n"
    )
    if "call ubK()\n" in text:
        text = text.replace("call ubK()\n", "call ubK()\n" + inject, 1)
        counts["timers"] = 2
    else:
        text = text.replace(
            "function main takes nothing returns nothing\n",
            "function main takes nothing returns nothing\n" + inject,
            1,
        )
        counts["timers"] = 2
    return text, counts


def main() -> None:
    if not OUT.exists():
        raise SystemExit(f"missing playable base map: {OUT}")

    BUILD.mkdir(parents=True, exist_ok=True)
    j_path = BUILD / "war3map.j.r5"
    # Extract j from current playable out (r4), never from r3 build Skin-era j
    run_tool(["extract", str(OUT), "war3map.j", str(j_path)])
    j_text = j_path.read_text(encoding="utf-8", errors="replace")
    # Sanity: must NOT already contain rewritten Skin-era-only markers? Just patch.
    j_new, counts = patch_jass(j_text)
    j_path.write_text(j_new, encoding="utf-8")
    print(f"JASS patch counts: {counts}")
    print(f"j size {len(j_text)} -> {len(j_new)}")

    # Backup r4 base once
    if not BACKUP.exists():
        shutil.copy2(OUT, BACKUP)
        print(f"backed up r4 base -> {BACKUP}")

    # ONLY replace war3map.j — no Skin.w3u/w3t/w3a, no Compact
    run_tool(["replace", str(OUT), "war3map.j", str(j_path)])
    print(f"OUT {OUT} size={OUT.stat().st_size}")


if __name__ == "__main__":
    main()
