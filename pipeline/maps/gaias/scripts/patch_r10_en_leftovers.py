#!/usr/bin/env python3
"""Gaias zhCN r10: leftover English UI scan fixes (no tip-timer regress).

Hard rules:
- NEVER CompactArchive
- NEVER rewrite war3mapSkin.w3u/w3t/w3a binary
- ONLY patch via tools/w3x_replace_nocompact (j / wts / Skin.txt)
- Keep r9 one-shot ZhCN_RenameAll timers; do NOT reintroduce periodic tips
- Keep map name with 【汉化】
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/workspace/wc3-map-l10n")
SRC_R9 = ROOT / "gaias/out/GaiasORPG_v1_3A_12_zhCN-r9.w3x"
OUT = ROOT / "gaias/out/GaiasORPG_v1_3A_12_zhCN.w3x"
SNAP = ROOT / "gaias/out/GaiasORPG_v1_3A_12_zhCN-r10.w3x"
BUILD = ROOT / "gaias/build"
TOOL = ROOT / "tools/w3x_replace_nocompact"

J_OUT = BUILD / "war3map.j.r10"
WTS_OUT = BUILD / "war3map.wts.r10"
SKIN_OUT = BUILD / "war3mapSkin.txt.r10"

# Green Note extended tip (A08R / AZ8R) — song letters G/R/B kept (hotkeys)
GREEN_NOTE_UBERTIP = (
    "演奏|cff00ff00绿色|r音符，连续演奏3个音符会对范围内所有盟友施加一个范围增益：|n|n"
    "|cffc0c0c0真名颂歌|r|n|cff00ff00G|r|cffff0000RR|r - 最高属性提高 |cffffcc00敏捷 x 0.08|r|n|cffccccff冷却：3秒|r|n|n"
    "|cffc0c0c0碎音安魂曲|r|n|cff00ff00G|r|cffff0000R|r|cff00ff00G|r - 对区域内敌人造成 |cffffcc00敏捷 x 4|r 点伤害|n|cffccccff冷却：4秒|r|n|n"
    "|cffc0c0c0裂钢挽歌|r|n|cff00ff00GG|r|cff8080ffB|r - 护甲穿透提高 |cffffcc00敏捷 x 0.1|r|n|cffccccff冷却：3秒|r|n|n"
    "|cffc0c0c0鹰兔小步舞曲|r|n|cff00ff00G|r|cff8080ffB|r|cff00ff00G|r - 闪避与命中提高 |cffffcc00敏捷 x 0.1|r|n|cffccccff冷却：3秒|r|n|n"
    "|cffc0c0c0破障连祷|r|n|cff00ff00G|r|cffff0000R|r|cff8080ffB|r - 驱散区域内盟友的所有负面效果|n|cffccccff冷却：4秒|n|n冷却：无|r"
)

# Exact JASS string literal swaps (must match escaped form in file)
JASS_SWAPS: list[tuple[str, str]] = [
    # Dialogs / portal Cancel
    ('"Cancel"', '"取消"'),
    ('"Repick"', '"重新选择"'),
    # Teleport menu visible labels (7th arg); ids stay English for code
    ('hgX(JO,"Riversdale",.355,.40,.445,.38,"Riversdale"',
     'hgX(JO,"Riversdale",.355,.40,.445,.38,"河畔镇"'),
    ('hgX(JO,"Mytargas",.355,.37,.445,.35,"Mytargas"',
     'hgX(JO,"Mytargas",.355,.37,.445,.35,"米塔加斯"'),
    ('hgX(JO,"DunHaldran",.355,.31,.445,.29,"Dun Haldran"',
     'hgX(JO,"DunHaldran",.355,.31,.445,.29,"邓哈尔德兰"'),
    # Entering zone messages
    ('"|cffccccff正在进入：Riversdale|r"',
     '"|cffccccff正在进入：河畔镇|r"'),
    ('"|cffccccff正在进入：Mytargas - 贸易区|r"',
     '"|cffccccff正在进入：米塔加斯 - 贸易区|r"'),
    ('"|cffccccff正在进入：Dun Haldran|r"',
     '"|cffccccff正在进入：邓哈尔德兰|r"'),
    # Button tooltips
    (',"UITextures\\\\SlotIcon.tga","Pet",false,On,MWG)',
     ',"UITextures\\\\SlotIcon.tga","宠物",false,On,MWG)'),
    (',"UITextures\\\\SlotIcon.tga","Pet",false,On,vJG)',
     ',"UITextures\\\\SlotIcon.tga","宠物",false,On,vJG)'),
    ('rHf("Resources",.722000,.1132000,.742,.0932000,"","UITextures\\\\buttonResources.tga","Resources",true,On,qoG)',
     'rHf("Resources",.722000,.1132000,.742,.0932000,"","UITextures\\\\buttonResources.tga","资源",true,On,qoG)'),
    # Neutral vault player names
    ('SetPlayerName(Player(6),"Vault")', 'SetPlayerName(Player(6),"宝库")'),
    ('SetPlayerName(Player(7),"Vault")', 'SetPlayerName(Player(7),"宝库")'),
    ('SetPlayerName(Player(8),"Vault")', 'SetPlayerName(Player(8),"宝库")'),
    ('SetPlayerName(Player(9),"Vault")', 'SetPlayerName(Player(9),"宝库")'),
    ('SetPlayerName(Player(10),"Vault")', 'SetPlayerName(Player(10),"宝库")'),
    ('SetPlayerName(Player(11),"Vault")', 'SetPlayerName(Player(11),"宝库")'),
]

EN_HINT = (
    '"\\n|cff5555ffHint:|r\\nItems can also be carried in your |cffffff00backpack|r for later use. '
    "To pick up an item with your backpack, simply select the backpack on your quickbar "
    "(|cffffff00Hotkey: F2|r) and right-click the item. Your Material bag (|cffffff00Hotkey: F3|r) "
    'will allow you to collect crafting resources."'
)
ZH_HINT = (
    '"\\n|cff5555ff提示：|r\\n物品也可以放进|cffffff00背包|r备用。'
    "要用背包拾取物品，在快捷栏选中背包（|cffffff00快捷键：F2|r）再右键点击物品。"
    '材料袋（|cffffff00快捷键：F3|r）可收集制造材料。"'
)

WTS_REPLACEMENTS: dict[int, str] = {
    5023: (
        "狂战士向所选对手宣布一场持续10秒的生死决斗。|n此技能效果期间，狂战士产生 |cffffcc0035%|r 额外威胁值，"
        "且狂战士与其对手互相造成的伤害提高 |cffffcc0015%|r，对其他人造成的伤害降低 |cffffcc0015%|r。\n"
        "|n|cff99ccff如果该技能在3层怒气时使用，对狂战士的伤害加成将改为伤害减免，并消耗所有怒气层数。"
        "|n|n当Mak'gora的参与者死亡时，其对手将恢复最大生命值的15%。|r|n|cffccccff冷却时间：25秒|r"
    ),
    8439: (
        "|cff909090当一个单位被杀死时，有35%几率在掉落表上额外掷一次。"
        "|n成功演奏歌曲后有[歌曲基础冷却 x 12]/[可用音符技能数量]%的几率将你的一个音符技能变为“小丑音符”。"
        "演奏该音符会重置所有音符的歌曲冷却，并获得4层“战斗节奏”。|r"
        "|n当“决斗者姿态”激活时，每次闪避攻击都会触发一次立即反击，造成普通攻击伤害。"
        "反击伤害无法被闪避。技能动画期间无法触发反击。"
    ),
    12532: (
        "|cff909090你的“自然仆从”现在是一头狼。|n你的“天空仆从”现在是一只猎鹰。"
        "|n仆从的攻击速度（自然仆从）和法术急速（火精灵、宁芙和火花）提高 15%。"
        "|n你的“自然仆从”现在是一只熊。|n你的“天空仆从”现在是一只渡鸦。"
        "|n所有仆从造成伤害和进行治疗时的暴击几率提高 15%。|r"
        "|n你的“自然仆从”现在是一棵树人。|n你的“天空仆从”现在是一只乌鸦。"
        "|n仆从的攻击强度（自然仆从）和法术强度（火精灵、宁芙和火花）提高 15%。"
    ),
    13046: (
        "|cff909090你已赢得了动物首领们的尊重。"
        "|n你的宠物现在获得狼、熊和树人的所有加成。此外，“爪击”现在会根据宠物类型获得额外效果。"
        "|n熊：使用时治疗最大生命值的15%。"
        "|n狼：施加流血效果，在15秒内造成[攻击强度 * 0.5]点物理伤害。"
        "|n树人：使目标致盲，命中几率降低10%，持续5秒。"
        "|n暴击会使目标中毒，降低10%的法术急速、移动速度和攻击速度，持续6秒。|r"
        "|n每点敏捷还会增加0.5点护甲穿透。攻击速度降低15%，但你的护甲穿透会加到普通攻击伤害上。"
    ),
    13176: GREEN_NOTE_UBERTIP,
    13607: GREEN_NOTE_UBERTIP,
}


def run_tool(args: list[str]) -> None:
    cmd = [str(TOOL), *args]
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def escape_jass(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def patch_jass(text: str) -> tuple[str, dict]:
    counts: dict[str, int] = {}
    for old, new in JASS_SWAPS:
        n = text.count(old)
        if n == 0:
            print(f"WARN missing swap: {old[:60]!r}")
        else:
            text = text.replace(old, new)
        counts[old[:40]] = n

    if EN_HINT not in text:
        # try without worrying about exact - search flexible
        m = re.search(
            r'"\\n\|cff5555ffHint:\|r\\nItems can also be carried in your \|cffffff00backpack\|r[^"]*"',
            text,
        )
        if not m:
            raise SystemExit("EN backpack Hint tip not found")
        text = text[: m.start()] + ZH_HINT + text[m.end() :]
        counts["EN_HINT"] = 1
    else:
        text = text.replace(EN_HINT, ZH_HINT)
        counts["EN_HINT"] = 1

    # Inject Green Note tip fix into ZhCN_AbilityTips (append before endfunction of first tips fn)
    green_calls = "\n".join(
        [
            f'call BlzSetAbilityExtendedTooltip($41303852,"{escape_jass(GREEN_NOTE_UBERTIP)}",0)',
            f'call BlzSetAbilityExtendedTooltip($41303852,"{escape_jass(GREEN_NOTE_UBERTIP)}",1)',
            f'call BlzSetAbilityResearchExtendedTooltip($415A3852,"{escape_jass(GREEN_NOTE_UBERTIP)}",0)',
            f'call BlzSetAbilityResearchExtendedTooltip($415A3852,"{escape_jass(GREEN_NOTE_UBERTIP)}",1)',
        ]
    )
    # Insert at start of ZhCN_AbilityTips so later chunks don't matter; actually END so we win last-write
    marker = "function ZhCN_AbilityTips takes nothing returns nothing\n"
    if marker not in text:
        raise SystemExit("ZhCN_AbilityTips not found")
    # Find end of ZhCN_AbilityTips: first endfunction after marker that is followed by function ZhCN_
    start = text.find(marker)
    # Prefer inserting just before the final endfunction of the last ZhCN_AbilityTips_chunk
    # Simpler: add ZhCN_FixGreenNote and call it from ZhCN_RenameAll
    helper = (
        "\nfunction ZhCN_FixGreenNote takes nothing returns nothing\n"
        + green_calls
        + "\nendfunction\n"
    )
    if "function ZhCN_FixGreenNote" in text:
        print("FixGreenNote already present")
    else:
        # place before ZhCN_RenameUnits or after last AbilityTips chunk
        anchor = "function ZhCN_RenameUnits takes nothing returns nothing"
        if anchor not in text:
            raise SystemExit("ZhCN_RenameUnits missing")
        text = text.replace(anchor, helper + anchor, 1)
        counts["inject_FixGreenNote"] = 1

    # Call from ZhCN_RenameAll alongside AbilityTips
    if "call ZhCN_FixGreenNote()" not in text:
        if "call ZhCN_AbilityTips()" not in text:
            raise SystemExit("call ZhCN_AbilityTips missing in RenameAll")
        text = text.replace(
            "call ZhCN_AbilityTips()",
            "call ZhCN_AbilityTips()\ncall ZhCN_FixGreenNote()",
            1,
        )
        counts["call_FixGreenNote"] = 1

    # Globes leftover inside Chinese tips (JASS Blz strings)
    globes_n = text.count("（取代“Globes”）")
    if globes_n:
        text = text.replace("（取代“Globes”）", "（取代“宝珠”）")
        counts["Globes"] = globes_n

    return text, counts


def patch_wts(text: str) -> tuple[str, int]:
    replaced = 0
    # Also Globes in WTS
    if "（取代“Globes”）" in text:
        text = text.replace("（取代“Globes”）", "（取代“宝珠”）")
        replaced += text.count("宝珠")  # rough

    for sid, body in WTS_REPLACEMENTS.items():
        pat = re.compile(rf"(?m)^(STRING\s+{sid}\s*\{{)\s*.*?(\s*\}})", re.S)
        m = pat.search(text)
        if not m:
            print(f"WARN WTS STRING {sid} not found")
            continue
        text = pat.sub(rf"\1\n{body}\n\2", text, count=1)
        replaced += 1
    return text, replaced


def patch_skin(text: str) -> tuple[str, int]:
    n = 0
    old = "COLON_FOOD_TOTAL=Magic attacks deal normal damage to any unit.9"
    new = "COLON_FOOD_TOTAL=地城点数上限："
    if old in text:
        text = text.replace(old, new)
        n += 1
    else:
        # already fixed or different
        m = re.search(r"(?m)^COLON_FOOD_TOTAL=(.*)$", text)
        print(f"COLON_FOOD_TOTAL current: {m.group(1) if m else 'MISSING'}")
        if m and not re.search(r"[\u4e00-\u9fff]", m.group(1)):
            text = re.sub(
                r"(?m)^COLON_FOOD_TOTAL=.*$",
                new,
                text,
            )
            n += 1
    return text, n


def main() -> None:
    if not SRC_R9.exists():
        raise SystemExit(f"missing {SRC_R9}")
    BUILD.mkdir(parents=True, exist_ok=True)

    shutil.copy2(SRC_R9, OUT)
    print(f"base copy r9 -> OUT ({OUT.stat().st_size})")

    run_tool(["extract", str(OUT), "war3map.j", str(J_OUT)])
    run_tool(["extract", str(OUT), "war3map.wts", str(WTS_OUT)])
    run_tool(["extract", str(OUT), "war3mapSkin.txt", str(SKIN_OUT)])

    j = J_OUT.read_text(encoding="utf-8", errors="replace")
    j2, jcounts = patch_jass(j)
    # Preserve one-shot timers
    for t in ("0.5,false,function ZhCN_RenameAll", "2.,false,function ZhCN_RenameAll",
              "8.,false,function ZhCN_RenameAll", "20.,false,function ZhCN_RenameAll"):
        if t not in j2:
            raise SystemExit(f"missing timer {t}")
    if re.search(r"TimerStart\([^)]*,\s*true\s*,\s*function ZhCN_", j2):
        raise SystemExit("periodic ZhCN timer reintroduced")
    if "BlzSetUnitProperName" in j2[j2.find("function ZhCN_") : j2.find("function main takes")]:
        raise SystemExit("forbidden BlzSetUnitProperName")
    J_OUT.write_text(j2, encoding="utf-8")
    print("JASS swaps:", jcounts)

    wts = WTS_OUT.read_text(encoding="utf-8", errors="replace")
    wts2, wn = patch_wts(wts)
    # keep 【汉化】 in STRING 1
    if "【汉化】" not in wts2:
        raise SystemExit("map name lost 【汉化】")
    WTS_OUT.write_text(wts2, encoding="utf-8")
    print(f"WTS replaced blocks={wn}")

    skin = SKIN_OUT.read_text(encoding="utf-8", errors="replace")
    skin2, sn = patch_skin(skin)
    SKIN_OUT.write_text(skin2, encoding="utf-8")
    print(f"Skin fixes={sn}")

    run_tool(["replace", str(OUT), "war3map.j", str(J_OUT)])
    run_tool(["replace", str(OUT), "war3map.wts", str(WTS_OUT)])
    run_tool(["replace", str(OUT), "war3mapSkin.txt", str(SKIN_OUT)])

    # verify extract
    ver_j = BUILD / "war3map.j.r10.verify"
    ver_w = BUILD / "war3map.wts.r10.verify"
    ver_s = BUILD / "war3mapSkin.txt.r10.verify"
    run_tool(["extract", str(OUT), "war3map.j", str(ver_j)])
    run_tool(["extract", str(OUT), "war3map.wts", str(ver_w)])
    run_tool(["extract", str(OUT), "war3mapSkin.txt", str(ver_s)])
    vj = ver_j.read_text(encoding="utf-8", errors="replace")
    vw = ver_w.read_text(encoding="utf-8", errors="replace")
    vs = ver_s.read_text(encoding="utf-8", errors="replace")

    assert '"取消"' in vj and vj.count('"Cancel"') == 0
    assert '"重新选择"' in vj and '"Repick"' not in vj
    assert "河畔镇" in vj and "邓哈尔德兰" in vj
    assert "function ZhCN_FixGreenNote" in vj
    assert "call ZhCN_FixGreenNote()" in vj
    assert "真名颂歌" in vj
    assert "5.,true,function ZhCN_RenameAll" not in vj
    assert "【汉化】" in vw
    assert "地城点数上限" in vs
    assert "Magic attacks deal normal damage" not in vs

    shutil.copy2(OUT, SNAP)
    meta = {
        "release": "r10",
        "base": "r9",
        "j_swaps": jcounts,
        "wts_blocks": wn,
        "skin_fixes": sn,
        "out_size": OUT.stat().st_size,
        "snap": str(SNAP),
        "no_repeating_zhcn_timers": True,
        "map_name_has_hanhua": True,
        "p_o_hotkeys_unchanged": True,
    }
    (BUILD / "r10_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"OK r10 -> {SNAP} size={SNAP.stat().st_size}")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
