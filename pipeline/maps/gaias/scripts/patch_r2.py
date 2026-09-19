#!/usr/bin/env python3
"""Patch remaining EN UI for Gaias zhCN r2: skin, jass glossary, w3i/WTS name, Farmer rename."""
from __future__ import annotations

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

# Exact JASS string-literal replacements (unescaped content).
# Order: longer keys first to avoid partial issues (we match full literals only).
GLOSSARY: list[tuple[str, str]] = [
    # Threat / IgH
    ("Personal", "个人"),
    ("Team", "队伍"),
    ("Stats / Souls", "属性 / 灵魂"),
    # Item category prefixes (full literal assignments)
    ("Weapon", "武器"),
    ("Misc", "杂项"),
    ("Helmet", "头盔"),
    ("Accessory", "饰品"),
    # NOTE: bare "Armor" used both as i5X label AND SubString(VxH,0,5)=="Armor" model check.
    # Handle Armor specially below — only replace set i5X="Armor" / OiH contexts, not SubString.
    # O3 armor/weapon/misc types
    ("Two-handed", "双手"),
    ("Two-hander", "双手武器"),
    ("Offhand Weapon", "副手武器"),  # already zh in build but safe
    ("Psionic Blade", "灵能之刃"),
    ("Instrument", "乐器"),
    ("Gauntlets", "护手"),
    ("Gloves", "手套"),
    ("Hauberk", "锁子甲"),
    ("Leather", "皮甲"),
    ("Quiver", "箭袋"),
    ("Shield", "盾牌"),
    ("Amulet", "护符"),
    ("Trophy", "战利品"),
    ("Relic", "圣物"),
    ("Totem", "图腾"),
    ("Skull", "颅骨"),
    ("Chain", "链甲"),
    ("Cloth", "布甲"),
    ("Staff", "法杖"),
    ("Dagger", "匕首"),
    ("Hammer", "锤子"),
    ("Lance", "长枪"),
    ("Sword", "剑"),
    ("Mail", "锁甲"),
    ("Rune", "符文"),
    ("Book", "书册"),
    ("Ring", "戒指"),
    ("Vest", "皮衣"),
    ("Robe", "法袍"),
    ("Cap", "软帽"),
    ("Hat", "帽子"),
    ("Bow", "弓"),
    ("Gem", "宝石"),
    ("Axe", "斧"),
    # Class IDs (must update set UfG= and == comparisons together)
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
    # q1X plurals / "and"
    ("Crusaders", "十字军"),
    ("Berserkers", "狂战士"),
    ("Bishops", "主教"),
    ("Monks", "武僧"),
    ("Sorcerers", "巫师"),
    ("Necromancers", "死灵法师"),
    ("Hunters", "猎人"),
    ("Druids", "德鲁伊"),
    ("Assassins", "刺客"),
    ("Bards", "吟游诗人"),
    ("Hexblades", "咒刃"),
    ("Psions", "灵能者"),
    ("Valkyries", "瓦尔基里"),
    (" and ", " 和 "),
]

