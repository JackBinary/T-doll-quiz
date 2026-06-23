#!/usr/bin/env python3
"""
Analyze answer vectors to find:
  1. Low-discrimination questions (most dolls pick the same answer)
  2. Redundant question pairs (answers are highly correlated)
  3. Doll clusters (dolls with identical or near-identical vectors)

Run after build_answers.py completes.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path
from itertools import combinations

ANSWERS_DIR = Path("answers")
QUESTIONS = 20


def load_all() -> dict[str, dict]:
    data = {}
    for f in sorted(ANSWERS_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        if len(d) == QUESTIONS:
            data[f.stem] = d
    return data


def answer_to_int(a: str) -> int:
    return {"A": 0, "B": 1, "C": 2, "D": 3}[a]


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def analyze_discrimination(all_answers: dict):
    print_section("QUESTION DISCRIMINATION")
    print("(% of dolls on the most common answer -- >60% is weak)")
    print()

    weak = []
    for q in range(1, QUESTIONS + 1):
        key = f"Q{q}"
        counts = Counter(v[key] for v in all_answers.values())
        total = sum(counts.values())
        top_answer, top_count = counts.most_common(1)[0]
        pct = top_count / total * 100
        flag = " <<< WEAK" if pct > 60 else ""
        dist = " ".join(f"{a}:{counts.get(a,0)}" for a in "ABCD")
        print(f"  Q{q:02d}: {pct:4.1f}% on {top_answer}  [{dist}]{flag}")
        if pct > 60:
            weak.append(q)

    if weak:
        print(f"\n  Weak questions: {weak}")
    else:
        print("\n  All questions discriminate adequately.")


def analyze_correlation(all_answers: dict):
    print_section("QUESTION PAIR CORRELATION")
    print("(pairs where answers match >70% of the time -- likely redundant)")
    print()

    dolls = list(all_answers.values())
    redundant = []

    for qa, qb in combinations(range(1, QUESTIONS + 1), 2):
        ka, kb = f"Q{qa}", f"Q{qb}"
        matches = sum(1 for d in dolls if d[ka] == d[kb])
        pct = matches / len(dolls) * 100
        if pct > 70:
            print(f"  Q{qa:02d} / Q{qb:02d}: {pct:.1f}% agreement")
            redundant.append((qa, qb))

    if not redundant:
        print("  No highly correlated pairs found.")


def analyze_clusters(all_answers: dict):
    print_section("DOLL CLUSTERS (identical or near-identical vectors)")
    print()

    # Group by exact vector
    by_vector = defaultdict(list)
    for name, answers in all_answers.items():
        vec = tuple(answers[f"Q{q}"] for q in range(1, QUESTIONS + 1))
        by_vector[vec].append(name)

    exact_dupes = {v: names for v, names in by_vector.items() if len(names) > 1}
    if exact_dupes:
        print(f"  Exact duplicates ({len(exact_dupes)} groups):")
        for names in exact_dupes.values():
            print(f"    {', '.join(names)}")
    else:
        print("  No exact duplicates.")

    # Near-duplicates: differ on only 1-2 questions
    names = list(all_answers.keys())
    near = []
    for a, b in combinations(names, 2):
        diff = sum(
            1 for q in range(1, QUESTIONS + 1)
            if all_answers[a][f"Q{q}"] != all_answers[b][f"Q{q}"]
        )
        if diff <= 2:
            near.append((diff, a, b))

    near.sort()
    if near:
        print(f"\n  Near-duplicates (differ on 1-2 questions): {len(near)} pairs")
        for diff, a, b in near[:20]:
            print(f"    {a} / {b}  (differ on {diff})")
        if len(near) > 20:
            print(f"    ... and {len(near)-20} more")
    else:
        print("\n  No near-duplicates found.")


def print_summary(all_answers: dict):
    print_section("SUMMARY")
    print(f"  Dolls with complete answer vectors: {len(all_answers)}")
    # Answer distribution across all questions
    all_counts = Counter()
    for answers in all_answers.values():
        for v in answers.values():
            all_counts[v] += 1
    total = sum(all_counts.values())
    print("  Overall answer distribution:")
    for ans in "ABCD":
        pct = all_counts[ans] / total * 100
        print(f"    {ans}: {pct:.1f}%")


def main():
    all_answers = load_all()
    if not all_answers:
        print("No answer files found. Run build_answers.py first.")
        return

    print_summary(all_answers)
    analyze_discrimination(all_answers)
    analyze_correlation(all_answers)
    analyze_clusters(all_answers)


if __name__ == "__main__":
    main()
