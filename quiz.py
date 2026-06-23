#!/usr/bin/env python3
"""
Akinator-style T-doll personality quiz.

Asks strategic questions to narrow down to a single T-doll via soft Manhattan
distance probability matching. No doll is hard-eliminated; scores decay
smoothly with accumulated distance so early disagreements don't lock you out.
"""

import json
import math
from pathlib import Path

ANSWERS_DIR = Path("answers")

# Controls how sharply distance converts to probability.
# Higher = faster convergence but more sensitive to early noise.
ALPHA = 0.35

MIN_QUESTIONS = 10   # always ask at least this many
MAX_QUESTIONS = 25   # hard ceiling

# Stop early when top doll is this many times more probable than second place.
# Scale-invariant: works with 21 dolls or 398.
LEAD_RATIO = 10.0

ALL_KEYS = [f"Q{i}" for i in range(1, 21)] + [f"P{i}" for i in range(1, 68)]

STATEMENT_MAP: dict[str, str] = {
    "Q1":  "When a plan falls through, your first move is to get it out: talk about it, vent, or make the frustration visible rather than absorb it alone.",
    "Q2":  "When something genuinely excites or delights you, people around you can tell.",
    "Q3":  "When you're drained and someone asks how you're doing, you give an honest answer rather than deflecting.",
    "Q4":  "When something catches you emotionally in public, you sit with it privately rather than mention it to whoever's nearby.",
    "Q5":  "When you care about someone, you tell them directly rather than showing it through actions or teasing.",
    "Q6":  "Cancelled plans genuinely bother you, even if you understand why they happen.",
    "Q7":  "With someone new, you make the first move rather than waiting for them to come to you.",
    "Q8":  "A friendship can feel genuinely close even without regular contact.",
    "Q9":  "When you're genuinely skilled at something, you own it: you don't undersell it or attribute it to luck.",
    "Q10": "When you meet someone better than you at something you do, it fires you up rather than throwing you off.",
    "Q11": "When asked to do something you've never done before, your default is to figure it out yourself rather than ask for a walkthrough first.",
    "Q12": "Failure passes through you fairly quickly: you file it and keep moving.",
    "Q13": "When things are going wrong and there's no clear fix, you tend to work through it alone rather than reach out.",
    "Q14": "When someone challenges something you're confident about, you hold your ground until they give you a real reason to update.",
    "Q15": "Under real pressure, you get quieter and more focused rather than louder and more energized.",
    "Q16": "The most draining conflicts for you are the ones with people you actually care about.",
    "Q17": "Getting a project with no instructions energizes you more than it unsettles you.",
    "Q18": "You do your best work alone: collaboration adds coordination overhead you'd rather not deal with.",
    "Q19": "When someone you respect tells you you're wrong, you give their view serious weight rather than resisting internally first.",
    "Q20": "You tend to think through decisions alone before bringing others in, if at all.",
    "P1":  "When you get public feedback that stings but isn't wrong, you take it and move on: no point making it a thing.",
    "P2":  "When a teammate keeps falling behind, your first reaction is concern for them rather than frustration at the drag on the team.",
    "P3":  "When you push yourself hard, it's primarily about proving it to yourself: recognition from others is secondary.",
    "P4":  "When someone new joins and immediately performs well, your first instinct is excitement: there's finally someone worth competing against.",
    "P5":  "When you're genuinely worn down, you'd rather keep the energy up than let people see you flagging.",
    "P6":  "When you're clearly winning and the other person isn't having fun, you ease up: you'd rather they enjoy themselves than run up the score.",
    "P7":  "When something goes wrong and it's partly your fault, you own it out loud right away rather than fixing it first and explaining later.",
    "P8":  "A genuinely good day is one where the people you care about had a good time and you were part of it.",
    "P9":  "The most honest version of how you feel usually comes out directly: you don't really have a filter for it.",
    "P10": "When someone compliments something you did, you take it at face value and let it land rather than deflecting or wondering if they meant it.",
    "P11": "When things feel like too much, being near a specific person steadies you more than finishing a task does.",
    "P12": "You carry a quiet fear that your results might be flukes: that you haven't fully earned where you are.",
    "P13": "When you're ahead of schedule with nothing left to do, you can actually sit with that and let yourself have the moment.",
    "P14": "Under rising pressure, you tend to get smaller on the outside while working harder underneath.",
    "P15": "When someone close to you gets recognition you wanted, you find a way to work harder rather than go quiet about it.",
    "P16": "When you do something embarrassing in front of someone you wanted to impress, you laugh it off out loud before anyone else can react.",
    "P17": "When someone keeps getting more recognition than you, it bothers you more than you'll admit: and it tends to come out sideways.",
    "P18": "When you care about someone, you get louder and funnier around them: attention is how you reach people.",
    "P19": "When you can't stop thinking about a mistake, what eventually breaks you out of it is finding a way to laugh at yourself.",
    "P20": "When you're performing well and someone's watching, you go harder: the audience is the fuel.",
    "P21": "When something falls through and it wasn't your fault, what you need is acknowledgment that you handled it well despite the circumstances.",
    "P22": "When you've worked hard at something with no recognition, you make the effort more visible rather than quietly doubling down.",
    "P23": "When someone pushes back and they're partially right, you get defensive first and come around later when you've thought about it.",
    "P24": "When you have unexpected free time, you migrate straight into whatever's next rather than actually unplugging.",
    "P25": "When a teammate makes a small but avoidable mistake, you pull them aside and walk through it rather than let it go.",
    "P26": "When you want to do something nice for someone, you tend to think through what they actually need and quietly handle it before they have to ask.",
    "P27": "When someone senior is clearly wrong in a group setting, you speak up: rank doesn't make something correct.",
    "P28": "Your workspace tends to be clean and presentable: you feel off if it isn't.",
    "P29": "When a stranger is clearly struggling, you step in and offer something concrete: you don't need a relationship established first.",
    "P30": "When you're performing better than expected, you're pleased but already thinking about where the gaps are: something can always be tighter.",
    "P31": "When you hit a problem you can't immediately solve, your first move is to break it down and identify what's actually the problem before trying anything.",
    "P32": "When you feel genuinely at ease, it's usually because you're doing something useful: productivity feels like rest for you.",
    "P33": "There's a big difference between how you present to people you don't know well and who you actually are: the first version is considerably more polished.",
    "P34": "When asked to do something your way versus their way, you default to their approach: results matter more than method.",
    "P35": "When you've formed a genuine opinion of someone, they probably won't hear it from you unless they ask directly.",
    "P36": "When a teammate struggles with something you're good at, you step in before they have to ask.",
    "P37": "After a long day, talking is how you reset: you're generally up for conversation even when tired.",
    "P38": "When you hit your limit with someone, you tend to get quieter: shorter answers, less engagement.",
    "P39": "When your work gets criticized publicly, you keep what you feel internal: you address the criticism, not the feeling.",
    "P40": "When you unwind, you tend toward something low-key with one or two people you trust rather than going fully solo.",
    "P41": "When you're proud of something and no one noticed, you feel fine: you know what you accomplished.",
    "P42": "When someone you care about needs you to cross a line you won't cross, you hold it without making it a confrontation.",
    "P43": "When you've been sitting with something heavy, you tend to wait until you understand it well enough to explain it clearly before saying anything.",
    "P44": "When someone compliments something you worked hard on, it sits with you longer than it probably should.",
    "P45": "When someone offers to help with something you've been carrying quietly, you decline: they shouldn't have to deal with it.",
    "P46": "When you want to check in on someone you care about, you find a practical reason to reach out rather than just saying you wanted to see how they're doing.",
    "P47": "The version of yourself you most want to be is someone who doesn't carry every mistake forward: who can set it down and move on.",
    "P48": "When something reminds you of an old mistake, you try to find what you'd do differently: it becomes useful, eventually.",
    "P49": "On a quieter night with nothing urgent, you tend to end up somewhere between rest and thinking: your mind goes where it wants.",
    "P50": "When someone tries to get to know you better, you tend to turn it back around on them: you're more comfortable asking than being asked.",
    "P51": "A mistake you've been carrying feels less like a standard to close and more like something you keep returning to, even when you try not to.",
    "P52": "When someone you respect confides something they've never told anyone, your first instinct is to stay very still and let them finish.",
    "P53": "When you do something genuinely well and someone notices, you wonder if they'd still think so if they saw the full picture.",
    "P54": "When you realize you've said more than you meant to with someone you care about, you change the subject as fast as possible.",
    "P55": "What most reliably makes you feel like yourself is knowing exactly where you stand.",
    "P56": "When you're around someone new, you're mainly paying attention to whether they can be trusted with what you already know.",
    "P57": "When given real responsibility over something that matters to someone, your first thought is that you need to understand it completely before you touch it.",
    "P58": "When you've been genuinely useful and someone tries to thank you, you want to tell them it was nothing: and you mostly mean it.",
    "P59": "Your loyalty shows up mainly as showing up prepared, every time, without being asked.",
    "P60": "When someone compliments your work sincerely, you say thank you and move on: the job was the point, not the recognition.",
    "P61": "The way you signal trust to a longtime partner is by stopping to double-check their work: that's the whole signal.",
    "P62": "When you make a mistake that affects someone else, the worst part is facing them afterward: even if they're fine with it, you aren't.",
    "P63": "When you do something you've done a hundred times, you look for what can be done better this time.",
    "P64": "When something goes wrong and it's not your fault, you focus on the fix rather than the fault: questions of blame come later.",
    "P65": "The side of you almost no one sees is softer: more affected by things than you let on.",
    "P66": "The clearest sign you're comfortable with someone is that you stop managing how you come across around them.",
    "P67": "What you want most from the people close to you is steadiness: to be the same person every time.",
}

