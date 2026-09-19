#!/usr/bin/env bash
# wowr EN -> zh-CN localization pipeline (PackyAPI)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONUNBUFFERED=1

echo "== extract =="
python scripts/extract_strings.py --out data/en_strings.jsonl
python scripts/extract_strings.py --kinds fdf,misc --out data/en_fdf_misc.jsonl
python scripts/extract_strings.py --kinds wts --out data/en_wts.jsonl

echo "== translate FDF (all) =="
python scripts/packy_translate.py --in data/en_fdf_misc.jsonl --kind fdf --resume \
  --batch-size 30 --concurrency 4

echo "== translate Misc =="
python scripts/packy_translate.py --in data/en_fdf_misc.jsonl --kind misc --resume \
  --batch-size 20 --concurrency 2

echo "== pilot WTS (100) =="
python scripts/packy_translate.py --in data/en_wts.jsonl --kind wts --resume \
  --limit 100 --batch-size 25 --concurrency 3

echo "== apply =="
python scripts/apply_translations.py

echo "== full WTS (background) =="
echo "Continuing full WTS (uses cache/progress.txt):"
echo "  PYTHONUNBUFFERED=1 nohup python scripts/packy_translate.py --in data/en_wts.jsonl --kind wts --resume \\"
echo "    --batch-size 30 --concurrency 4 > cache/wts_full.log 2>&1 &"
echo "  # when done / periodically: python scripts/apply_translations.py"

echo "Done. Cache: cache/packy_zh.json  Progress: cache/progress.txt"
