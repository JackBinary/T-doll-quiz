# Matching Algorithm

## Overview

Two-phase scoring. Phase 1 narrows 398 dolls to a cluster of 20-120. Phase 2 scores the user against only that cluster. Final result is the doll with the smallest Hamming distance on Phase 2 answers.

---

## Phase 1: Cluster Assignment

The user answers 10 questions. These are the 10 discriminating questions identified during analysis:

| ID shown to user | Internal key |
|-----------------|--------------|
| 1               | Q1           |
| 2               | Q2           |
| 3               | Q3           |
| 4               | Q7           |
| 5               | Q10          |
| 6               | Q11          |
| 7               | Q12          |
| 8               | Q15          |
| 9               | Q18          |
| 10              | Q20          |

The answers are A/B/C/D. Each answer is a dimension; the user's vector is 10 characters long.

**Cluster assignment**: compute Hamming distance from the user's 10-answer vector to every doll's Phase 1 vector. The user is assigned to the cluster of the single nearest doll (ties broken by first match alphabetically). This is a 1-nearest-neighbor lookup -- no centroid math needed, no scipy at runtime.

```
user_p1 = ["A","D","B","D","A","A","B","A","A","C"]  // 10 answers

best_doll = null
best_dist = 11

for doll in dolls:
    dist = hamming(user_p1, doll.p1_vector)   // 0–10
    if dist < best_dist:
        best_dist = dist
        best_doll = doll

cluster = best_doll.cluster
```

---

## Phase 2: Doll Match

The user answers the cluster's 10 questions (11 for Cluster 1). These are drawn from `phase2_questions.json` for the assigned cluster.

Cluster 1 has an 11th tiebreaker question targeting Lusa vs. MAG-7. All other clusters have exactly 10. The P11 answer is only relevant for Cluster 1; ignore it for all other clusters.

**Scoring**: compute Hamming distance from the user's Phase 2 vector to every doll in the cluster.

```
user_p2 = ["B","A","C","A","D","B","A","C","B","A"]  // or 11 answers for C1

best_doll = null
best_dist = 12

for doll in cluster.dolls:
    dist = hamming(user_p2, doll.p2_vector)   // 0–10 (or 0–11 for C1)
    if dist < best_dist:
        best_dist = dist
        best_doll = doll

return best_doll
```

**Ties on Phase 2**: break by falling back to Phase 1 Hamming distance. Ties there are cosmetically acceptable -- both dolls in the pair have genuinely identical quiz personalities.

---

## Data Files at Runtime

Everything the frontend needs ships as a single pre-built JSON: `quiz_data.json`.

```json
{
  "phase1_questions": [
    {
      "id": "Q1",
      "text": "A plan you worked hard on falls through at the last minute.",
      "answers": {
        "A": "Vent immediately -- you need to get it out of your system",
        "B": "Go quiet and process alone before talking to anyone",
        "C": "Shrug and start adapting, deal with it later",
        "D": "Make a joke about it to cut the tension"
      }
    }
    // ...9 more (Q2, Q3, Q7, Q10, Q11, Q12, Q15, Q18, Q20)
  ],

  "clusters": {
    "1": {
      "archetype": "Loud/Energetic",
      "questions": [
        { "id": "P1", "text": "...", "answers": { "A": "...", ... } }
        // ...10 more (P1–P11 for cluster 1)
      ],
      "dolls": {
        "UMP9": {
          "p1": ["A","D","B","D","A","A","B","A","A","C"],
          "p2": ["B","A","C","A","D","B","A","C","B","A"]
        }
        // ...119 more
      }
    }
    // ...clusters 2–8
  },

  "descriptions": {
    "UMP9": {
      "what_shes_like": "UMP9 is a force of infectious charge...",
      "i_see_you": "You have a pull toward putting on a brave...",
      "portrait": "doll_images/UMP9.png"
    }
    // ...397 more
  }
}
```

Build this file with `python3 export_quiz_data.py` (to be written). It reads `answers/`, `answers_p2/`, `phase2_questions.json`, `descriptions/`, and the question text hardcoded from `build_answers.py`. Output: `frontend/public/quiz_data.json`.

---

## Cluster Reference

| ID | Archetype             | Size |
|----|-----------------------|------|
| 1  | Loud/Energetic        | 120  |
| 2  | Anxious Perfectionist | 26   |
| 3  | Dramatic Expressive   | 20   |
| 4  | Methodical Planner    | 24   |
| 5  | Reserved Adapter      | 73   |
| 6  | Introspective         | 20   |
| 7  | Cautious Observer     | 39   |
| 8  | Quiet Professional    | 76   |

---

## Edge Cases

**Doll has no Phase 2 answers**: exclude from matching. ~20 dolls have no usable quotes; they were skipped during data generation. They simply won't appear as results.

**User answers all the same**: still valid; they'll land in whatever cluster has the most dolls answering that way. The 398-doll universe includes enough variety that even degenerate inputs return a result.

**Phase 2 tie after Phase 1 tiebreak**: return the first alphabetically. Cosmetically acceptable; this only happens when two dolls are genuinely indistinguishable from their quotes.
