#!/usr/bin/env python3
"""
Third-pass pipeline: answer the 20 quiz questions as each T-doll,
based on their raw quotes (not summaries).

Output: answers/<name>.json — a dict of {"Q1": "B", "Q2": "A", ...}
Resumable. Run: python3 build_answers.py

After completion, run: python3 analyze_answers.py to check for
question redundancy and clustering.
"""

import json
import re
import time
from pathlib import Path

import requests

LLM_URL   = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = "/home/jgarland/llama-models/gemma-4-12b-it-qat-q4_0.gguf"

QUOTES_DIR  = Path("quotes")
ANSWERS_DIR = Path("answers")

LLM_TIMEOUT = 120

QUESTIONS = """\
Q1. A plan you worked hard on falls through at the last minute.
  A. Vent immediately -- you need to get it out of your system
  B. Go quiet and process alone before talking to anyone
  C. Shrug and start adapting, deal with it later
  D. Make a joke about it to cut the tension

Q2. Something genuinely delights you. How visible is it?
  A. People around you definitely know
  B. You smile but keep it to yourself
  C. It leaks out eventually whether you intend it to or not
  D. You get loud about it -- containing it doesn't really occur to you

Q3. You're exhausted and someone asks how you're doing.
  A. "Fine." (and you mean it as a closing statement)
  B. Something honest but brief
  C. More than you planned to, and then feel weird about it
  D. Exactly what's going on -- you don't really have a filter for this

Q4. A song hits you unexpectedly hard while other people are around.
  A. You mention it to whoever's nearby
  B. You turn it up and let it wash over you privately
  C. You change the subject in your head and move on
  D. You replay it in your head for the rest of the day and say nothing

Q5. You care about someone. How do they know?
  A. You tell them directly
  B. You show up consistently without making a big deal of it
  C. You do small things and hope they notice
  D. You tease them -- that's just how you are

Q6. A friend cancels plans last minute.
  A. Mild disappointment but you understand
  B. More bothered than you let on
  C. Honestly, kind of relieved
  D. You're already texting to reschedule

Q7. When someone new enters your circle, you tend to...
  A. Watch them for a while before engaging
  B. Find a reason to be helpful and see what develops
  C. Let them come to you
  D. Jump in -- you like meeting people

Q8. What does "close" actually mean to you in a friendship?
  A. Picking up exactly where you left off after months apart
  B. Knowing what's going on with each other on a regular basis
  C. Being in the same space a lot, doing your own things
  D. Rare but deep conversations

Q9. You're genuinely good at something. How do you carry that?
  A. You know it, you just don't broadcast it
  B. You're still not fully convinced -- might just be luck
  C. You've worked for it and you own it
  D. You'd rather the results speak than claim it yourself

Q10. Someone is better at your thing than you are.
  A. Competitive -- it motivates you
  B. Fine, you use them as a benchmark
  C. A little destabilizing, if you're honest
  D. Mostly irrelevant -- you're not doing it for the comparison

Q11. You're asked to do something you've never done before. First thought?
  A. "I'll figure it out."
  B. "What do I need to know first?"
  C. "Can someone walk me through it?"
  D. "What if I'm not actually good at it?"

Q12. Failure. What does it do to you?
  A. Burns for a bit, then you're back with adjustments
  B. You file it and keep moving -- it's information
  C. It sticks around longer than it should
  D. It clarifies something -- you learn more from it than success

Q13. Things are going wrong and there's no clear fix.
  A. Get methodical -- break it down, find the next step
  B. Lean on someone who can help you think through it
  C. Absorb it alone until you have something actionable
  D. Find the one thing you can actually control and go there

Q14. Someone challenges you on something you're confident about.
  A. Hold your ground until they make a compelling case
  B. Hear them out genuinely -- maybe they see something you don't
  C. Agree outwardly even if you're not convinced
  D. Push back immediately

Q15. Under real pressure, you get...
  A. Focused -- everything else falls away
  B. Faster, louder, more
  C. Quieter than usual
  D. Funnier -- it's a coping mechanism

Q16. The most draining kind of conflict is...
  A. When the other person won't engage honestly
  B. When you're in the wrong and you know it
  C. When there's no resolution possible
  D. When it's with someone you actually care about

Q17. Someone hands you a project with no instructions.
  A. Good -- you'll figure out what it needs
  B. Uncertain until you know what success looks like
  C. Energized -- constraints are someone else's problem
  D. Fine, but you'll check in once you have a direction

Q18. Working alone vs. with others?
  A. Alone -- you work better without the coordination overhead
  B. Together -- a good team is hard to replicate
  C. Depends entirely on the people
  D. Together for the messy parts, alone to finish

Q19. Someone you respect tells you you're wrong.
  A. Consider it seriously -- they usually have a reason
  B. Disagree internally until you've worked through it yourself
  C. Want to understand their reasoning before you update anything
  D. Feel it, even if they turn out to be right

Q20. You make decisions by...
  A. Thinking it through alone first, then maybe consulting
  B. Talking it out with someone you trust
  C. Going with your gut and adjusting as you go
  D. Researching until you feel confident
"""

SYSTEM_PROMPT = """\
You will be given the in-game quotes for a Girls' Frontline T-doll. \
Based ONLY on what the quotes reveal about her personality, behavior, and emotional patterns, \
answer each of the 20 questions as she would.

Rules:
- Use direct quote evidence where it exists.
- Where it doesn't, extrapolate from the overall pattern of how she speaks and acts.
- Do not project generic anime/game tropes. Answer from the quotes.
- If a doll is genuinely ambiguous on a question, pick the answer that fits slightly better.

Respond with ONLY a JSON object, no other text. Example:
{"Q1":"B","Q2":"D","Q3":"A","Q4":"C","Q5":"B","Q6":"A","Q7":"D","Q8":"C","Q9":"B","Q10":"A","Q11":"D","Q12":"C","Q13":"B","Q14":"A","Q15":"D","Q16":"C","Q17":"B","Q18":"A","Q19":"D","Q20":"C"}
"""


def get_answers(name: str, quotes: str) -> dict:
    prompt = (
        f"T-doll: {name}\n\nQuotes:\n{quotes}\n\n"
        f"Questions:\n{QUESTIONS}\n"
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

    # Extract JSON from response (model sometimes adds surrounding text)
    match = re.search(r'\{[^}]+\}', raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in response: {raw[:200]}")
    data = json.loads(match.group())

    # Validate we got all 20 questions with valid answers
    for i in range(1, 21):
        key = f"Q{i}"
        if key not in data or data[key] not in ("A", "B", "C", "D"):
            raise ValueError(f"Missing or invalid answer for {key}: {data.get(key)}")

    return data


def main():
    ANSWERS_DIR.mkdir(exist_ok=True)

    quote_files = sorted(QUOTES_DIR.glob("*.txt"))
    total = len(quote_files)
    done = skipped = errors = 0

    for i, qf in enumerate(quote_files, 1):
        name = qf.stem
        out_path = ANSWERS_DIR / f"{name}.json"

        if out_path.exists():
            skipped += 1
            continue

        quotes = qf.read_text(encoding="utf-8").strip()
        if len(quotes) < 30:
            skipped += 1
            continue

        print(f"[{i}/{total}] {name}", end="", flush=True)

        try:
            answers = get_answers(name, quotes)
            out_path.write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
            done += 1
            print(" ok")
        except Exception as e:
            print(f" ERROR: {e}")
            errors += 1

    print(f"\nDone. {done} answer sets written, {skipped} skipped, {errors} errors.")


if __name__ == "__main__":
    main()
