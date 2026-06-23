#!/usr/bin/env python3
"""
Phase 2 answer generation: answer the 10 cluster-specific questions for each
T-doll based on raw quotes. Cluster assignment is recomputed from Phase 1 answers.

Requires: answers/, quotes/, phase2_questions.json
Output: answers_p2/<name>.json  {"P1":"B","P2":"A",...}
Resumable. Run: python3 build_phase2_answers.py
After: python3 analyze_phase2.py
"""

import json
import re
from pathlib import Path
from collections import defaultdict

import numpy as np
import requests
from scipy.spatial.distance import pdist
from scipy.cluster.hierarchy import linkage, fcluster

LLM_URL    = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL  = "/home/jgarland/llama-models/gemma-4-12b-it-qat-q4_0.gguf"
LLM_TIMEOUT = 120

QUOTES_DIR     = Path("quotes")
ANSWERS_DIR    = Path("answers")
ANSWERS_P2_DIR = Path("answers_p2")
QUESTIONS_FILE = Path("phase2_questions.json")

GOOD_QS = [1, 2, 3, 7, 10, 11, 12, 15, 18, 20]
ANS_MAP  = {"A": 0, "B": 1, "C": 2, "D": 3}

SYSTEM_PROMPT = """\
You will be given the in-game quotes for a Girls' Frontline T-doll. \
Based ONLY on what the quotes reveal about her personality, behavior, and emotional patterns, \
answer each of the 10 questions as she would.

Rules:
- Use direct quote evidence where it exists.
- Where it doesn't, extrapolate from the overall pattern of how she speaks and acts.
- Do not project generic anime/game tropes. Answer from the quotes.
- If a doll is genuinely ambiguous on a question, pick the answer that fits slightly better.

Respond with ONLY a JSON object with keys P1 through P10, no other text.
Example: {"P1":"B","P2":"D","P3":"A","P4":"C","P5":"B","P6":"A","P7":"D","P8":"C","P9":"B","P10":"A"}
"""


def get_cluster_assignments() -> dict[str, int]:
    data = {}
    for f in sorted(ANSWERS_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        if len(d) == 20:
            data[f.stem] = tuple(d[f"Q{q}"] for q in GOOD_QS)

    names = list(data.keys())
    arr   = np.array([[ANS_MAP[c] for c in data[n]] for n in names])
    dists = pdist(arr, metric="hamming") * 10
    Z     = linkage(dists, method="ward")
    labels = fcluster(Z, 8, criterion="maxclust")
    return {name: int(label) for name, label in zip(names, labels)}


def build_question_block(q_data: dict, cluster_id: int) -> str:
    cluster    = q_data["clusters"][str(cluster_id)]
    recycled   = q_data["recycled_questions"]
    lines = []
    n = 1
    for key in cluster["recycled"]:
        q = recycled[key]
        lines.append(f"P{n}. {q['text']}")
        for letter, text in q["answers"].items():
            lines.append(f"  {letter}. {text}")
        lines.append("")
        n += 1
    for q in cluster["new_questions"]:
        lines.append(f"P{n}. {q['text']}")
        for letter, text in q["answers"].items():
            lines.append(f"  {letter}. {text}")
        lines.append("")
        n += 1
    return "\n".join(lines)


def get_answers(name: str, quotes: str, question_block: str) -> dict:
    prompt = (
        f"T-doll: {name}\n\nQuotes:\n{quotes}\n\n"
        f"Questions:\n{question_block}\n"
        f"Answer as {name} based on the quotes above."
    )
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 120,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    r = requests.post(LLM_URL, json=payload, timeout=LLM_TIMEOUT)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    raw = (msg.get("content") or msg.get("reasoning_content") or "").strip()

    m = re.search(r"\{[^}]+\}", raw, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON in response: {raw[:200]}")
    data = json.loads(m.group())

    for i in range(1, 11):
        key = f"P{i}"
        if key not in data or data[key] not in "ABCD":
            raise ValueError(f"Bad answer for {key}: {data.get(key)}")
    return data


def main():
    ANSWERS_P2_DIR.mkdir(exist_ok=True)

    q_data      = json.loads(QUESTIONS_FILE.read_text())
    assignments = get_cluster_assignments()

    # Pre-build question blocks per cluster
    blocks = {cid: build_question_block(q_data, cid) for cid in range(1, 9)}

    quote_files = sorted(QUOTES_DIR.glob("*.txt"))
    total = len(quote_files)
    done = skipped = errors = 0

    for i, qf in enumerate(quote_files, 1):
        name     = qf.stem
        out_path = ANSWERS_P2_DIR / f"{name}.json"

        if out_path.exists():
            skipped += 1
            continue

        quotes = qf.read_text(encoding="utf-8").strip()
        if len(quotes) < 30:
            skipped += 1
            continue

        cluster_id = assignments.get(name)
        if cluster_id is None:
            print(f"[{i}/{total}] {name} no cluster, skipping")
            skipped += 1
            continue

        print(f"[{i}/{total}] {name} (C{cluster_id})", end="", flush=True)
        try:
            answers = get_answers(name, quotes, blocks[cluster_id])
            out_path.write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
            done += 1
            print(" ok")
        except Exception as e:
            print(f" ERROR: {e}")
            errors += 1

    print(f"\nDone. {done} written, {skipped} skipped, {errors} errors.")


if __name__ == "__main__":
    main()
