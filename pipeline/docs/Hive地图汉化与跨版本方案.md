# Hive 自制图：解包 → 翻译 → 打包（兼顾 1.27 / 重制版）

## 1. 地图本质

`.w3x` / `.w3m` = **带 512 字节地图头的 MPQ 压缩包**。  
解包改文本再打包时，**必须保留原地图头**，否则客户端可能无法识别。

---

## 2. 文本藏在哪（汉化要改什么）

| 优先级 | 文件 | 内容 | 难度 |
|--------|------|------|------|
| ★★★ | `war3map.wts` | WE 生成的可翻译串（TRIGSTR_xxx）：任务、对话、多数物编名/提示 | 文本，最好改 |
| ★★ | `war3map.j` 或 `war3map.lua` | 自定义脚本里写死的 `"字符串"` | 需扫引号，易漏 |
| ★ | `war3map.w3u/.w3t/.w3a/...` | 物编二进制；若未走 TRIGSTR，字符串在物编里 | 用工具转 LNI/JSON 再改 |
| ★ | `war3map.w3i` | 地图名、简介 | 少量 |
| ★ | `war3mapSkin.txt` 等 | 界面/提示覆盖 | 看图 |

**现实**：很多 Hive 图「界面物编」在 `.wts`，剧情/系统提示在 `.j`。完整汉化通常要 **wts + j/lua 两路**。

---

## 3. 推荐工具链

