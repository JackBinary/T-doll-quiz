#!/usr/bin/env python3
"""
Replace overused words and phrases in descriptions/ with random alternatives.
Phrases are matched before individual words (longest-first) to avoid partial clobbers.
Writes back in place. Safe to re-run -- uses a seeded hash per file so results
are deterministic for the same file content.
"""

import hashlib
import random
import re
from pathlib import Path

DESCRIPTIONS_DIR = Path("descriptions")

# Order matters: longer phrases first so they match before their component words do.
REPLACEMENTS = [
    # Structural phrases
    ("a whirlwind of",              ["a force of", "a flash of", "a burst of", "a surge of", "a spark of"]),
    ("carries herself with",        ["moves with", "operates with", "holds herself with", "leads with"]),
    ("carries himself with",        ["moves with", "operates with", "holds himself with", "leads with"]),
    ("moves through the world",     ["navigates the world", "exists in the world", "walks through the world", "operates in the world"]),
    ("lies beneath her",            ["hides behind her", "sits behind her", "waits under her", "lives under her"]),
    ("lies beneath his",            ["hides behind his", "sits behind his", "waits under his", "lives under his"]),
    ("lies beneath the",            ["hides behind the", "sits behind the", "waits under the", "lives under the"]),
    ("hides beneath",               ["hides behind", "sits under", "waits beneath", "lives behind"]),
    ("with practiced grace",        ["with precision", "with care", "with ease", "without fanfare"]),
    ("with quiet grace",            ["with measured care", "with contained ease", "without fanfare", "with practiced restraint"]),
    ("to ensure that",              ["to make sure that", "to keep", "to guarantee that"]),
    ("to ensure",                   ["to make sure", "to guarantee", "to keep"]),
    ("you're the type who",         ["you're someone who", "you're wired to", "you're the kind of person who", "you're built to"]),
    ("you are the type who",        ["you're someone who", "you're wired to", "you're the kind of person who", "you're built to"]),
    ("a habit of",                  ["a pattern of", "a pull toward", "a way of"]),

    # Single words (case-insensitive match handled below)
    ("quietly",         ["privately", "inwardly", "without drawing attention", "to herself"]),
    ("constantly",      ["always", "perpetually", "endlessly", "relentlessly", "consistently"]),
    ("secretly",        ["privately", "inwardly", "quietly"]),
    ("devotion",        ["loyalty", "dedication", "attachment", "care"]),
    ("terrified",       ["afraid", "anxious", "uneasy", "scared"]),
    ("exterior",        ["surface", "shell", "front", "outside"]),
    ("exterior,",       ["surface,", "shell,", "front,", "outside,"]),
    ("demeanor",        ["manner", "bearing", "presence", "way"]),
    ("beneath",         ["under", "behind", "below", "past"]),
    ("facade",          ["front", "shell", "surface", "face"]),
]

# Single-word substitutions that need whole-word matching
WORD_REPLACEMENTS = [
    ("quiet",       ["still", "restrained", "measured", "contained", "composed"]),
    ("quietly",     ["privately", "inwardly", "softly", "without a word"]),
    ("energy",      ["presence", "force", "pull", "charge", "weight", "current"]),
    ("carries",     ["holds", "wears", "moves with", "leads with"]),
    ("moves",       ["walks", "operates", "navigates", "exists"]),
    ("grace",       ["ease", "precision", "control", "care", "poise"]),
]


def seeded_choice(options: list, seed: str) -> str:
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    return options[h % len(options)]


def diversify(text: str, file_seed: str) -> str:
    call_counter = [0]

    def pick(options: list, context: str) -> str:
        call_counter[0] += 1
        seed = f"{file_seed}:{context}:{call_counter[0]}"
        return seeded_choice(options, seed)

    # Phase 1: phrase replacements (already ordered longest-first within category)
    for phrase, alternatives in REPLACEMENTS:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        def replace_phrase(m, alts=alternatives, orig=phrase):
            replacement = pick(alts, orig)
            # Preserve leading capitalisation
            if m.group()[0].isupper():
                replacement = replacement[0].upper() + replacement[1:]
            return replacement
        text = pattern.sub(replace_phrase, text)

    # Phase 2: whole-word replacements
    for word, alternatives in WORD_REPLACEMENTS:
        pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
        def replace_word(m, alts=alternatives, orig=word):
            replacement = pick(alts, orig)
            if m.group()[0].isupper():
                replacement = replacement[0].upper() + replacement[1:]
            return replacement
        text = pattern.sub(replace_word, text)

    return text


def main():
    files = sorted(DESCRIPTIONS_DIR.glob("*.md"))
    changed = skipped = 0

    for f in files:
        original = f.read_text(encoding="utf-8")
        if "No quotes available" in original:
            skipped += 1
            continue

        diversified = diversify(original, f.stem)
        if diversified != original:
            f.write_text(diversified, encoding="utf-8")
            changed += 1
        else:
            skipped += 1

    print(f"Done. {changed} files updated, {skipped} unchanged.")


if __name__ == "__main__":
    main()