# Skin FrameDef translations (key=value lines under [FrameDef] / [Errors])
SKIN_KV: dict[str, str] = {
    "AGILITY": "敏捷",
    "AGILITY_HILIGHT": "|Cffffff00敏捷|R",
    "ARMOR_LARGE": "类型：|Cffffcc00锁甲|R",
    "ARMOR_MEDIUM": "类型：|Cffffcc00皮甲|R",
    "ARMOR_NONE": "类型：|Cffffcc00布甲|R",
    "ARMORTIP_LARGE": "锁甲受到任何攻击时均为正常伤害。",
    "ARMORTIP_LARGE_V0C": "锁甲受到任何攻击时均为正常伤害。",
    "ARMORTIP_LARGE_V0M": "锁甲受到任何攻击时均为正常伤害。",
    "ARMORTIP_MEDIUM": "皮甲受到所有攻击类型时均为正常伤害。",
    "ARMORTIP_MEDIUM_V0M": "皮甲受到所有攻击类型时均为正常伤害。",
    "ARMORTIP_NONE": "布甲受到任何攻击时均为正常伤害。",
    "ARMORTIP_SMALL": "布甲受到所有攻击类型时均为正常伤害。",
    "ARMORTIP_SMALL_V0C": "布甲受到所有攻击类型时均为正常伤害。",
    "ARMORTIP_SMALL_V0M": "布甲受到所有攻击类型时均为正常伤害。",
    "BONUS_ATTACK_SPEED": "- 攻击速度加成：|cffffcc00(敏捷/[基础敏捷] - 1) x 25%|r|n - 法术急速：|cffffcc00(敏捷/[基础敏捷] - 1) x 25%|r",
    "BONUS_DAMAGE": "- 每点使造成的伤害提高|cffffcc001|r",
    "BONUS_DEFENSE": "- 攻击/法术暴击几率：|cffffcc005 + (敏捷/[基础敏捷] - 1) x 5%|r|n - 闪避几率：|cffffcc005 + (敏捷/[基础敏捷] - 1) x 3%|r",
    "BONUS_DEFENSE_FIXED": "- 攻击/法术暴击几率：|cffffcc005 + (敏捷/[基础敏捷] - 1) x 5%|r|n - 闪避几率：|cffffcc005 + (敏捷/[基础敏捷] - 1) x 3%|r",
    "BONUS_HITPOINTS": "- 近战/远程暴击伤害倍率：|cffffcc001.5 + (力量/[基础力量] - 1) x 0.1|r",
    "BONUS_HPREGEN": "- 每点提高护甲穿透：|cffffcc000.5 x 力量|r",
    "BONUS_MANA": "- 法术暴击伤害倍率：|cffffcc001.5 + (智力/[基础智力] - 1) x 0.1|r",
    "BONUS_MANAREGEN": "- 每点使法术强度提高|cffffcc001|r",
    "COLON_AGILITY": "敏捷：",
    "COLON_ARMOR": "护甲：",
    "COLON_DAMAGE": "攻击强度：",
    "COLON_DAMAGE_REDUCTION": "护甲值按护甲点数减免伤害。百分比减免：",
    "COLON_FOOD": "地城点数：",
    "COLON_GOLD": "金币：",
    "COLON_GOLD_INCOME_RATE": "金币收入：",
    "COLON_HERO_ATTRIBUTES": "英雄属性：",
    "COLON_INTELLECT": "智力：",
    "COLON_LUMBER": "魔法水晶：",
    "COLON_PRIMARY_ATTRIBUTE": "主属性：",
    "COLON_STRENGTH": "力量：",
    "DAMAGE_MAGIC": "类型：|Cffffcc00魔法|R",
    "DAMAGE_MELEE": "类型：|Cffffcc00普通|R",
    "DAMAGE_PIERCE": "类型：|Cffffcc00穿刺|R",
    "DAMAGETIP_MAGIC": "魔法攻击对任何单位造成正常伤害。",
    "DAMAGETIP_MAGIC_V0C": "魔法攻击对任何单位造成正常伤害。",
    "DAMAGETIP_MAGIC_V0M": "魔法攻击对任何单位造成正常伤害。",
    "DAMAGETIP_MELEE": "普通攻击对所有护甲类型造成正常伤害。",
    "DAMAGETIP_MELEE_V0C": "普通攻击对所有护甲类型造成正常伤害。",
    "DAMAGETIP_MELEE_V0M": "普通攻击对所有护甲类型造成正常伤害。",
    "DAMAGETIP_NORMAL": "普通攻击对所有护甲类型造成正常伤害。",
    "DAMAGETIP_NORMAL_V0C": "普通攻击对所有护甲类型造成正常伤害。",
    "DAMAGETIP_NORMAL_V0M": "普通攻击对所有护甲类型造成正常伤害。",
    "DAMAGETIP_PIERCE": "穿刺攻击对所有单位造成正常伤害，对强化护甲伤害降低。",
    "DAMAGETIP_PIERCE_V0C": "穿刺攻击对所有单位造成正常伤害，对强化护甲伤害降低。",
    "DAMAGETIP_PIERCE_V0M": "穿刺攻击对所有单位造成正常伤害，对强化护甲伤害降低。",
    "DAMAGETIP_UNKNOWN": "魔法攻击对任何单位造成正常伤害。",
    "GOLD": "金币",
    "IDLE_PEON": "点击选择你的墓碑。",
    "IDLE_PEON_DESC": "自动接敌已禁用。",
    "INTELLECT": "智力",
    "INTELLECT_HILIGHT": "|Cffffff00智力|R",
    "INTELLIGENCE": "智力",
    "LUMBER": "魔法水晶",
    "PRIMARY_ATTRIBUTE": "|cffffff00主属性|r",
    "RESOURCE_UBERTIP_GOLD": "金币可通过任务和怪物获得。",
    "RESOURCE_UBERTIP_LUMBER": "魔法水晶可通过首领和任务获得。",
    "RESOURCE_UBERTIP_SUPPLY": "当前黑火深渊地城点数。深入黑火深渊或完成特殊楼层事件可获得更多地城点数。",
    "RESOURCES_COLUMN0": "金币",
    "RESOURCES_COLUMN1": "魔法水晶",
    "STRENGTH": "力量",
    "STRENGTH_HILIGHT": "|Cffffff00力量|R",
    # Errors
    "Nofood": "地城点数不足。",
    "Nogold": "金币不足。",
    "Nolumber": "魔法水晶不足。",
    "Notpowerup": "背包无法存放此类型物品。",
    "Notsapper": "无法以此法术选中首领。",
    "Targetstructure": "只能选中墓碑。",
}


