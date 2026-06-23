#!/usr/bin/env python3
"""
Second-pass pipeline: reads profiles/ and generates user-facing result content.

For each doll produces two things:
  - A short paragraph ("What she's like") for under the portrait
  - A punchy "I see you" quip addressed to the user who matched with her

Output: descriptions/<name>.md (resumable)
Run: python3 build_descriptions.py
"""

import re
import time
from pathlib import Path

import requests

LLM_URL   = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = "/home/jgarland/llama-models/gemma-4-12b-it-qat-q4_0.gguf"

PROFILES_DIR     = Path("profiles")
DESCRIPTIONS_DIR = Path("descriptions")

LLM_TIMEOUT = 120

SYSTEM_PROMPT = """\
You write the result screen copy for a personality quiz whose final answer is a Girls' Frontline T-doll.
The user has just been told which doll they matched with. You need two pieces of copy.

1. "What she's like" — a single paragraph, 3-5 sentences. Warm and specific. Written about the doll \
in third person. No game mechanics, no weapon stats. Pure personality and vibe. Should feel like a \
real character description, not a summary of bullet points.

2. "I see you" — 1-2 sentences addressed directly to the user ("You..."). Not a compliment, not a \
horoscope platitude. A specific, slightly uncomfortably accurate observation about the kind of person \
who matched with this doll. The best version of this will make someone feel seen without being able \
to explain exactly how the quiz figured it out.

Output ONLY these two blocks, in this exact format — no other text:

WHAT SHE'S LIKE
[paragraph]

I SEE YOU
[quip]
"""


def generate_description(name: str, profile_text: str) -> str:
    prompt = (
        f"Here is the personality profile for the T-doll {name}:\n\n"
        f"{profile_text}\n\n"
        f"Write the result screen copy for {name}."
    )
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.75,
        "max_tokens": 400,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    r = requests.post(LLM_URL, json=payload, timeout=LLM_TIMEOUT)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    return (msg.get("content") or msg.get("reasoning_content") or "").strip()


def main():
    DESCRIPTIONS_DIR.mkdir(exist_ok=True)

    profile_files = sorted(PROFILES_DIR.glob("*.md"))
    total = len(profile_files)
    done = skipped = errors = 0

    for i, pf in enumerate(profile_files, 1):
        name = pf.stem
        out_path = DESCRIPTIONS_DIR / pf.name

        if out_path.exists():
            skipped += 1
            continue

        profile_text = pf.read_text(encoding="utf-8").strip()
        if profile_text == f"## {name}\n\n*No quotes available.*":
            out_path.write_text(profile_text + "\n", encoding="utf-8")
            skipped += 1
            continue

        print(f"[{i}/{total}] {name}", end="", flush=True)

        try:
            desc = generate_description(name, profile_text)
            out_path.write_text(f"## {name}\n\n{desc}\n", encoding="utf-8")
            done += 1
            print(" ok")
        except Exception as e:
            print(f" ERROR: {e}")
            errors += 1

    print(f"\nDone. {done} written, {skipped} skipped, {errors} errors.")


if __name__ == "__main__":
    main()