assert len(STATEMENT_MAP) == 87


def load_dolls() -> dict[str, dict[str, int]]:
    """Return {name: {key: rating}} for every complete (87-key) answer file."""
    dolls: dict[str, dict[str, int]] = {}
    for path in sorted(ANSWERS_DIR.glob("*.json")):
        try:
            data: dict = json.loads(path.read_text())
        except Exception:
            continue
        if all(
            k in data and isinstance(data[k], int) and data[k] in (1, 2, 3, 4)
            for k in ALL_KEYS
        ):
            dolls[path.stem] = {k: data[k] for k in ALL_KEYS}
    return dolls


def to_probs(distances: dict[str, float]) -> dict[str, float]:
    """Convert distance dict to probabilities via shifted softmax."""
    min_d = min(distances.values())
    scores = {n: math.exp(-ALPHA * (d - min_d)) for n, d in distances.items()}
    total = sum(scores.values())
    return {n: s / total for n, s in scores.items()}


def pick_question(dolls: dict, probs: dict, asked: set[str]) -> str | None:
    """
    Return the un-asked question with the highest probability-weighted variance
    across all dolls. High variance means the dolls most likely to match the
    user are spread across different answer values: so asking it will
    discriminate maximally between the current top candidates.
    """
    candidates = [q for q in ALL_KEYS if q not in asked]
    if not candidates:
        return None

    best_q, best_var = None, -1.0
    for q in candidates:
        mu = sum(probs[n] * dolls[n][q] for n in dolls)
        var = sum(probs[n] * (dolls[n][q] - mu) ** 2 for n in dolls)
        if var > best_var:
            best_var, best_q = var, q
    return best_q