JASS_STR = re.compile(r'"((?:\\.|[^"\\])*)"')


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


def patch_jass(text: str) -> tuple[str, dict[str, int]]:
    gloss = dict(GLOSSARY)
    # Sort by key length desc for matching
    keys = sorted(gloss.keys(), key=len, reverse=True)
    counts: dict[str, int] = {k: 0 for k in gloss}
    parts: list[str] = []
    last = 0
    armor_label_hits = 0
    for m in JASS_STR.finditer(text):
        parts.append(text[last : m.start()])
        raw_esc = m.group(1)
        raw = unescape_jass(raw_esc)
        # Special: only replace bare "Armor" when NOT part of SubString(...,"Armor") model-path check.
        # Look at preceding ~40 chars for SubString(
        prev = text[max(0, m.start() - 48) : m.start()]
        if raw == "Armor":
            if "SubString(" in prev:
                parts.append(m.group(0))
            else:
                parts.append('"护甲"')
                armor_label_hits += 1
            last = m.end()
            continue
        if raw in gloss:
            counts[raw] += 1
            parts.append('"' + escape_jass(gloss[raw]) + '"')
        else:
            parts.append(m.group(0))
        last = m.end()
    parts.append(text[last:])
    out = "".join(parts)
    counts["Armor(label)"] = armor_label_hits

    # Inject Farmer rename helper + call from main
    helper = r'''
function ZhCN_RenameUnits takes nothing returns nothing
local group zg=CreateGroup()
local unit zu
call GroupEnumUnitsInRect(zg,bj_mapInitialPlayableArea,null)
loop
set zu=FirstOfGroup(zg)
exitwhen zu==null
if GetUnitName(zu)=="Farmer" then
call BlzSetUnitName(zu,"农夫")
endif
call GroupRemoveUnit(zg,zu)
endloop
call DestroyGroup(zg)
set zg=null
set zu=null
endfunction
'''
    if "function ZhCN_RenameUnits" not in out:
        # Insert before function main
        out = out.replace(
            "function main takes nothing returns nothing",
            helper + "\nfunction main takes nothing returns nothing",
            1,
        )
        # Start a one-shot timer early in main after ubK()
        out = out.replace(
            "function main takes nothing returns nothing\nlocal string DLv",
            "function main takes nothing returns nothing\nlocal string DLv",
            1,
        )
        if "call TimerStart(CreateTimer(),1.,false,function ZhCN_RenameUnits)" not in out:
            out = out.replace(
                "call ubK()\n",
                "call ubK()\ncall TimerStart(CreateTimer(),1.,false,function ZhCN_RenameUnits)\n",
                1,
            )
            counts["Farmer_hook"] = 1
    return out, counts


def patch_skin(text: str) -> tuple[str, int]:
    hit = 0
    lines = []
    for line in text.splitlines(keepends=True):
        raw = line.rstrip("\r\n")
        endl = line[len(raw) :]
        if "=" in raw and not raw.startswith("[") and not raw.startswith("//"):
            k, _, v = raw.partition("=")
            if k in SKIN_KV and v != SKIN_KV[k]:
                lines.append(f"{k}={SKIN_KV[k]}{endl}")
                hit += 1
                continue
        lines.append(line)
    out = "".join(lines)
    # Ensure INVULNERABLE override exists in FrameDef
    if "INVULNERABLE=" not in out:
        out = out.replace(
            "[FrameDef]\n",
            "[FrameDef]\nINVULNERABLE=无敌\n",
            1,
        )
        hit += 1
    return out, hit


def patch_wts(text: str) -> tuple[str, int]:
    hit = 0
    new_name = "Gaias Retaliation ORPG v1.3A (12) 【汉化】"
    text2, n = re.subn(
        r"(STRING 1\s*\{\n)Gaias Retaliation ORPG v1\.3A \(12\)(\n\})",
        rf"\g<1>{new_name}\2",
        text,
        count=1,
    )
    hit += n
    def repl_1278(m):
        nonlocal hit
        body = m.group(2)
        if "【中文汉化版】" in body[:40]:
            return m.group(0)
        hit += 1
        # Insert after opening brace / leading newlines
        return m.group(1) + "\n【中文汉化版】" + body.lstrip("\n") + m.group(3)
    text2, _ = re.subn(
        r"(STRING 1278\s*\{)(.*?)(\})",
        repl_1278,
        text2,
        count=1,
        flags=re.S,
    )
    return text2, hit


