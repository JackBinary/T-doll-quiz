#!/usr/bin/env python3
"""
Analyze Phase 2 answer vectors within each cluster.
Reports discrimination, correlation, and uniqueness progress.
Run after build_phase2_answers.py completes.
"""

import json
from pathlib import Path
from collections import Counter, defaultdict
from itertools import combinations

import numpy as np
from scipy.spatial.distance import pdist
from scipy.cluster.hierarchy import linkage, fcluster

ANSWERS_DIR    = Path("answers")
ANSWERS_P2_DIR = Path("answers_p2")
QUESTIONS_FILE = Path("phase2_questions.json")

GOOD_QS = [1, 2, 3, 7, 10, 11, 12, 15, 18, 20]
ANS_MAP  = {"A": 0, "B": 1, "C": 2, "D": 3}

ARCHETYPES = {
    1: "Loud/Energetic",
    2: "Anxious Perfectionist",
    3: "Dramatic Expressive",
    4: "Methodical Planner",
    5: "Reserved Adapter",
    6: "Introspective",
    7: "Cautious Observer",
    8: "Quiet Professional",
}


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


def load_p2() -> dict[str, dict]:
    data = {}
    for f in sorted(ANSWERS_P2_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        if len(d) == 10:
            data[f.stem] = d
    return data


def analyze_cluster(cid: int, members: list, p2: dict):
    present = [m for m in members if m in p2]
    if not present:
        return

    print(f"\n{'='*60}")
    print(f"  Cluster {cid} — {ARCHETYPES.get(cid)} ({len(present)}/{len(members)})")
    print(f"{'='*60}")
    print("  Discrimination (>60% = WEAK):")

    weak = []
    for q in range(1, 11):
        key = f"P{q}"
        counts = Counter(p2[m][key] for m in present if key in p2[m])
        if not counts:
            continue
        total = sum(counts.values())
        top_ans, top_n = counts.most_common(1)[0]
        pct = top_n / total * 100
        flag = " <<< WEAK" if pct > 60 else ""
        dist = " ".join(f"{a}:{counts.get(a,0)}" for a in "ABCD")
        print(f"    P{q:02d}: {pct:4.1f}% on {top_ans}  [{dist}]{flag}")
        if pct > 60:
            weak.append(q)

    if weak:
        print(f"\n  Weak Phase-2 questions: {[f'P{q}' for q in weak]}")

    # Correlation
    redundant = []
    for qa, qb in combinations(range(1, 11), 2):
        ka, kb = f"P{qa}", f"P{qb}"
        matches = sum(1 for m in present if p2[m].get(ka) == p2[m].get(kb))
        pct = matches / len(present) * 100
        if pct > 70:
            redundant.append((qa, qb, pct))
    if redundant:
        print(f"\n  Correlated pairs (>70%):")
        for qa, qb, pct in redundant:
            print(f"    P{qa}/P{qb}: {pct:.1f}%")

    # Uniqueness within cluster
    by_vec = defaultdict(list)
    for m in present:
        vec = tuple(p2[m].get(f"P{q}", "?") for q in range(1, 11))
        by_vec[vec].append(m)

    unique   = sum(1 for v in by_vec.values() if len(v) == 1)
    in_dupes = sum(len(v) for v in by_vec.values() if len(v) > 1)

    print(f"\n  Unique: {unique}/{len(present)}  Still in duplicate groups: {in_dupes}")

    exact = [(v, ns) for v, ns in by_vec.items() if len(ns) > 1]
    if exact:
        print(f"  Exact duplicate groups ({len(exact)}):")
        for _, ns in exact[:10]:
            print(f"    {', '.join(ns)}")
        if len(exact) > 10:
            print(f"    ... and {len(exact)-10} more")

    near = []
    for a, b in combinations(present, 2):
        diff = sum(1 for q in range(1, 11)
                   if p2[a].get(f"P{q}") != p2[b].get(f"P{q}"))
        if 1 <= diff <= 2:
            near.append((diff, a, b))
    near.sort()
    if near:
        print(f"  Near-duplicates (1-2 diff): {len(near)} pairs")
        for diff, a, b in near[:5]:
            print(f"    {a} / {b}  (diff {diff})")
        if len(near) > 5:
            print(f"    ... and {len(near)-5} more")


def main():
    assignments = get_cluster_assignments()
    p2          = load_p2()

    clusters = defaultdict(list)
    for name, cid in assignments.items():
        clusters[cid].append(name)

    print(f"Phase 2 answers loaded: {len(p2)}")

    for cid in sorted(clusters, key=lambda x: -len(clusters[x])):
        analyze_cluster(cid, clusters[cid], p2)

    # ── Overall uniqueness across Phase 1 (10 good Qs) + Phase 2 (10 cluster Qs)
    p1 = {}
    for f in sorted(ANSWERS_DIR.glob("*.json")):
        d = json.loads(f.read_text())
        if len(d) == 20:
            p1[f.stem] = {f"Q{q}": d[f"Q{q}"] for q in GOOD_QS}

    by_combined = defaultdict(list)
    for name in p2:
        if name not in p1:
            continue
        vec = tuple(p1[name].get(f"Q{q}", "?") for q in GOOD_QS)
        vec += tuple(p2[name].get(f"P{q}", "?") for q in range(1, 11))
        by_combined[vec].append(name)

    total   = len(p2)
    unique  = sum(1 for v in by_combined.values() if len(v) == 1)
    dupes   = sum(len(v) for v in by_combined.values() if len(v) > 1)

    print(f"\n{'='*60}")
    print(f"  OVERALL (Phase 1 + Phase 2 combined)")
    print(f"{'='*60}")
    print(f"  Uniquely identified: {unique}/{total} ({unique/total*100:.1f}%)")
    print(f"  Still in duplicate groups: {dupes}")

    if dupes:
        exact_combined = [(v, ns) for v, ns in by_combined.items() if len(ns) > 1]
        print(f"  Combined duplicate groups ({len(exact_combined)}):")
        for _, ns in exact_combined[:15]:
            print(f"    {', '.join(ns)}")
        if len(exact_combined) > 15:
            print(f"    ... and {len(exact_combined)-15} more")


if __name__ == "__main__":
    main()