def run_quiz(dolls: dict[str, dict[str, int]]) -> None:
    asked: set[str] = set()
    answered: dict[str, int] = {}
    probs = {n: 1.0 / len(dolls) for n in dolls}

    print(f"\n{len(dolls)} dolls loaded.\n")
    print("Rate each statement about yourself:")
    print("  1 = Strongly disagree   2 = Slightly disagree")
    print("  3 = Slightly agree      4 = Strongly agree\n")

    for round_num in range(1, MAX_QUESTIONS + 1):
        sorted_p = sorted(probs.values(), reverse=True)
        top_p = sorted_p[0]
        second_p = sorted_p[1] if len(sorted_p) > 1 else 0.0

        if round_num > MIN_QUESTIONS and second_p > 0 and top_p / second_p >= LEAD_RATIO:
            break

        q = pick_question(dolls, probs, asked)
        if q is None:
            break

        print(f"[{round_num}] {STATEMENT_MAP[q]}")
        while True:
            raw = input("    > ").strip()
            if raw in ("1", "2", "3", "4"):
                break
            print("    Enter 1, 2, 3, or 4.")

        answered[q] = int(raw)
        asked.add(q)

        distances = {
            n: sum(abs(answered[k] - dolls[n][k]) for k in answered)
            for n in dolls
        }
        probs = to_probs(distances)

    top_name = max(probs, key=probs.get)
    top5 = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:5]

    print(f"\n{'─' * 40}")
    print(f"  You are: {top_name}")
    print(f"{'─' * 40}\n")

    for rank, (name, p) in enumerate(top5, 1):
        bar = "█" * round(p * 36)
        marker = " <--" if rank == 1 else ""
        print(f"  {rank}. {name:<22} {p:5.1%}  {bar}{marker}")
    print()


def main() -> None:
    dolls = load_dolls()
    if not dolls:
        print(f"No complete answer files found in {ANSWERS_DIR}/")
        print("Run build_all_answers.py first.")
        return
    run_quiz(dolls)


if __name__ == "__main__":
    main()
