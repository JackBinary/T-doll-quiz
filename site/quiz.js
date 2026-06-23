/* ============================================================
   Akinator-style T-doll quiz engine.
   Ports quiz.py: soft Manhattan distance -> shifted softmax,
   max-variance adaptive question selection, lead-ratio early stop.
   ============================================================ */

const DATA = window.QUIZ_DATA;
const { statements, keys: ALL_KEYS, dolls } = DATA;

// Tuning, kept identical to quiz.py.
const ALPHA = 0.35;
const MIN_QUESTIONS = 10;
const MAX_QUESTIONS = 25;
const LEAD_RATIO = 10.0;

/* ---------- algorithm ---------- */

function toProbs(distances) {
  let min = Infinity;
  for (const d of Object.values(distances)) if (d < min) min = d;
  const scores = {};
  let total = 0;
  for (const [n, d] of Object.entries(distances)) {
    const s = Math.exp(-ALPHA * (d - min));
    scores[n] = s; total += s;
  }
  const probs = {};
  for (const [n, s] of Object.entries(scores)) probs[n] = s / total;
  return probs;
}

function distancesFor(answered) {
  const dist = {};
  for (const doll of dolls) {
    let sum = 0;
    for (const k in answered) sum += Math.abs(answered[k] - doll.vector[k]);
    dist[doll.name] = sum;
  }
  return dist;
}

// Highest probability-weighted variance across dolls = most discriminating.
function pickQuestion(probs, asked) {
  let bestQ = null, bestVar = -1;
  for (const q of ALL_KEYS) {
    if (asked.has(q)) continue;
    let mu = 0;
    for (const doll of dolls) mu += probs[doll.name] * doll.vector[q];
    let varSum = 0;
    for (const doll of dolls) {
      const diff = doll.vector[q] - mu;
      varSum += probs[doll.name] * diff * diff;
    }
    if (varSum > bestVar) { bestVar = varSum; bestQ = q; }
  }
  return bestQ;
}

function rankProbs(probs) {
  return Object.entries(probs).sort((a, b) => b[1] - a[1]);
}

const dollByName = Object.fromEntries(dolls.map(d => [d.name, d]));

/* ---------- state ---------- */

let state;
function freshState() {
  const probs = {};
  for (const d of dolls) probs[d.name] = 1 / dolls.length;
  return {
    asked: new Set(),
    answered: {},
    history: [],            // ordered list of asked keys for BACK
    probs,
    currentQ: null,
    round: 0,
  };
}

/* ---------- screens ---------- */

