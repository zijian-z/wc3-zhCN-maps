#!/usr/bin/env python3
"""Batch-translate JSONL EN strings to zh-CN via PackyAPI (OpenAI-compatible)."""
from __future__ import annotations

import argparse
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

# Line-buffer logs when redirected to files
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IN = ROOT / "data/en_strings.jsonl"
DEFAULT_CACHE = ROOT / "cache/packy_zh.json"
DEFAULT_GLOSSARY = ROOT / "scripts/glossary.tsv"
DEFAULT_PROGRESS = ROOT / "cache/progress.txt"

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
"""

PLACEHOLDER_RE = re.compile(
    r"%\d+%|%[sd]|\|c[0-9A-Fa-f]{8}|\|[nNrR]|<[A-Za-z0-9_]+,[A-Za-z0-9_]+>"
)


def load_env() -> tuple[str, str, str]:
    load_dotenv(ROOT / ".env")
    key = os.getenv("PACKYAPI_API_KEY", "").strip()
    base = os.getenv("PACKYAPI_BASE_URL", "https://cf.api.fan/v1").strip()
    model = os.getenv("PACKYAPI_MODEL", "deepseek-v4-flash").strip()
    if not key:
        print("ERROR: PACKYAPI_API_KEY missing in .env", file=sys.stderr)
        sys.exit(1)
    return key, base, model


def load_glossary(path: Path) -> dict[str, str]:
    g: dict[str, str] = {}
    if not path or not path.exists():
        return g
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "\t" not in line:
            continue
        a, b = line.split("\t", 1)
        g[a.strip()] = b.strip()
    return g


def load_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception as e:
        print(f"WARN: cache load failed ({e}), starting fresh", file=sys.stderr)
    return {}


def save_cache(path: Path, cache: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=False),
        encoding="utf-8",
    )
    tmp.replace(path)


def write_progress(path: Path, msg: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def placeholders(s: str) -> list[str]:
    return PLACEHOLDER_RE.findall(s)


def placeholders_ok(src: str, dst: str) -> bool:
    return placeholders(src) == placeholders(dst)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def build_user_payload(batch: list[dict], glossary: dict[str, str]) -> str:
    gloss_hint = ""
    if glossary:
        # Only include glossary entries that appear in this batch (cheap filter)
        hits = []
        for item in batch:
            src = item["source"]
            for en, zh in glossary.items():
                if en in src:
                    hits.append(f"{en} → {zh}")
        if hits:
            # unique preserve order
            seen = set()
            uniq = []
            for h in hits:
                if h not in seen:
                    seen.add(h)
                    uniq.append(h)
            gloss_hint = "Glossary hints:\n" + "\n".join(uniq[:40]) + "\n\n"

    payload = [{"i": i, "s": item["source"]} for i, item in enumerate(batch)]
    return (
        gloss_hint
        + "Translate each object.s to Simplified Chinese. Return JSON array "
        + '[{"i":0,"t":"..."}, ...] only.\n\n'
        + json.dumps(payload, ensure_ascii=False)
    )


def parse_response(content: str, n: int) -> dict[int, str]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    # try direct JSON
    data = None
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\[[\s\S]*\]", content)
        if m:
            data = json.loads(m.group(0))
    if not isinstance(data, list):
        raise ValueError(f"expected JSON array, got: {content[:200]}")
    out: dict[int, str] = {}
    for obj in data:
        if not isinstance(obj, dict):
            continue
        i = obj.get("i", obj.get("index"))
        t = obj.get("t", obj.get("translation", obj.get("zh")))
        if i is None or t is None:
            continue
        out[int(i)] = str(t)
    if len(out) < n // 2:
        raise ValueError(f"too few translations returned: {len(out)}/{n}")
    return out


def translate_batch(
    client: OpenAI,
    model: str,
    batch: list[dict],
    glossary: dict[str, str],
    max_retries: int = 6,
) -> dict[int, str]:
    user = build_user_payload(batch, glossary)
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
                timeout=120,
            )
            content = resp.choices[0].message.content or ""
            parsed = parse_response(content, len(batch))
            # fill missing with identity; validate placeholders
            result: dict[int, str] = {}
            for i, item in enumerate(batch):
                src = item["source"]
                if i not in parsed:
                    result[i] = src
                    continue
                dst = parsed[i]
                if not placeholders_ok(src, dst):
                    # one micro-retry for this string alone is expensive; keep EN
                    result[i] = src
                else:
                    result[i] = dst
            return result
        except Exception as e:
            last_err = e
            wait = min(60.0, (2 ** attempt) + random.uniform(0, 1.5))
            err_s = str(e).lower()
            if "rate" in err_s or "429" in err_s or "timeout" in err_s:
                time.sleep(wait)
            else:
                time.sleep(min(10.0, wait))
    raise RuntimeError(f"batch failed after retries: {last_err}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="infile", type=Path, default=DEFAULT_IN)
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    ap.add_argument("--progress", type=Path, default=DEFAULT_PROGRESS)
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="Max new strings to translate")
    ap.add_argument("--resume", action="store_true", help="Skip already-cached sources")
    ap.add_argument(
        "--kind",
        default="",
        help="Only rows whose kind matches (wts|fdf|misc)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key, base, model = load_env()
    # Never print key
    print(f"model={model} base={base} batch={args.batch_size} conc={args.concurrency}")

    rows = read_jsonl(args.infile)
    if args.kind:
        rows = [r for r in rows if r.get("kind") == args.kind]

    cache = load_cache(args.cache)
    glossary = load_glossary(args.glossary)

    todo = []
    for r in rows:
        src = r["source"]
        if args.resume and src in cache:
            continue
        if src in cache and not args.resume:
            # still skip duplicates already done unless forcing
            continue
        todo.append(r)

    # Deduplicate todo by source (extract already unique, but be safe)
    seen_src = set()
    uniq_todo = []
    for r in todo:
        if r["source"] in seen_src:
            continue
        seen_src.add(r["source"])
        uniq_todo.append(r)
    todo = uniq_todo

    if args.limit and args.limit > 0:
        todo = todo[: args.limit]

    print(
        f"rows={len(rows)} cached={len(cache)} todo={len(todo)} "
        f"kind={args.kind or 'all'}"
    )
    write_progress(
        args.progress,
        f"START todo={len(todo)} cached={len(cache)} kind={args.kind or 'all'} "
        f"limit={args.limit}",
    )

    if args.dry_run or not todo:
        print("nothing to translate" if not todo else "dry-run: skip API")
        write_progress(args.progress, f"DONE todo=0 (dry={args.dry_run})")
        return

    client = OpenAI(api_key=key, base_url=base)

    batches = [
        todo[i : i + args.batch_size]
        for i in range(0, len(todo), args.batch_size)
    ]

    done = 0
    errors = 0
    lock_updates: list[tuple[str, str]] = []

    def work(batch_idx: int, batch: list[dict]) -> tuple[int, dict[str, str], str | None]:
        """Translate batch; on failure shrink (halve) until size 1, then give up."""
        try:
            mapped = translate_batch(client, model, batch, glossary)
            updates = {}
            for i, item in enumerate(batch):
                updates[item["source"]] = mapped.get(i, item["source"])
            return batch_idx, updates, None
        except Exception as e:
            if len(batch) <= 1:
                return batch_idx, {}, str(e)
            # shrink: split and translate sequentially
            mid = max(1, len(batch) // 2)
            updates: dict[str, str] = {}
            errs: list[str] = []
            for part in (batch[:mid], batch[mid:]):
                if not part:
                    continue
                _, part_upd, part_err = work(batch_idx, part)
                updates.update(part_upd)
                if part_err:
                    errs.append(part_err)
            if updates:
                return batch_idx, updates, ("; ".join(errs) if errs else None)
            return batch_idx, {}, str(e)

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
        futs = [ex.submit(work, i, b) for i, b in enumerate(batches)]
        for fut in as_completed(futs):
            bidx, updates, err = fut.result()
            if updates:
                cache.update(updates)
                done += len(updates)
                # always save so resume survives crashes / long hung siblings
                save_cache(args.cache, cache)
                write_progress(
                    args.progress,
                    f"OK batch={bidx} +{len(updates)} done={done}/{len(todo)} "
                    f"cache={len(cache)}",
                )
                print(f"batch {bidx}: +{len(updates)} (done {done}/{len(todo)})")
            if err:
                errors += 1
                print(f"ERROR batch {bidx}: {err}", file=sys.stderr)
                write_progress(args.progress, f"ERROR batch={bidx} err={err}")

    save_cache(args.cache, cache)
    write_progress(
        args.progress,
        f"FINISH done={done} errors={errors} cache={len(cache)}",
    )
    print(f"finished done={done} errors={errors} cache_size={len(cache)}")


if __name__ == "__main__":
    main()
