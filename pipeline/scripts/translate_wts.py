#!/usr/bin/env python3
"""Translate war3map.wts values via glossary; unknown strings get [中] prefix for MVP visibility."""
import argparse, re
from pathlib import Path

DEFAULT = {
    "Player 1": "玩家 1",
    "Force 1": "势力 1",
    "dommy": "占位技能",
    "Systems": "系统",
    "Any": "任意",
    "Nondescript": "无描述",
    "Unknown": "未知",
    "(Dummy)": "（占位）",
}

def load_glossary(path):
    g = dict(DEFAULT)
    if not path:
        return g
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "\t" not in line:
            continue
        a,b=line.split("\t",1)
        g[a]=b
    return g

def translate_wts(text, glossary, mark_unknown=False):
    pat=re.compile(r"(STRING\s+\d+\s*(?://[^\n]*)?\s*\{)(.*?)(\})", re.S)
    out=[]; last=0; n=0
    for m in pat.finditer(text):
        out.append(text[last:m.start()])
        header, body, close = m.group(1), m.group(2), m.group(3)
        lines=body.split("\n")
        prefix=[]; vals=[]
        for line in lines:
            if not vals and (line.strip()=="" or line.strip().startswith("//")):
                prefix.append(line)
            else:
                vals.append(line)
        raw="\n".join(vals).strip("\n").strip()
        if raw in glossary:
            zh=glossary[raw]
        elif mark_unknown and raw:
            zh="[中] "+raw
        else:
            zh=raw
        new_body=("\n".join(prefix))
        if prefix and not new_body.endswith("\n"):
            new_body += "\n"
        if not prefix:
            new_body = "\n"
        new_body += zh + "\n"
        out.append(header+new_body+close)
        last=m.end(); n+=1
    out.append(text[last:])
    return "".join(out), n

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--glossary"); ap.add_argument("--mark-unknown", action="store_true")
    args=ap.parse_args()
    src=Path(args.src).read_text(encoding="utf-8", errors="replace")
    # strip BOM
    if src.startswith("\ufeff"):
        src=src[1:]
    zh,n=translate_wts(src, load_glossary(args.glossary), args.mark_unknown)
    Path(args.dst).write_text(zh, encoding="utf-8")
    print(f"translated {n} STRING blocks -> {args.dst}")

if __name__=="__main__":
    main()