const screens = {
  intro: document.getElementById("screen-intro"),
  quiz: document.getElementById("screen-quiz"),
  result: document.getElementById("screen-result"),
};
function show(name) {
  for (const s of Object.values(screens)) s.classList.remove("is-active");
  screens[name].classList.add("is-active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ---------- quiz flow ---------- */

const el = {
  qNum: document.getElementById("q-num"),
  qTotal: document.getElementById("q-total"),
  statement: document.getElementById("statement-text"),
  confPct: document.getElementById("conf-pct"),
  confFill: document.getElementById("conf-fill"),
  contention: document.getElementById("contention-count"),
  back: document.getElementById("btn-back"),
};

// "Effective number of candidates" (inverse Simpson index): a smooth count of
// how many dolls are still meaningfully in the running. Starts near the full
// roster and collapses toward 1 as answers pile up. Deliberately reveals no
// names, so you can't steer toward a doll you like.
function effectiveCandidates(probs) {
  let sumSq = 0;
  for (const p of Object.values(probs)) sumSq += p * p;
  return Math.max(1, Math.round(1 / sumSq));
}

function shouldStop() {
  if (state.round >= MAX_QUESTIONS) return true;
  const ranked = rankProbs(state.probs);
  const top = ranked[0][1];
  const second = ranked[1] ? ranked[1][1] : 0;
  if (state.round > MIN_QUESTIONS && second > 0 && top / second >= LEAD_RATIO) return true;
  return false;
}

function nextQuestion() {
  if (state.round > 0 && shouldStop()) return finish();

  const q = pickQuestion(state.probs, state.asked);
  if (q === null) return finish();

  state.currentQ = q;
  state.round += 1;
  renderQuestion();
}

function renderQuestion() {
  el.qNum.textContent = String(state.round).padStart(2, "0");

  // Rough estimate of total length: between MIN and MAX, biased by progress.
  const ranked = rankProbs(state.probs);
  const top = ranked[0][1], second = ranked[1] ? ranked[1][1] : 0;
  el.qTotal.textContent = "~" + estimateTotal(top, second);

  el.statement.textContent = statements[state.currentQ];

  // Confidence = leading probability, scaled for feel (it starts at 1/N).
  const conf = Math.min(100, Math.round(top * 100));
  el.confPct.textContent = conf + "%";
  el.confFill.style.width = Math.max(2, conf) + "%";

  // Non-spoiler "narrowing" readout: how many dolls are still in contention.
  el.contention.textContent = effectiveCandidates(state.probs);

  el.back.disabled = state.history.length === 0;
}

function estimateTotal(top, second) {
  // Cheap heuristic just for display: closer to a lock => fewer remaining.
  if (state.round < MIN_QUESTIONS) return MIN_QUESTIONS + 6;
  const lead = second > 0 ? top / second : 99;
  if (lead >= LEAD_RATIO) return state.round;
  return Math.min(MAX_QUESTIONS, state.round + Math.ceil((LEAD_RATIO - lead) / 2));
}

function answer(value) {
  const q = state.currentQ;
  state.answered[q] = value;
  state.asked.add(q);
  state.history.push(q);
  state.probs = toProbs(distancesFor(state.answered));
  nextQuestion();
}

function goBack() {
  if (state.history.length === 0) return;
  const last = state.history.pop();
  delete state.answered[last];
  state.asked.delete(last);
  state.round -= 1;
  state.probs = Object.keys(state.answered).length
    ? toProbs(distancesFor(state.answered))
    : Object.fromEntries(dolls.map(d => [d.name, 1 / dolls.length]));
  state.currentQ = last;
  renderQuestion();
}

/* ---------- result ---------- */

function finish() {
  const ranked = rankProbs(state.probs);
  const [topName, topProb] = ranked[0];
  const doll = dollByName[topName];

  document.getElementById("result-img").src = doll.image;
  document.getElementById("result-img").alt = doll.name;
  document.getElementById("result-name").textContent = doll.name;
  document.getElementById("result-pct").textContent = Math.round(topProb * 100) + "%";
  document.getElementById("result-what").textContent =
    doll.whatShesLike || "No profile on record.";
  document.getElementById("result-isee").textContent =
    doll.iSeeYou || "The system has you pegged, even without words.";

  const list = document.getElementById("result-ranklist");
  list.innerHTML = "";
  const max = ranked[0][1] || 1;
  for (let i = 0; i < Math.min(5, ranked.length); i++) {
    const [name, p] = ranked[i];
    const li = document.createElement("li");
    li.className = "rank-item" + (i === 0 ? " is-top" : "");
    li.innerHTML = `
      <div class="rank-row"><span class="rank-name">${i + 1}. ${name}</span></div>
      <span class="rank-pct">${(p * 100).toFixed(1)}%</span>
      <div class="rank-track"><div class="rank-fill" style="width:0%"></div></div>`;
    list.appendChild(li);
    // animate fill after paint
    requestAnimationFrame(() => {
      li.querySelector(".rank-fill").style.width = (p / max * 100) + "%";
    });
  }

  show("result");
}

/* ---------- wiring ---------- */

function startQuiz() {
  state = freshState();
  show("quiz");
  nextQuestion();
}

document.getElementById("btn-begin").addEventListener("click", startQuiz);
document.getElementById("btn-restart").addEventListener("click", startQuiz);
document.getElementById("btn-restart-q").addEventListener("click", startQuiz);
document.getElementById("btn-back").addEventListener("click", goBack);

document.querySelectorAll(".ans").forEach(btn => {
  btn.addEventListener("click", () => {
    btn.classList.add("flash");
    setTimeout(() => btn.classList.remove("flash"), 320);
    answer(parseInt(btn.dataset.value, 10));
  });
});

// Keyboard: 1-4 to answer, Backspace to go back.
document.addEventListener("keydown", (e) => {
  if (!screens.quiz.classList.contains("is-active")) return;
  if (["1", "2", "3", "4"].includes(e.key)) {
    const btn = document.querySelector(`.ans[data-value="${e.key}"]`);
    if (btn) btn.click();
  } else if (e.key === "Backspace") {
    e.preventDefault();
    goBack();
  }
});

/* ---------- intro counts + butterfly ambiance ---------- */

// Optional count slots: null-safe so editing the intro copy can't break the page.
const introCount = document.getElementById("intro-count");
if (introCount) introCount.textContent = dolls.length;
const footCount = document.getElementById("foot-count");
if (footCount) footCount.textContent = dolls.length + " T-DOLLS INDEXED";

(function butterflies() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const field = document.getElementById("butterfly-field");
  function spawn() {
    const b = document.createElement("div");
    b.className = "bf-particle";
    const size = 14 + Math.random() * 22;
    b.style.width = size + "px";
    b.style.height = size + "px";
    b.style.left = Math.random() * 100 + "vw";
    // Travel within +/-30 deg of straight up. Horizontal drift uses vh so the
    // on-screen angle stays true (1vh == 1vw in pixels). Body leans into it.
    const deg = Math.random() * 60 - 30;
    const driftVh = Math.tan(deg * Math.PI / 180) * 115;
    b.style.setProperty("--drift", driftVh.toFixed(1) + "vh");
    b.style.setProperty("--tilt", (deg * 0.5).toFixed(1) + "deg");
    b.style.setProperty("--flap", (0.3 + Math.random() * 0.35).toFixed(2) + "s");
    const dur = 12 + Math.random() * 12;
    b.style.animationDuration = dur + "s";
    b.innerHTML = `<img src="assets/butterfly.png" alt="">`;
    field.appendChild(b);
    setTimeout(() => b.remove(), dur * 1000);
  }
  for (let i = 0; i < 4; i++) setTimeout(spawn, i * 2500);
  setInterval(spawn, 3800);
})();
