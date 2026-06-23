# Which T-Doll Are You?

A personality quiz that matches you to one of the T-Dolls from Girls' Frontline. Answer a handful of statements about yourself, from strongly disagree to strongly agree, and it finds your closest match out of a roster of nearly 400 characters.

Play it here: https://jackbinary.github.io/T-doll-quiz/

This is an unofficial fan project. It is not affiliated with Sunborn or the official game, and all T-Doll images are property of Sunborn, used for non-commercial fan purposes.

## How the matching works

Every doll is a vector of 87 numbers. Each number is a 1-to-4 rating against a single statement (for example, "When something genuinely excites or delights you, people around you can tell"). The first 20 statements cover core personality dimensions; the remaining 67 come from character archetypes.

When you take the quiz, your answers build the same kind of vector, one statement at a time. After each answer:

1. **Distance.** Every doll's vector is compared to yours by Manhattan distance (the sum of absolute differences across the statements you've answered so far).
2. **Probability.** Distances become probabilities through a shifted softmax with `ALPHA = 0.35`. Closer dolls get more of the weight.
3. **Next question.** The quiz picks the unanswered statement with the highest probability-weighted variance across the dolls still in contention. That is the statement the leading candidates most disagree on, so it splits the field fastest.

The quiz asks at least 10 statements and never more than 25. It stops early once the leading doll holds 10 times the probability of the runner-up. The on-screen "in contention" number is an inverse Simpson index, a smooth count of how many dolls are still realistically in the running. It never shows names while you play, so you can't steer the result toward a doll you already like.

The web version in `quiz.js` is a direct port of the Python in `quiz.py`. Same constants, same math, same questions.

## Repo layout

| Path | What's in it |
| --- | --- |
| `profiles/` | One markdown profile per doll: summary, traits, communication style. |
| `quotes/` | Voice lines and dialogue per doll, the raw material for rating statements. |
| `descriptions/` | Per-doll result text, split into "What She's Like" and "I See You" sections. |
| `answers/` | The generated vectors. One JSON per doll: `{"Q1":3, ..., "P67":2}`. |
| `doll_images/` | Official CG art, one PNG per doll. |
| `image_manifest.json` | Maps each doll name to its image file. |
| `quiz.py` | The quiz as a command-line program. |
| `site/` | The static web quiz (HTML, CSS, JS). |
| `build_*.py` | The pipeline scripts described below. |

## The pipeline

The data is built in stages, each script reading the output of the last.

1. **`build_image_map.py`** writes `image_manifest.json`, pairing each doll with a local CG or pulling the full-size image from IOPWiki when one isn't already in `doll_images/`.
2. **`build_all_answers.py`** turns quotes into vectors. It sends all 87 statements to a local LLM (a llama.cpp server on `127.0.0.1:8080`, running Gemma), one statement per request so each is judged cold against the doll's quotes. Requests run up to 8 at a time. It writes `answers/<name>.json` and is resumable: re-running fills in only the missing or errored keys.
3. **`build_site_data.py`** bundles everything the site needs into `site/quiz_data.js`: the statements, the answer vectors, the result descriptions, and the image paths. A doll only makes it into the bundle if it has a complete 87-key vector and an image that exists on disk, so half-finished entries are skipped automatically.

## Running it locally

The command-line quiz needs only Python (standard library, no packages):

```sh
python3 quiz.py
```

To open the web version, regenerate the data and serve the `site/` folder:

```sh
python3 build_site_data.py
python3 -m http.server -d site 8000
```

Then visit http://localhost:8000.

Regenerating the vectors with `build_all_answers.py` is the only step with extra requirements: a running llama.cpp server and the `requests` and `tqdm` packages.

## Adding or updating a doll

Drop the doll's `quotes/<name>.md` and `profiles/<name>.md` in place, make sure `doll_images/<name>.png` exists (and is listed in `image_manifest.json`), then run `build_all_answers.py` to generate its vector and `build_site_data.py` to fold it into the site bundle. Write a `descriptions/<name>.md` with the result text so the match screen has something to show.

## Deployment

A push to `main` triggers `.github/workflows/deploy.yml`, which regenerates `quiz_data.js` from the committed answers, copies the images into the published folder, and ships `site/` to GitHub Pages. There is no manual build step: edit a doll, commit, push, and the live quiz updates within a minute or two.
