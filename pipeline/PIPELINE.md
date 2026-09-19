# 魔兽争霸3 自定义图汉化流水线

面向**无源码成品图**（`.w3x`）的可复用方法。已在 Gaias ORPG、沉没之城（Sunken City）上跑通。

## 原则

1. **优先改 `war3map.wts`（字符串表）**：对象数据里若是 `TRIGSTR_xxx`，只换表内正文最稳。
2. **写回用 nocompact 替换**：`tools/w3x_replace_nocompact`，**禁止 CompactArchive**（易坏图）。
3. **WTS 编码**：尽量 **UTF-8 BOM + CRLF**（部分图 lobby 元数据依赖此格式）。
4. **不要手改 `.w3u/.w3a/.w3t` 二进制字符串长度**（Gaias r3 因此打不开）。
5. **对象硬编码英文**：用世界编辑器/正规序列化工具，或进图后 `BlzSetAbilityTooltip` 等运行时挂接；挂接避免高频循环定时器（会卡顿），改为进图后少量一次性调用，或挂在原图选职业逻辑末尾。
6. **脚本硬编码英文**：对 `war3map.j` 做**精确字面量替换**（UI 标题、Hint 等），勿整文件机翻。
7. **交付**：日常用临时网盘 / 本机 inbox；**未完全修好前不要发 GitHub Release**。
8. **密钥**：`PACKYAPI_API_KEY` 只放 `.env`，永不提交。

## 目录

```
pipeline/
  tools/           # w3x_replace / w3x_replace_nocompact
  scripts/         # 通用抽串、Packy 翻译、回写
  maps/gaias/      # Gaias 专用补丁脚本（r2–r10）
  maps/sunken/     # 沉没之城专用补丁脚本（r3–r4）
  docs/            # 方案笔记
  .env.example
  PIPELINE.md
```

## 通用步骤（新图）

```bash
# 0. 环境
cp pipeline/.env.example .env   # 填入 PACKYAPI_API_KEY
export PATH=... # 确保能跑 tools/w3x_replace_nocompact

# 1. 抽出 WTS
./pipeline/tools/w3x_replace_nocompact extract map.w3x war3map.wts /tmp/en.wts

# 2. 抽串 → 翻译缓存（OpenAI 兼容 PackyAPI）
python3 pipeline/scripts/extract_strings.py ...
python3 pipeline/scripts/packy_translate.py --resume ...

# 3. 回写 WTS（BOM+CRLF），从【原版英文图】替换，勿动 j/对象文件除非必要
python3 pipeline/scripts/apply_translations.py ...
./pipeline/tools/w3x_replace_nocompact replace out.w3x war3map.wts zh_bom.wts
# 若有 locales：
./pipeline/tools/w3x_replace_nocompact replace out.w3x '_Locales\zhCN.w3mod\war3map.wts' zh_bom.wts

# 4. 扫残留英文：WTS 拉丁占比高的条目 + JASS 字面量（Multiboard/Hint/BlzFrameSetText）
# 5. 试玩：能开图 → 再补技能正文 / UI；坏图则回退只改 WTS 的版本
```

## 已验证经验

| 问题 | 处理 |
|------|------|
| 列表无地图名/简介 | WTS STRING 名/描述 + BOM/CRLF |
| 技能标题中、正文英 | 补翻 WTS 长说明；或 JASS `BlzSetAbility*`（限频） |
| 改对象文件后打不开 | 回退；改用 WTS / 运行时挂接 |
| 进图一直卡 | 去掉周期性全图扫/重挂 tip |
| 快捷键字母 P/O/Q… | 属键位显示，不要汉化 |
| Reforged 看不见酒馆 | 部分图要求经典画质；商店可能先隐藏，选难度后显示 |

## Gaias / 沉没之城脚本

见 `pipeline/maps/gaias/scripts/`、`pipeline/maps/sunken/scripts/`。新图应抽通用步骤，地图特例单独放 `pipeline/maps/<name>/`。
