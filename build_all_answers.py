#!/usr/bin/env python3
"""
Single-phase answer generation: each of the 87 statements is sent to the LLM
as a separate request so it evaluates every statement cold against the quotes.
Requests run concurrently (up to MAX_WORKERS at a time) for throughput.

Output: answers/<name>.json  {"Q1":3,...,"Q20":1,"P1":4,...,"P67":2}
Resumable per-key: re-running fills in any missing or errored keys.
Run: python3 build_all_answers.py
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm
from pathlib import Path

import requests

LLM_URL     = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL   = "/home/jgarland/llama-models/gemma-4-12b-it-qat-q4_0.gguf"
LLM_TIMEOUT = 60
MAX_WORKERS = 8  # set to match your llama.cpp --parallel value

QUOTES_DIR  = Path("quotes")
ANSWERS_DIR = Path("answers")

# ---------------------------------------------------------------------------
# All 87 statements. "You" refers to the doll throughout.
# Q1–Q20: core personality dimensions
# P1–P67: archetype-derived dimensions (flattened from all clusters)
# ---------------------------------------------------------------------------

STATEMENTS = """\
Q1. When a plan falls through, your first move is to get it out -- talk about it, vent, or make the frustration visible rather than absorb it alone.
Q2. When something genuinely excites or delights you, people around you can tell.
Q3. When you're drained and someone asks how you're doing, you give an honest answer rather than deflecting.
Q4. When something catches you emotionally in public, you sit with it privately rather than mention it to whoever's nearby.
Q5. When you care about someone, you tell them directly rather than showing it through actions or teasing.
Q6. Cancelled plans genuinely bother you, even if you understand why they happen.
Q7. With someone new, you make the first move rather than waiting for them to come to you.
Q8. A friendship can feel genuinely close even without regular contact.
Q9. When you're genuinely skilled at something, you own it -- you don't undersell it or attribute it to luck.
Q10. When you meet someone better than you at something you do, it fires you up rather than throwing you off.
Q11. When asked to do something you've never done before, your default is to figure it out yourself rather than ask for a walkthrough first.
Q12. Failure passes through you fairly quickly -- you file it and keep moving.
Q13. When things are going wrong and there's no clear fix, you tend to work through it alone rather than reach out.
Q14. When someone challenges something you're confident about, you hold your ground until they give you a real reason to update.
Q15. Under real pressure, you get quieter and more focused rather than louder and more energized.
Q16. The most draining conflicts for you are the ones with people you actually care about.
Q17. Getting a project with no instructions energizes you more than it unsettles you.
Q18. You do your best work alone -- collaboration adds coordination overhead you'd rather not deal with.
Q19. When someone you respect tells you you're wrong, you give their view serious weight rather than resisting internally first.
Q20. You tend to think through decisions alone before bringing others in, if at all.
P1. When you get public feedback that stings but isn't wrong, you take it and move on -- no point making it a thing.
P2. When a teammate keeps falling behind, your first reaction is concern for them rather than frustration at the drag on the team.
P3. When you push yourself hard, it's primarily about proving it to yourself -- recognition from others is secondary.
P4. When someone new joins and immediately performs well, your first instinct is excitement -- there's finally someone worth competing against.
P5. When you're genuinely worn down, you'd rather keep the energy up than let people see you flagging.
P6. When you're clearly winning and the other person isn't having fun, you ease up -- you'd rather they enjoy themselves than run up the score.
P7. When something goes wrong and it's partly your fault, you own it out loud right away rather than fixing it first and explaining later.
P8. A genuinely good day is one where the people you care about had a good time and you were part of it.
P9. The most honest version of how you feel usually comes out directly -- you don't really have a filter for it.
P10. When someone compliments something you did, you take it at face value and let it land rather than deflecting or wondering if they meant it.
P11. When things feel like too much, being near a specific person steadies you more than finishing a task does.
P12. You carry a quiet fear that your results might be flukes -- that you haven't fully earned where you are.
P13. When you're ahead of schedule with nothing left to do, you can actually sit with that and let yourself have the moment.
P14. Under rising pressure, you tend to get smaller on the outside while working harder underneath.
P15. When someone close to you gets recognition you wanted, you find a way to work harder rather than go quiet about it.
P16. When you do something embarrassing in front of someone you wanted to impress, you laugh it off out loud before anyone else can react.
P17. When someone keeps getting more recognition than you, it bothers you more than you'll admit -- and it tends to come out sideways.
P18. When you care about someone, you get louder and funnier around them -- attention is how you reach people.
P19. When you can't stop thinking about a mistake, what eventually breaks you out of it is finding a way to laugh at yourself.
P20. When you're performing well and someone's watching, you go harder -- the audience is the fuel.
P21. When something falls through and it wasn't your fault, what you need is acknowledgment that you handled it well despite the circumstances.
P22. When you've worked hard at something with no recognition, you make the effort more visible rather than quietly doubling down.
P23. When someone pushes back and they're partially right, you get defensive first and come around later when you've thought about it.
P24. When you have unexpected free time, you migrate straight into whatever's next rather than actually unplugging.
P25. When a teammate makes a small but avoidable mistake, you pull them aside and walk through it rather than let it go.
P26. When you want to do something nice for someone, you tend to think through what they actually need and quietly handle it before they have to ask.
P27. When someone senior is clearly wrong in a group setting, you speak up -- rank doesn't make something correct.
P28. Your workspace tends to be clean and presentable -- you feel off if it isn't.
P29. When a stranger is clearly struggling, you step in and offer something concrete -- you don't need a relationship established first.
P30. When you're performing better than expected, you're pleased but already thinking about where the gaps are -- something can always be tighter.
P31. When you hit a problem you can't immediately solve, your first move is to break it down and identify what's actually the problem before trying anything.
P32. When you feel genuinely at ease, it's usually because you're doing something useful -- productivity feels like rest for you.
P33. There's a big difference between how you present to people you don't know well and who you actually are -- the first version is considerably more polished.
P34. When asked to do something your way versus their way, you default to their approach -- results matter more than method.
P35. When you've formed a genuine opinion of someone, they probably won't hear it from you unless they ask directly.
P36. When a teammate struggles with something you're good at, you step in before they have to ask.
P37. After a long day, talking is how you reset -- you're generally up for conversation even when tired.
P38. When you hit your limit with someone, you tend to get quieter -- shorter answers, less engagement.
P39. When your work gets criticized publicly, you keep what you feel internal -- you address the criticism, not the feeling.
P40. When you unwind, you tend toward something low-key with one or two people you trust rather than going fully solo.
P41. When you're proud of something and no one noticed, you feel fine -- you know what you accomplished.
P42. When someone you care about needs you to cross a line you won't cross, you hold it without making it a confrontation.
P43. When you've been sitting with something heavy, you tend to wait until you understand it well enough to explain it clearly before saying anything.
P44. When someone compliments something you worked hard on, it sits with you longer than it probably should.
P45. When someone offers to help with something you've been carrying quietly, you decline -- they shouldn't have to deal with it.
P46. When you want to check in on someone you care about, you find a practical reason to reach out rather than just saying you wanted to see how they're doing.
P47. The version of yourself you most want to be is someone who doesn't carry every mistake forward -- who can set it down and move on.
P48. When something reminds you of an old mistake, you try to find what you'd do differently -- it becomes useful, eventually.
P49. On a quieter night with nothing urgent, you tend to end up somewhere between rest and thinking -- your mind goes where it wants.
P50. When someone tries to get to know you better, you tend to turn it back around on them -- you're more comfortable asking than being asked.
P51. A mistake you've been carrying feels less like a standard to close and more like something you keep returning to, even when you try not to.
P52. When someone you respect confides something they've never told anyone, your first instinct is to stay very still and let them finish.
P53. When you do something genuinely well and someone notices, you wonder if they'd still think so if they saw the full picture.
P54. When you realize you've said more than you meant to with someone you care about, you change the subject as fast as possible.
P55. What most reliably makes you feel like yourself is knowing exactly where you stand.
P56. When you're around someone new, you're mainly paying attention to whether they can be trusted with what you already know.
P57. When given real responsibility over something that matters to someone, your first thought is that you need to understand it completely before you touch it.
P58. When you've been genuinely useful and someone tries to thank you, you want to tell them it was nothing -- and you mostly mean it.
P59. Your loyalty shows up mainly as showing up prepared, every time, without being asked.
P60. When someone compliments your work sincerely, you say thank you and move on -- the job was the point, not the recognition.
P61. The way you signal trust to a longtime partner is by stopping to double-check their work -- that's the whole signal.
P62. When you make a mistake that affects someone else, the worst part is facing them afterward -- even if they're fine with it, you aren't.
P63. When you do something you've done a hundred times, you look for what can be done better this time.
P64. When something goes wrong and it's not your fault, you focus on the fix rather than the fault -- questions of blame come later.
P65. The side of you almost no one sees is softer -- more affected by things than you let on.
P66. The clearest sign you're comfortable with someone is that you stop managing how you come across around them.
P67. What you want most from the people close to you is steadiness -- to be the same person every time.
"""

# Build lookup: "Q1" -> statement text, "P3" -> statement text, etc.
STATEMENT_MAP: dict[str, str] = {}
for _line in STATEMENTS.strip().splitlines():
    _m = re.match(r'^([QP]\d+)\.\s+(.+)$', _line)
    if _m:
        STATEMENT_MAP[_m.group(1)] = _m.group(2)

ALL_KEYS = [f"Q{i}" for i in range(1, 21)] + [f"P{i}" for i in range(1, 68)]
assert len(ALL_KEYS) == 87
assert all(k in STATEMENT_MAP for k in ALL_KEYS), "Statement map is missing keys"

SYSTEM_PROMPT = """\
You are evaluating a single personality statement about a Girls' Frontline T-doll based on her in-game quotes.
"You" in the statement refers to the doll, not you.
Rate how well the statement describes the doll:
  4 = Strongly agree
  3 = Slightly agree
  2 = Slightly disagree
  1 = Strongly disagree
