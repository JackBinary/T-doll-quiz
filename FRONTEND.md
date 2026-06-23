# Frontend Plan

## Tech Stack

Vite + TypeScript, no framework. A quiz is 3 screens and some state -- React overhead isn't justified. Output is a static bundle that can be served from anywhere.

```
frontend/
  index.html
  src/
    main.ts        // entry point, loads quiz_data.json, mounts app
    quiz.ts        // state machine: intro → phase1 → phase2 → result
    render.ts      // all DOM manipulation
    match.ts       // hamming + cluster + doll lookup
  public/
    quiz_data.json   // pre-built by export_quiz_data.py
    doll_images/     // 447 portraits, symlinked or copied from project root
  dist/              // build output (git-ignored)
```

Set up: `npm create vite@latest frontend -- --template vanilla-ts`

---

## Screen States

The app is a state machine with four states. No routing, no history, just swapping what's visible.

### 1. Intro

Title + subtitle + start button. Nothing fancy. Can include a one-line explanation: "20 questions. We match you to a T-doll."

### 2. Question (used for both Phase 1 and Phase 2)

The same component handles all 20-21 questions. The only difference between phases is the question pool in state.

Layout:
```
[progress bar: e.g. "Question 7 of 20"]

[question text -- large, centered]

[A] [answer text]
[B] [answer text]
[C] [answer text]
[D] [answer text]
```

Behavior:
- Clicking an answer immediately advances to the next question (no confirm step)
- After question 10, run cluster assignment (`match.ts`), store cluster ID in state
- Questions 11-20 (or 11-21) draw from the assigned cluster's Phase 2 pool
- No back button -- once answered, locked

Progress bar shows absolute position (e.g. "7 of 20"), not percentage. Clusters vary in size so "7 of 20" is always accurate.

### 3. Result

```
[doll portrait -- full height, left or center]

[doll name]

WHAT SHE'S LIKE
[paragraph from descriptions/<name>.md]

I SEE YOU
[paragraph from descriptions/<name>.md]

[Share / Play Again buttons]
```

The portrait filename maps directly: `quiz_data.descriptions[name].portrait` → `public/doll_images/<name>.png`. Some dolls use non-ASCII filenames (e.g. `43M.png`). The export script handles this.

Share button: copy the doll's name + "I SEE YOU" text to clipboard. Optional: generate a URL with `?result=<name>` so it deep-links back.

---

## State Shape

```ts
type Phase = "intro" | "phase1" | "phase2" | "result"

interface QuizState {
  phase: Phase
  questionIndex: number           // 0-based within current phase
  p1Answers: Record<string, string>   // { Q1: "B", Q7: "A", ... }
  p2Answers: Record<string, string>   // { P1: "A", P2: "C", ... }
  clusterId: number | null
  resultDoll: string | null
}
```

State lives in a plain object in `main.ts`. Every answer click mutates it and calls `render(state)`.

---

## match.ts

Three functions, no external dependencies:

```ts
function hamming(a: string[], b: string[]): number {
  return a.reduce((n, v, i) => n + (v !== b[i] ? 1 : 0), 0)
}

function assignCluster(p1Answers: string[], data: QuizData): number {
  // 1-NN: find doll with smallest hamming distance on Phase 1 vector
  // return that doll's cluster ID
}

function findMatch(p2Answers: string[], clusterId: number, data: QuizData): string {
  // hamming distance vs every doll in cluster on Phase 2 vector
  // secondary sort on Phase 1 hamming distance for ties
  // return doll name
}
```

Both functions run synchronously on answer 10 and answer 20. Dataset is small enough (~400 dolls × 10 answers) that there's no perf concern.

---

## Build Steps Before Frontend Work

1. **Write `export_quiz_data.py`**: bundles `answers/`, `answers_p2/`, `phase2_questions.json`, `descriptions/`, and Phase 1 question text into `frontend/public/quiz_data.json`. This is the only Python step that needs to run before frontend dev starts.

2. **Symlink or copy portraits**: `frontend/public/doll_images/` should point at the existing `doll_images/` directory. A symlink works fine for local dev; copy for deployment.

---

## What's Already Done

- 398 doll Phase 1 answer vectors (`answers/*.json`)
- 398 doll Phase 2 answer vectors (`answers_p2/*.json`)
- 8-cluster assignment (deterministic from `answers/` via scipy)
- Phase 1 + Phase 2 question text (`build_answers.py` + `phase2_questions.json`)
- Descriptions for all non-empty dolls (`descriptions/*.md`)
- Portraits for ~447 dolls (`doll_images/`)
- 100% unique identification across all 398 dolls with known personalities

What's left:
- `export_quiz_data.py` (Python, ~80 lines)
- `frontend/` (Vite + TS, ~300 lines total)

---

## Deployment

The output of `vite build` is a fully static `dist/` folder. Drag it into Netlify, GitHub Pages, or any static host. No server needed.

One thing to check: `quiz_data.json` will be roughly 2-3 MB uncompressed. Vite doesn't bundle it (it's in `public/`), but any CDN will gzip it. Expect ~600KB over the wire.
