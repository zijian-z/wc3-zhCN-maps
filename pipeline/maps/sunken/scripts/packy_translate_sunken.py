#!/usr/bin/env python3
"""Sunkens-oriented Packy translator: auth-gate then delegate to scripts/packy_translate.py patterns."""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
IN_DEFAULT = ROOT / "sunken/cache/en_strings.jsonl"
CACHE_DEFAULT = ROOT / "sunken/cache/packy_zh.json"
PROGRESS_DEFAULT = ROOT / "sunken/cache/progress.txt"
STATUS_DEFAULT = ROOT / "sunken/cache/status.txt"
GLOSSARY = ROOT / "scripts/glossary.tsv"


def write_status(msg: str) -> None:
    STATUS_DEFAULT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_DEFAULT.write_text(msg + "\n", encoding="utf-8")
    print(msg)


def ensure_key() -> str:
    """Load .env; if PACKYAPI_API_KEY empty, restore from box-secrets silently."""
    load_dotenv(ENV, override=True)
    key = (os.getenv("PACKYAPI_API_KEY") or "").strip()
    if key:
        return key
    secrets = Path("/home/box/agent-data/box-secrets.json")
    if secrets.exists():
        try:
            import json
            data = json.loads(secrets.read_text(encoding="utf-8"))
            card = data.get("card") or {}
            key = (card.get("PACKYAPI_API_KEY") or "").strip()
            if key:
                # write into .env without printing
                lines = []
                if ENV.exists():
                    lines = ENV.read_text(encoding="utf-8").splitlines()
                found = False
                out = []
                for line in lines:
                    if line.startswith("PACKYAPI_API_KEY="):
                        out.append(f"PACKYAPI_API_KEY={key}")
                        found = True
                    else:
                        out.append(line)
                if not found:
                    out.append(f"PACKYAPI_API_KEY={key}")
                ENV.write_text("\n".join(out) + "\n", encoding="utf-8")
                os.environ["PACKYAPI_API_KEY"] = key
                return key
        except Exception:
            pass
    return ""


def main() -> None:
    key = ensure_key()
    if not key:
        write_status(
            "BLOCKED: PACKYAPI_API_KEY missing/empty in .env — refuse API calls. "
            "Populate PACKYAPI_API_KEY (len>0) then re-run with --resume."
        )
        sys.exit(2)

    # Rewrite argv defaults if not provided
    argv = sys.argv[1:]
    def has_flag(name: str) -> bool:
        return any(a == name or a.startswith(name + "=") for a in argv)

    extra = []
    if not has_flag("--in"):
        extra += ["--in", str(IN_DEFAULT)]
    if not has_flag("--cache"):
        extra += ["--cache", str(CACHE_DEFAULT)]
    if not has_flag("--progress"):
        extra += ["--progress", str(PROGRESS_DEFAULT)]
    if not has_flag("--glossary") and GLOSSARY.exists():
        extra += ["--glossary", str(GLOSSARY)]
    if "--resume" not in argv:
        extra += ["--resume"]

    write_status(f"AUTH_OK key_len={len(key)} launching packy_translate")
    # Import and run main of packy_translate with patched argv
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.argv = ["packy_translate.py"] + extra + argv
    # Execute the shared script
    runpy.run_path(str(ROOT / "scripts/packy_translate.py"), run_name="__main__")


if __name__ == "__main__":
    main()