def rewrite_w3i(src: Path, dst: Path) -> None:
    raw = bytearray(src.read_bytes())
    # Replace null-terminated strings starting at offset 28: name, author, description
    off = 28
    strings = []
    for _ in range(3):
        end = raw.find(b"\x00", off)
        strings.append(bytes(raw[off:end]))
        off = end + 1
    rest = bytes(raw[off:])
    header = bytes(raw[:28])

    new_name = "Gaias Retaliation ORPG v1.3A (12) 【汉化】".encode("utf-8")
    author = strings[1]
    old_desc = strings[2].decode("utf-8", "replace")
    if not old_desc.startswith("【中文汉化版】"):
        new_desc = (
            "【中文汉化版】请使用经典模式（Classic）。加载时尽量勿 Alt+Tab。\r\n\r\n"
            + old_desc
        )
    else:
        new_desc = old_desc
    new_desc_b = new_desc.encode("utf-8")

    out = bytearray()
    out += header
    out += new_name + b"\x00"
    out += author + b"\x00"
    out += new_desc_b + b"\x00"
    out += rest
    dst.write_bytes(out)
    print(f"w3i: name={new_name.decode()} desc_len {len(strings[2])}->{len(new_desc_b)} size {len(raw)}->{len(out)}")


def run_tool(args: list[str]) -> None:
    cmd = [str(TOOL)] + args
    print("RUN:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"tool failed rc={r.returncode}")


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)

    # Start from current build jass (already mostly translated)
    j_path = BUILD / "war3map.j"
    if not j_path.exists():
        j_path.write_text((EXTRACT / "war3map.j").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    j_text = j_path.read_text(encoding="utf-8", errors="replace")
    j_new, j_counts = patch_jass(j_text)
    j_path.write_text(j_new, encoding="utf-8")
    fixed = sum(1 for k, v in j_counts.items() if v and k != "Farmer_hook")
    total_repl = sum(v for k, v in j_counts.items() if k != "Farmer_hook")
    print(f"JASS: replacements={total_repl} distinct_keys_hit={sum(1 for v in j_counts.values() if v)}")
    top = sorted(((k, v) for k, v in j_counts.items() if v), key=lambda x: -x[1])[:25]
    print(" top:", top)

    # WTS
    wts_path = BUILD / "war3map.wts"
    wts_text = wts_path.read_text(encoding="utf-8", errors="replace")
    wts_new, wts_hits = patch_wts(wts_text)
    wts_path.write_text(wts_new, encoding="utf-8")
    print(f"WTS: name/desc patches={wts_hits}")

    # Skin
    skin_src = EXTRACT / "war3mapSkin.txt"
    skin_dst = BUILD / "war3mapSkin.txt"
    skin_text = skin_src.read_text(encoding="utf-8", errors="replace")
    skin_new, skin_hits = patch_skin(skin_text)
    skin_dst.write_text(skin_new, encoding="utf-8")
    print(f"SKIN: translated_keys={skin_hits}")

    # w3i
    w3i_dst = BUILD / "war3map.w3i"
    rewrite_w3i(EXTRACT / "war3map.w3i", w3i_dst)

    # Rebuild map from EN source
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_MAP, OUT)
    raw = bytearray(OUT.read_bytes())
    if raw[:4] == b"MPQ\x1a":
        old_hs = struct.unpack_from("<I", raw, 4)[0]
        if old_hs != 32:
            struct.pack_into("<I", raw, 4, 32)
            OUT.write_bytes(raw)
            print(f"fixed MPQ headerSize {old_hs} -> 32")

    locale_wts = r"_Locales\zhCN.w3mod\war3map.wts"
    try:
        run_tool(["replace", str(OUT), locale_wts, str(wts_path)])
    except SystemExit as e:
        print(f"WARN locale wts: {e}")
    run_tool(["replace", str(OUT), "war3map.wts", str(wts_path)])
    run_tool(["replace", str(OUT), "war3map.j", str(j_path)])
    run_tool(["replace", str(OUT), "war3map.w3i", str(w3i_dst)])
    run_tool(["replace", str(OUT), "war3mapSkin.txt", str(skin_dst)])
    # Also try locale skin
    try:
        run_tool(["replace", str(OUT), r"_Locales\zhCN.w3mod\war3mapSkin.txt", str(skin_dst)])
    except SystemExit as e:
        print(f"WARN locale skin (ok if unsupported): {e}")

    print(f"OUT {OUT} size={OUT.stat().st_size}")


if __name__ == "__main__":
    main()