| 用途 | 工具 | 说明 |
|------|------|------|
| 解包/转 LNI/跨版本 | [w3x2lni](https://github.com/sumneko/w3x2lni) | 国内地图圈事实标准；物编→可读 LNI；支持多版本数据模型 |
| 纯 MPQ 读写 | MPQEditor（Zezula）、[JMPQ3](https://github.com/inwc3/jmpq3)、[umpqx](https://github.com/uakfdotb/umpqx) | 换文件、设 locale；umpqx 重建时要 `-header` 拷原头 |
| wts⇄JSON | [WC3MapTranslator](https://github.com/ChiefOfGxBxL/WC3MapTranslator) | 方便脚本/机翻管线 |
| 多语言 wts 同步 | [wc3trans](https://github.com/tdauth/wc3trans) | 主 wts 更新后合并到各语言副本 |
| 编辑器侧 | YDWE / 官方 WE / Reforged WE | 看目标版本；改完再用 w3x2lni 整理亦可 |

国内常见「改图一条龙 / 火龙 HWM」本质也是拆 MPQ；长期自动化更建议 **w3x2lni + 脚本**。

---

## 4. 标准流程（可自动化）

```
下载 .w3x
  ↓
检测是否加密/保护（无 listfile、文件名乱码）→ 有则先找未保护版或专门脱壳
  ↓
解包（w3x2lni 转目录/LNI，或 MPQ 导出）
  ↓
抽取字符串
  - 解析 war3map.wts → JSON/CSV
  - 正则扫 war3map.j / .lua 中双引号（排除原生 API 名）
  - （可选）物编 LNI 里的 name/tip/ubertip
  ↓
翻译（人工 / 机翻+校对）；保留 TRIGSTR_ID 不变
  ↓
写回 + 打包（保留 512B 头；压缩可选）
  ↓
目标客户端实测（1.27 / 重制 / 对战平台）
```

### 4.1 最简单：整图改成中文（适合自己玩）

1. 解包，翻译并**直接覆盖**根目录 `war3map.wts`（及 j 里硬编码）。  
2. 打包。  
3. 谁打开都是中文。兼容性最好，但不保留英文底稿。

### 4.2 更干净：多语言覆盖（推荐做「可分享汉化补丁」）

**A. 经典 LANGID（1.26/1.27 与重制都能认）** — Hive 教程推荐「双端兼容」做法：

- 默认 `war3map.wts` 保持英文（locale Neutral `0000`）  
- 另存中文 wts，在 MPQ 里设 locale = **zh-CN `0x0804`**  
- 中文客户端读中文；其它语言仍读默认  

**B. 重制 `_Locales`（仅 Reforged）**：

```
_Locales/zhCN.w3mod/war3map.wts
```

老客户端不认这套路径；若还要在 1.27 玩，优先用 **A**。

中文 locale 码：`0804`（简中）/ `0404`（繁中）。

---

## 5. 版本兼容（1.27 vs 重制）怎么处理

把两件事拆开：

### 5.1 「汉化」≠「改地图引擎版本」

多数情况：**不改物编版本**，只改字符串，原图在哪个客户端能开，汉化后也能开。  
这是默认策略。

### 5.2 真正要跨版本「能开」时

| 情况 | 做法 |
|------|------|
| 图标明 1.26/1.27 | 用 1.27 客户端或支持选版本的平台（如部分对战平台） |
| 图标明 1.32+ / Reforged | 用重制客户端 |
| 想把老图转成重制可开 | [w3x2lni](https://github.com/sumneko/w3x2lni) 做版本/数据转换（有风险：触发器 API、模型、平衡） |
| 想一份文件两边玩 | **很难 100%**；更稳是：保留原版逻辑 + 经典 LANGID 中文 wts，在「能开这张图的客户端」上玩 |

**实操建议**：

1. 维护一张表：`地图名 | 原要求版本 | 测试客户端 | 汉化方式(覆盖/LANGID/_Locales)`  
2. 工具链按「玩法客户端」分两套输出，而不是强行合成一个万能图：  
   - `maps/classic/` → 1.27 能开的汉化包  
   - `maps/reforged/` → 重制能开的汉化包（必要时 `_Locales`）  
3. 仅当「同一张图两边都要开且逻辑要动」时再上 w3x2lni 转换，并**分别回归测试**。

---

## 6. 坑与边界

1. **加密/保护图**：listfile 残缺、文件名哈希。普通拆包失败 → 找作者未保护版，或专用恢复工具；不要硬重建。  
2. **JASS 硬编码**：只改 wts 会出现「一半中文一半英文」。  
3. **TRIGSTR ID**：翻译时不要改编号；地图更新后 ID 会变，需用 wc3trans 之类做增量合并。  
4. **编码**：`.wts` 注意 UTF-8 vs 系统 ANSI；中文客户端乱码优先查编码。  
5. **Lua 图（重制）**：字符串在 `war3map.lua`，流程同 j，工具略不同。  
6. **机翻**：技能描述、专有名词需词表（英雄名、地图术语），否则观感很差。  
7. **版权/分享**：Hive 图二次分发要看作者授权；自用汉化一般没问题。

---

## 7. 建议落地的最小管线（给你自己用）

```
tools/
  w3x2lni/          # 解包、LNI、必要时转版本
  mpq/              # JMPQ3 或 MPQEditor 脚本
scripts/
  extract_wts.py    # wts → csv/json
  extract_j_strings.py
  apply_translation.py
  pack_map.py       # 写回 + 保留 header；可选设 0804 locale
glossary/
  terms.csv         # 统一译名
work/
  <mapname>/
    original.w3x
    unpacked/
    strings.en.json
    strings.zh.json
    out.w3x
```

**MVP 验收**（一张图跑通即可）：

1. 解包成功  
2. 只汉化 `war3map.wts`，进游戏地图名/任务已是中文  
3. 再扫一轮 `war3map.j` 硬编码  
4. 在声明版本的客户端能开、能存档（若图支持）

---

## 8. 一句话结论

- **解包/打包**：按 MPQ 处理，保留地图头；首选 w3x2lni + MPQ 工具。  
- **翻译**：主战场 `war3map.wts`，补完 `war3map.j`/`.lua`；物编走 LNI 更稳。  
- **兼容**：汉化默认「不改版本」；双端显示用 **经典 LANGID 中文 wts**；玩不了再按客户端出两份或 w3x2lni 转版本。  
- **不要指望**一张汉化包在任意 1.27/重制上 100% 可玩——可玩性由原图版本决定，汉化只解决文字。