Use the full range. Respond with ONLY a single digit: 1, 2, 3, or 4. Nothing else.\
"""


def get_rating(name: str, quotes: str, statement: str) -> int:
    prompt = (
        f"T-doll: {name}\n\n"
        f"Quotes:\n{quotes}\n\n"
        f"Statement: {statement}"
    )
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 5,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    r = requests.post(LLM_URL, json=payload, timeout=LLM_TIMEOUT)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    raw = (msg.get("content") or msg.get("reasoning_content") or "").strip()

    m = re.search(r'\b([1-4])\b', raw)
    if not m:
        raise ValueError(f"No valid rating in response: {raw!r}")
    return int(m.group(1))


def load_existing(path: Path) -> dict:
    """Return existing integer-valued ratings, or {} if file is missing/stale."""
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text())
        return {k: v for k, v in d.items() if isinstance(v, int) and v in (1, 2, 3, 4)}
    except Exception:
        return {}


def main():
    ANSWERS_DIR.mkdir(exist_ok=True)

    quote_files = sorted(QUOTES_DIR.glob("*.txt"))
    done = skipped = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        doll_bar = tqdm(quote_files, unit="doll", dynamic_ncols=True)
        for qf in doll_bar:
            name     = qf.stem
            out_path = ANSWERS_DIR / f"{name}.json"

            existing = load_existing(out_path)
            missing  = [k for k in ALL_KEYS if k not in existing]

            if not missing:
                skipped += 1
                continue

            quotes = qf.read_text(encoding="utf-8").strip()
            if len(quotes) < 30:
                skipped += 1
                continue

            doll_bar.set_description(name)

            futures = {
                pool.submit(get_rating, name, quotes, STATEMENT_MAP[k]): k
                for k in missing
            }

            results = dict(existing)
            error_count = 0
            with tqdm(as_completed(futures), total=len(futures), unit="stmt",
                      leave=False, dynamic_ncols=True) as stmt_bar:
                for fut in stmt_bar:
                    k = futures[fut]
                    try:
                        results[k] = fut.result()
                    except Exception as e:
                        tqdm.write(f"  ERROR {name}/{k}: {e}")
                        error_count += 1

            ordered = {k: results[k] for k in ALL_KEYS if k in results}
            out_path.write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")

            complete = len(ordered) == 87
            if complete and not error_count:
                done += 1
            else:
                tqdm.write(f"  {name}: {len(ordered)}/87 saved, {error_count} errors")

    print(f"\nDone. {done} complete, {skipped} skipped.")


if __name__ == "__main__":
    main()


