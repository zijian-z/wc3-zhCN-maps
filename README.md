# wc3-zhCN-maps

魔兽争霸3 自定义地图中文汉化：**成品发布（Release）** + **可复用流水线代码（`pipeline/`）**。

## 流水线代码

见 [`pipeline/PIPELINE.md`](pipeline/PIPELINE.md)。

包含：

- `w3x_replace` / `w3x_replace_nocompact`（MPQ 内替换，不 Compact）
- PackyAPI 批量翻译与 WTS 抽写脚本
- Gaias ORPG、沉没之城（Sunken City）上已验证的补丁脚本

配置：复制 `pipeline/.env.example` 为 `.env` 并填入 API Key（不要提交 `.env`）。

## 发布说明

未完全修好前可能不发新的 map Release；日常试玩包用临时链或本机拷贝。Release 仅作备份/定稿。

## 地图成品

历史定稿若有 Release，见本仓库 Releases 页。大文件默认不进 Git 树（见 `.gitignore`）。
