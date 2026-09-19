#!/usr/bin/env python3
"""Translate remaining mostly-EN WTS ability bodies for Sunken r4.

Clears identity cache entries, uses small batches, soft placeholder checks.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
IN_JSONL = ROOT / "sunken/cache/r4_en_bodies.jsonl"
CACHE = ROOT / "sunken/cache/packy_zh.json"
PROGRESS = ROOT / "sunken/cache/progress_r4b.txt"
GLOSSARY = ROOT / "scripts/glossary.tsv"

SYSTEM_PROMPT = """You are a professional game localizer for Warcraft III Reforged ORPG UI and tooltips.
Translate English to Simplified Chinese (zh-CN).

CRITICAL RULES:
1. Preserve ALL placeholders and WC3 format codes EXACTLY as-is: %s, %d, %1%, %2%, %3%, |n, |r, |R, |cAARRGGBB (any hex), and angle refs like <AIsh,DataB1>, <R0I3,mod1>.
2. Do not invent, drop, reorder, or alter placeholders.
3. Keep proper nouns when listed in the glossary (prefer glossary forms).
4. Keep Discord URLs, version numbers, and pure author credits unchanged when they appear alone or as URLs.
5. Output ONLY a JSON array of objects: [{"i": <int>, "t": "<translation>"}] matching input indices.
6. No markdown fences, no commentary.
7. Natural concise UI Chinese; game terms like Hero/Mana/Gold/Lumber stay consistent with glossary.
8. Translate labels: Type:→类型：, Damage:→伤害：, Mana Cost:→法力消耗：, Cooldown:→冷却：, Passive:→被动：, Active:→主动：, Range:→范围：, Duration:→持续时间：.
"""

COLOR_RE = re.compile(r"\|c[0-9A-Fa-f]{8}", re.I)
PIPE_RE = re.compile(r"\|[nNrR]")
PCT_RE = re.compile(r"%\d+%|%[sd]")
ANGLE_RE = re.compile(r"<[A-Za-z0-9_]+,[A-Za-z0-9_]+>")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def load_glossary(path: Path) -> dict[str, str]:
    g: dict[str, str] = {}
    if not path.exists():
        return g
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "\t" not in line:
            continue
        a, b = line.split("\t", 1)
        g[a.strip()] = b.strip()
    return g


def soft_ok(src: str, dst: str) -> bool:
    """Accept if Chinese present and format tokens roughly preserved."""
    if not CJK_RE.search(dst):
        return False
    # color codes: same multiset (case-insensitive)
    sc = [x.lower() for x in COLOR_RE.findall(src)]
    dc = [x.lower() for x in COLOR_RE.findall(dst)]
    if sorted(sc) != sorted(dc):
        # allow if counts equal and all src colors appear
        if len(sc) != len(dc) or any(c not in dc for c in sc):
            return False
    if sorted(PIPE_RE.findall(src)) != sorted(PIPE_RE.findall(dst)):
        # |n count must match at least
        if PIPE_RE.findall(src).count("|n") + PIPE_RE.findall(src).count("|N") != (
            PIPE_RE.findall(dst).count("|n") + PIPE_RE.findall(dst).count("|N")
        ):
            return False
    if PCT_RE.findall(src) != PCT_RE.findall(dst):
        return False
    if ANGLE_RE.findall(src) != ANGLE_RE.findall(dst):
        return False
    return True


def parse_response(content: str, n: int) -> dict[int, str]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\[[\s\S]*\]", content)
        if not m:
            raise
        data = json.loads(m.group(0))
    out: dict[int, str] = {}
    for obj in data:
        if not isinstance(obj, dict):
            continue
        i = obj.get("i", obj.get("index"))
        t = obj.get("t", obj.get("translation", obj.get("zh")))
        if i is None or t is None:
            continue
        out[int(i)] = str(t)
    if len(out) < max(1, n // 2):
        raise ValueError(f"too few translations: {len(out)}/{n}")
    return out


def build_user(batch: list[str], glossary: dict[str, str]) -> str:
    hits = []
    for src in batch:
        for en, zh in glossary.items():
            if en in src:
                hits.append(f"{en} → {zh}")
    seen = set()
    uniq = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            uniq.append(h)
    gloss = ""
    if uniq:
        gloss = "Glossary hints:\n" + "\n".join(uniq[:40]) + "\n\n"
    payload = [{"i": i, "s": s} for i, s in enumerate(batch)]
    return (
        gloss
        + 'Translate each object.s to Simplified Chinese. Return JSON array [{"i":0,"t":"..."}, ...] only.\n\n'
        + json.dumps(payload, ensure_ascii=False)
    )


def translate_one_batch(client: OpenAI, model: str, batch: list[str], glossary: dict[str, str]) -> dict[int, str]:
    last = None
    for attempt in range(6):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user(batch, glossary)},
                ],
                temperature=0.15,
                timeout=180,
            )
            content = resp.choices[0].message.content or ""
            parsed = parse_response(content, len(batch))
            out: dict[int, str] = {}
            for i, src in enumerate(batch):
                dst = parsed.get(i)
                if dst is None:
                    continue
                if soft_ok(src, dst):
                    out[i] = dst
                else:
                    # keep trying whole batch once more by not accepting
                    pass
            if len(out) >= max(1, (len(batch) + 1) // 2):
                return out
            # if few accepted, still return accepted ones
            if out and attempt >= 2:
                return out
            last = ValueError(f"soft_ok accepted {len(out)}/{len(batch)}")
        except Exception as e:
            last = e
            wait = min(45.0, (2 ** attempt) + random.uniform(0, 1))
            time.sleep(wait)
    raise RuntimeError(f"batch failed: {last}")


def main() -> None:
    load_dotenv(ROOT / ".env")
    key = (os.getenv("PACKYAPI_API_KEY") or "").strip()
    base = (os.getenv("PACKYAPI_BASE_URL") or "https://cf.api.fan/v1").strip()
    model = (os.getenv("PACKYAPI_MODEL") or "deepseek-v4-flash").strip()
    if not key:
        print("ERROR: no API key", file=sys.stderr)
        sys.exit(2)

    rows = [json.loads(l) for l in IN_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    glossary = load_glossary(GLOSSARY)

    # clear identity for targets
    cleared = 0
    for r in rows:
        src = r["source"]
        if src in cache and not CJK_RE.search(cache[src]):
            del cache[src]
            cleared += 1
    print(f"cleared_identity={cleared}")

    todo = []
    seen = set()
    for r in rows:
        src = r["source"]
        if src in seen:
            continue
        seen.add(src)
        if src in cache and CJK_RE.search(cache[src]):
            continue
        todo.append(src)

    print(f"todo={len(todo)} cached_good_targets={len(seen)-len(todo)} model={model}")
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    with PROGRESS.open("a", encoding="utf-8") as f:
        f.write(f"START todo={len(todo)}\n")

    if not todo:
        print("nothing to do")
        return

    client = OpenAI(api_key=key, base_url=base)
    # smaller batches for long strings
    batches: list[list[str]] = []
    cur: list[str] = []
    cur_chars = 0
    for s in todo:
        if cur and (len(cur) >= 6 or cur_chars + len(s) > 3500):
            batches.append(cur)
            cur, cur_chars = [], 0
        cur.append(s)
        cur_chars += len(s)
    if cur:
        batches.append(cur)

    print(f"batches={len(batches)}")
    done = 0
    errors = 0

    def work(idx: int, batch: list[str]):
        # shrink on failure
        try:
            mapped = translate_one_batch(client, model, batch, glossary)
            return idx, {batch[i]: t for i, t in mapped.items()}, None
        except Exception as e:
            if len(batch) <= 1:
                return idx, {}, str(e)
            mid = max(1, len(batch) // 2)
            updates = {}
            errs = []
            for part in (batch[:mid], batch[mid:]):
                _, u, err = work(idx, part)
                updates.update(u)
                if err:
                    errs.append(err)
            return idx, updates, ("; ".join(errs) if errs else None)

    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(work, i, b) for i, b in enumerate(batches)]
        for fut in as_completed(futs):
            bidx, updates, err = fut.result()
            if updates:
                cache.update(updates)
                done += len(updates)
                CACHE.write_text(
                    json.dumps(cache, ensure_ascii=False, indent=0),
                    encoding="utf-8",
                )
                msg = f"OK batch={bidx} +{len(updates)} done={done}/{len(todo)} cache={len(cache)}"
                print(msg, flush=True)
                with PROGRESS.open("a", encoding="utf-8") as f:
                    f.write(msg + "\n")
            if err:
                errors += 1
                print(f"ERROR batch={bidx}: {err}", file=sys.stderr)
                with PROGRESS.open("a", encoding="utf-8") as f:
                    f.write(f"ERROR batch={bidx}: {err}\n")

    # final coverage
    good = sum(1 for s in seen if s in cache and CJK_RE.search(cache[s]))
    print(f"FINISH done={done} errors={errors} target_good={good}/{len(seen)}")
    with PROGRESS.open("a", encoding="utf-8") as f:
        f.write(f"FINISH done={done} errors={errors} target_good={good}/{len(seen)}\n")


if __name__ == "__main__":
    main()
