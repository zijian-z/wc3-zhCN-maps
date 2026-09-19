#!/usr/bin/env bash
# Usage: pipeline_wts.sh <map.w3x> [glossary.tsv]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MAP_IN="$1"
GLOSSARY="${2:-}"
NAME="$(basename "$MAP_IN" | sed 's/\.[^.]*$//')"
WORK="$ROOT/work/$NAME"
TOOL="$ROOT/tools/w3x_replace"
mkdir -p "$WORK" "$ROOT/maps/out"
cp -f "$MAP_IN" "$WORK/original.w3x"
cp -f "$MAP_IN" "$WORK/map_zh.w3x"
"$TOOL" extract "$WORK/map_zh.w3x" war3map.wts "$WORK/war3map.wts.en"
python3 "$ROOT/scripts/translate_wts.py" "$WORK/war3map.wts.en" "$WORK/war3map.wts.zh" ${GLOSSARY:+--glossary "$GLOSSARY"}
"$TOOL" replace "$WORK/map_zh.w3x" war3map.wts "$WORK/war3map.wts.zh"
"$TOOL" extract "$WORK/map_zh.w3x" war3map.wts "$WORK/war3map.wts.verify"
cp -f "$WORK/map_zh.w3x" "$ROOT/maps/out/${NAME}_zh.w3x"
echo "OK -> $ROOT/maps/out/${NAME}_zh.w3x"
