/* =====================================================================
   Guessr — logique de jeu
   Modèle : 1 daily gratuit par thème et par jour, parties illimitées en premium.
   Le daily est DÉTERMINISTE (même tirage pour tout le monde le même jour), ce qui
   rend les scores comparables et donc le partage intéressant.
===================================================================== */

const CONTENT = window.GUESSR_CONTENT || {};

const THEME_META = {
  sneakers: { name: "Sneakers", emoji: "👟" },
  montre:   { name: "Montres",  emoji: "⌚" },
  moto:     { name: "Motos",    emoji: "🏍️" },
  voiture:  { name: "Voitures", emoji: "🚗" },
};

const ROUNDS = 5;
const ROUND_TIME = 15;
const CHOICES_AT = 0.5;        // le QCM n'apparaît qu'à mi-temps
const MAX_PTS = 5000;
const MIN_PTS_CORRECT = 800;
const REVEAL_TIME = 10;
const TYPO_PENALTY = 300;
const N_CHOICES = 6;
const EPOCH = "2026-01-01";    // origine des numéros de puzzle

/* ------------------------------------------------------ utilitaires */

function todayStr(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function yesterdayStr() {
  const d = new Date(); d.setDate(d.getDate() - 1); return todayStr(d);
}
function puzzleNumber(dateStr) {
  return Math.round((new Date(dateStr + "T00:00:00") - new Date(EPOCH + "T00:00:00")) / 86400000) + 1;
}
function seedFrom(str) {
  let h = 1779033703 ^ str.length;
  for (let i = 0; i < str.length; i++) { h = Math.imul(h ^ str.charCodeAt(i), 3432918353); h = h << 13 | h >>> 19; }
  return h >>> 0;
}
function mulberry32(a) {
  return function () {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
function shuffleWith(rand, arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}
function shuffle(arr) { return shuffleWith(Math.random, arr); }

function norm(s) {
  return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]/g, "");
}
function levenshtein(a, b) {
  if (a === b) return 0;
  if (!a.length || !b.length) return Math.max(a.length, b.length);
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    prev = cur;
  }
  return prev[b.length];
}

/* Le contenu est généré automatiquement : impossible d'écrire des alias à la main
   pour 190 modèles. On accepte donc, en plus du nom complet :
     - le nom préfixé de la marque ("nike air jordan 1")
     - le nom privé de la marque ("countach" pour Lamborghini Countach)
     - tout suffixe de mots ("jordan 1" pour Air Jordan 1) — la marque n'est pas
       toujours le premier mot du nom, donc retirer le préfixe ne suffit pas.
*/
function acceptedForms(item) {
  const full = norm(item.name);
  const brand = norm(item.brand);
  const forms = new Set([full, norm(item.brand + " " + item.name)]);
  if (brand && full.startsWith(brand) && full.length > brand.length) forms.add(full.slice(brand.length));

  const tokens = item.name.split(/\s+/).filter(Boolean);
  for (let i = 1; i < tokens.length; i++) {
    const suffix = tokens.slice(i).join(" ");
    // un suffixe d'un seul mot doit rester distinctif ("911" oui, "1" non)
    if (tokens.length - i === 1 && norm(suffix).length < 3) continue;
    forms.add(norm(suffix));
  }
  return [...forms].filter(f => f && f.length >= 2);
}

const digitsOf = s => (s.match(/\d+/g) || []).join(".");

function guessMatches(guess, item) {
  const g = norm(guess);
  if (g.length < 2) return false;
  return acceptedForms(item).some(form => {
    // Les chiffres portent l'essentiel du sens dans un nom de modèle : une Air Jordan 1
    // n'est pas une 11, une 205 n'est pas une 208. On exige qu'ils soient exacts, et on
    // ne tolère les fautes de frappe que sur le reste.
    if (digitsOf(form) !== digitsOf(g)) return false;
    const tol = form.length <= 4 ? 0 : form.length <= 8 ? 1 : 2;
    return levenshtein(form, g) <= tol;
  });
}

/* ------------------------------------------------------ comptes (démo locale) */

function usersDB() { try { return JSON.parse(localStorage.getItem("guessr_users") || "{}"); } catch { return {}; } }
function saveUsers(db) { localStorage.setItem("guessr_users", JSON.stringify(db)); }
function toyHash(s) { // hachage jouet : démo locale, PAS de la vraie sécurité
  let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
  return h.toString(36);
}
function currentUser() { return localStorage.getItem("guessr_session"); }
function me() { return usersDB()[currentUser()]; }
function saveMe(u) { const db = usersDB(); db[currentUser()] = u; saveUsers(db); }

/* On arrive par un lien partagé : demander un compte avant d'avoir vu le jeu tuerait
   la seule boucle qui compte. On joue donc en invité par défaut, et créer un compte
   plus tard récupère la progression. */
const GUEST = "__invite__";
function ensureSession() {
  if (currentUser() && me()) return;
  const db = usersDB();
  if (!db[GUEST]) db[GUEST] = { pass: null, premium: false, themes: {}, guest: true };
  saveUsers(db);
  localStorage.setItem("guessr_session", GUEST);
}
function isGuest() { return currentUser() === GUEST; }
function displayName() { return isGuest() ? "Invité" : currentUser(); }
function themeState(u, themeId) {
  u.themes = u.themes || {};
  u.themes[themeId] = u.themes[themeId] || { best: 0, streak: 0, lastDaily: null, dailyDone: {} };
  return u.themes[themeId];
}

/* ------------------------------------------------------ sélection du contenu */

function itemsFor(themeId) { return CONTENT[themeId] || []; }

/* Un même modèle peut avoir plusieurs photos : on ne doit jamais proposer deux fois
   le même nom dans une partie ni dans un QCM. */
function dedupeByName(items) {
  const seen = new Set();
  return items.filter(i => { const k = norm(i.name); if (seen.has(k)) return false; seen.add(k); return true; });
}

/* `fame` = notoriété (nb de versions linguistiques Wikipédia pour moto/voiture).
   Le daily pioche dans les modèles les plus connus pour rester accessible ;
   le mode Expert ouvre tout le catalogue, y compris les modèles obscurs. */
function poolFor(themeId, expert) {
  const all = dedupeByName([...itemsFor(themeId)].sort((a, b) => (b.fame || 0) - (a.fame || 0)));
  if (expert) return all;
  // Plancher assez bas pour qu'un thème à faible catalogue garde un vrai palier :
  // un plancher de 20 sur 23 sneakers laissait passer les modèles pointus dans le daily.
  return all.slice(0, Math.max(12, Math.ceil(all.length * 0.6)));
}

function pickPhoto(themeId, item, rand) {
  const variants = itemsFor(themeId).filter(i => norm(i.name) === norm(item.name));
  return variants[Math.floor(rand() * variants.length)] || item;
}

/* ------------------------------------------------------ état de partie */

let game = null;
let rafId = null;

function startDaily(themeId) {
  const date = todayStr();
  const rand = mulberry32(seedFrom(themeId + "|" + date));
  const pool = poolFor(themeId, false);
  if (pool.length < ROUNDS) { alert("Pas assez de contenu pour ce thème."); return; }
  const picks = shuffleWith(rand, pool).slice(0, ROUNDS).map(it => pickPhoto(themeId, it, rand));
  launch(themeId, picks, { mode: "daily", date, rand });
}

function startUnlimited(themeId, expert) {
  const pool = poolFor(themeId, expert);
  if (pool.length < ROUNDS) { alert("Pas assez de contenu pour ce thème."); return; }
  const picks = shuffle(pool).slice(0, ROUNDS).map(it => pickPhoto(themeId, it, Math.random));
  launch(themeId, picks, { mode: "unlimited", expert });
}

function launch(themeId, picks, opts) {
  game = {
    themeId, order: picks, round: 0, score: 0, results: [],
    mode: opts.mode, date: opts.date || todayStr(), expert: !!opts.expert,
    origins: picks.map(() => {
      const r = opts.rand || Math.random;
      return [30 + r() * 40, 35 + r() * 30];
    }),
  };
  const m = THEME_META[themeId];
  document.getElementById("hud-theme").textContent =
    `${m.emoji} ${m.name}${opts.mode === "daily" ? " · Daily #" + puzzleNumber(game.date) : opts.expert ? " · Expert" : ""}`;
  show("screen-game");
  startRound();
}

function startRound() {
  const s = game.order[game.round];
  game.roundStart = performance.now();
  game.answered = false;
  game.penalty = 0;
  game.choicesShown = false;

  document.getElementById("round-label").textContent = `${game.round + 1} / ${ROUNDS}`;
  document.getElementById("score-value").textContent = game.score.toLocaleString("fr-FR");
  document.getElementById("round-result").innerHTML = "";
  document.getElementById("guess-row").style.display = "flex";
  const input = document.getElementById("guess-input");
  input.value = ""; input.disabled = false;
  setTimeout(() => input.focus(), 50);

  const img = document.getElementById("photo");
  img.src = `images/${game.themeId}/${s.id}.jpg`;
  img.style.transform = "scale(3.5)";
  img.style.filter = "blur(7px) saturate(.5)";
  img.style.transformOrigin = `${game.origins[game.round][0]}% ${game.origins[game.round][1]}%`;

  const choicesEl = document.getElementById("choices");
  choicesEl.classList.add("hidden-choices");
  choicesEl.innerHTML = "";
  buildChoices(s).forEach(choice => {
    const btn = document.createElement("button");
    btn.className = "choice";
    btn.textContent = choice.name;
    btn.onclick = () => answerChoice(choice, btn);
    choicesEl.appendChild(btn);
  });

  cancelAnimationFrame(rafId);
  tick();
}

/* Leurres crédibles : même marque d'abord, puis notoriété proche — sinon proposer
   une Porsche 911 face à un modèle obscur donnerait la réponse.
   Les leurres viennent du MÊME pool que la question : au daily, proposer Air Jordan 2
   et 8 face à une Air Jordan 1 transformerait le QCM en tirage au sort. */
function buildChoices(answer) {
  const pool = poolFor(game.themeId, game.expert).filter(i => norm(i.name) !== norm(answer.name));
  const sameBrand = shuffle(pool.filter(i => i.brand === answer.brand));
  const byFame = pool
    .filter(i => i.brand !== answer.brand)
    .sort((a, b) => Math.abs((a.fame || 0) - (answer.fame || 0)) - Math.abs((b.fame || 0) - (answer.fame || 0)));
  const decoys = [...sameBrand.slice(0, 2), ...byFame].slice(0, N_CHOICES - 1);
  return shuffle([answer, ...decoys]);
}

function tick() {
  const elapsed = (performance.now() - game.roundStart) / 1000;
  const remaining = Math.max(0, ROUND_TIME - elapsed);

  const reveal = Math.min(1, elapsed / REVEAL_TIME);
  const img = document.getElementById("photo");
  img.style.transform = `scale(${(3.5 - 2.5 * reveal).toFixed(3)})`;
  img.style.filter = `blur(${(7 * (1 - Math.min(1, elapsed / 4))).toFixed(1)}px) saturate(${(0.5 + 0.5 * reveal).toFixed(2)})`;

  const timerEl = document.getElementById("timer-value");
  timerEl.textContent = remaining.toFixed(1);
  timerEl.classList.toggle("low", remaining <= 5);
  document.getElementById("points-preview").textContent = currentPoints(elapsed).toLocaleString("fr-FR");
  document.getElementById("timebar").style.transform = `scaleX(${remaining / ROUND_TIME})`;

  const choicesDelay = ROUND_TIME * CHOICES_AT;
  const hint = document.getElementById("guess-hint");
  if (!game.choicesShown && elapsed >= choicesDelay) {
    game.choicesShown = true;
    document.getElementById("choices").classList.remove("hidden-choices");
  }
  if (game.choicesShown) {
    hint.innerHTML = game.penalty ? `<span class="penalty-pop">−${game.penalty} pts de pénalité</span>` : "QCM disponible — la saisie rapporte plus.";
  } else {
    hint.innerHTML = `Saisie libre — le QCM apparaît dans <b>${(choicesDelay - elapsed).toFixed(1)}s</b>`
      + (game.penalty ? ` · <span class="penalty-pop">−${game.penalty} pts</span>` : "");
  }

  if (remaining <= 0 && !game.answered) { timeoutRound(); return; }
  if (!game.answered) rafId = requestAnimationFrame(tick);
}

function currentPoints(elapsed) {
  const f = Math.max(0, 1 - elapsed / ROUND_TIME);
  return Math.max(0, Math.round(MIN_PTS_CORRECT + (MAX_PTS - MIN_PTS_CORRECT) * f) - game.penalty);
}

function submitTyped() {
  if (!game || game.answered) return;
  const input = document.getElementById("guess-input");
  if (norm(input.value).length < 2) return;
  if (guessMatches(input.value, game.order[game.round])) {
    finishRound(true, "typed");
  } else {
    game.penalty += TYPO_PENALTY;
    input.classList.remove("shake"); void input.offsetWidth; input.classList.add("shake");
    input.select();
  }
}

function answerChoice(choice, btn) {
  if (game.answered) return;
  markChoices(btn);
  finishRound(norm(choice.name) === norm(game.order[game.round].name), "choice");
}

function markChoices(clickedBtn) {
  const s = game.order[game.round];
  document.querySelectorAll(".choice").forEach(b => {
    b.disabled = true;
    if (norm(b.textContent) === norm(s.name)) b.classList.add("correct");
    else if (b === clickedBtn) b.classList.add("wrong");
    else b.classList.add("dim");
  });
}

function finishRound(correct, mode) {
  game.answered = true;
  cancelAnimationFrame(rafId);
  const s = game.order[game.round];
  const elapsed = (performance.now() - game.roundStart) / 1000;
  const pts = correct ? currentPoints(elapsed) : 0;
  game.score += pts;
  game.results.push({ item: s, pts, time: elapsed, correct, mode });

  document.getElementById("guess-input").disabled = true;
  document.getElementById("choices").classList.remove("hidden-choices");
  if (mode !== "choice") markChoices(null);
  const img = document.getElementById("photo");
  img.style.transform = "scale(1)"; img.style.filter = "none";
  document.getElementById("guess-hint").innerHTML = "";
  document.getElementById("score-value").textContent = game.score.toLocaleString("fr-FR");

  showRoundResult(correct
    ? (mode === "typed" ? `Trouvé à la saisie en ${elapsed.toFixed(1)}s 🎯` : `Bien joué ! ${elapsed.toFixed(1)}s`)
    : `Raté… c'était « ${s.name} »`, pts);
}

function timeoutRound() {
  game.answered = true;
  const s = game.order[game.round];
  game.results.push({ item: s, pts: 0, time: ROUND_TIME, correct: false, mode: "timeout" });
  document.getElementById("guess-input").disabled = true;
  document.getElementById("choices").classList.remove("hidden-choices");
  markChoices(null);
  const img = document.getElementById("photo");
  img.style.transform = "scale(1)"; img.style.filter = "none";
  document.getElementById("guess-hint").innerHTML = "";
  showRoundResult(`Temps écoulé ! C'était « ${s.name} »`, 0);
}

function showRoundResult(label, pts) {
  const last = game.round === ROUNDS - 1;
  document.getElementById("round-result").innerHTML = `
    <div class="pts ${pts === 0 ? "zero" : ""}">${pts > 0 ? "+" : ""}${pts.toLocaleString("fr-FR")} pts</div>
    <div class="label">${label}</div>
    <button class="next-btn" onclick="nextRound()">${last ? "Voir le score final" : "Manche suivante →"}</button>`;
  document.querySelector(".next-btn").focus();
}

function nextRound() {
  game.round++;
  if (game.round >= ROUNDS) endGame(); else startRound();
}

/* ------------------------------------------------------ fin de partie */

function squareFor(r) {
  if (!r.correct) return "⬜";
  return r.mode === "typed" ? "🟩" : "🟨";
}

function shareText() {
  const m = THEME_META[game.themeId];
  const grid = game.results.map(squareFor).join("");
  const head = game.mode === "daily"
    ? `Guessr ${m.emoji} ${m.name} #${puzzleNumber(game.date)} — ${game.score.toLocaleString("fr-FR")} pts`
    : `Guessr ${m.emoji} ${m.name}${game.expert ? " (Expert)" : ""} — ${game.score.toLocaleString("fr-FR")} pts`;
  const st = themeState(me(), game.themeId);
  const streak = game.mode === "daily" && st.streak > 1 ? `  🔥${st.streak}` : "";
  return `${head}\n${grid}${streak}\n${location.origin + location.pathname}`;
}

function copyShare() {
  const txt = shareText();
  const done = () => {
    const b = document.getElementById("share-btn");
    b.textContent = "Copié ✓"; setTimeout(() => (b.textContent = "Partager mon score"), 1800);
  };
  if (navigator.clipboard) navigator.clipboard.writeText(txt).then(done, done);
  else {
    const ta = document.createElement("textarea");
    ta.value = txt; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch {}
    ta.remove(); done();
  }
}

function endGame() {
  const u = me();
  const st = themeState(u, game.themeId);

  if (game.mode === "daily") {
    // streak : +1 si le daily de la veille a été fait, sinon on repart à 1
    if (!st.dailyDone[game.date]) {
      st.streak = st.lastDaily === yesterdayStr() ? (st.streak || 0) + 1 : 1;
      st.lastDaily = game.date;
      st.dailyDone[game.date] = game.score;
    }
  }
  const isRecord = game.score > (st.best || 0);
  if (isRecord) st.best = game.score;
  saveMe(u);

  show("screen-end");
  const m = THEME_META[game.themeId];
  document.getElementById("end-theme").textContent =
    game.mode === "daily" ? `${m.emoji} ${m.name} · Daily #${puzzleNumber(game.date)}` : `${m.emoji} ${m.name}${game.expert ? " · Expert" : ""}`;
  document.getElementById("final-score").textContent = game.score.toLocaleString("fr-FR");
  document.getElementById("share-grid").textContent = game.results.map(squareFor).join(" ");
  document.getElementById("new-record").style.display = isRecord && game.score > 0 ? "block" : "none";
  document.getElementById("streak-line").textContent =
    game.mode === "daily" && st.streak > 1 ? `🔥 Série de ${st.streak} jours` : "";

  const modeLabel = { typed: "saisie", choice: "QCM", timeout: "temps écoulé" };
  document.getElementById("recap").innerHTML = game.results.map(r => `
    <div class="recap-row">
      <div class="recap-left">
        <img src="images/${game.themeId}/${r.item.id}.jpg" alt="">
        <div>
          <div class="name">${r.item.name}</div>
          <div class="sub">${r.item.brand} · ${r.correct ? r.time.toFixed(1) + "s · " + modeLabel[r.mode] : modeLabel[r.mode]}</div>
        </div>
      </div>
      <div class="rpts ${r.pts === 0 ? "zero" : ""}">${r.pts.toLocaleString("fr-FR")}</div>
    </div>`).join("");

  // Le rejeu est le moment naturel pour proposer le premium.
  const again = document.getElementById("play-again");
  if (me().premium) {
    again.textContent = "Rejouer";
    again.onclick = () => startUnlimited(game.themeId, game.expert);
  } else {
    again.textContent = "Rejouer — Premium";
    again.onclick = () => openPaywall(game.themeId);
  }
}

/* ------------------------------------------------------ écrans */

function show(id) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}

function goHome() {
  cancelAnimationFrame(rafId);
  ensureSession();
  renderHome();
  show("screen-home");
}

function renderHome() {
  const u = me();
  document.getElementById("chip-user").textContent = displayName();
  document.getElementById("chip-prem").textContent = u.premium ? "· ✨ Premium" : "";
  document.getElementById("chip-action").textContent = isGuest() ? "créer un compte" : "déconnexion";
  document.getElementById("chip-action").onclick = isGuest() ? showAuth : logout;
  const date = todayStr();
  const wrap = document.getElementById("themes");
  wrap.innerHTML = "";

  Object.entries(THEME_META).forEach(([tid, meta]) => {
    const n = dedupeByName(itemsFor(tid)).length;
    if (!n) return;
    const st = themeState(u, tid);
    const doneToday = st.dailyDone[date] !== undefined;
    const card = document.createElement("div");
    card.className = "theme-card";
    card.innerHTML = `
      <div class="theme-head">
        <div class="theme-emoji">${meta.emoji}</div>
        <div>
          <div class="theme-name">${meta.name}</div>
          <div class="theme-desc">${n} modèles${st.best ? " · record " + st.best.toLocaleString("fr-FR") : ""}${st.streak > 1 ? " · 🔥" + st.streak : ""}</div>
        </div>
      </div>
      <div class="theme-actions">
        ${doneToday
          ? `<div class="daily-done">Daily #${puzzleNumber(date)} fait ✓ <b>${st.dailyDone[date].toLocaleString("fr-FR")} pts</b></div>`
          : `<button class="btn btn-daily">Daily #${puzzleNumber(date)} · gratuit</button>`}
        <button class="btn ${u.premium ? "secondary" : "locked"} btn-unlimited">
          ${u.premium ? "Partie illimitée" : "🔒 Illimité — Premium"}
        </button>
        ${u.premium ? `<button class="btn secondary btn-expert">Mode Expert</button>` : ""}
      </div>`;
    const daily = card.querySelector(".btn-daily");
    if (daily) daily.onclick = () => startDaily(tid);
    card.querySelector(".btn-unlimited").onclick = () => u.premium ? startUnlimited(tid, false) : openPaywall(tid);
    const exp = card.querySelector(".btn-expert");
    if (exp) exp.onclick = () => startUnlimited(tid, true);
    wrap.appendChild(card);
  });
}

/* ------------------------------------------------------ auth */

function authFields() {
  const user = document.getElementById("auth-user").value.trim();
  const pass = document.getElementById("auth-pass").value;
  const err = document.getElementById("auth-error");
  err.textContent = "";
  if (user.length < 3) { err.textContent = "Pseudo : 3 caractères minimum."; return null; }
  if (pass.length < 4) { err.textContent = "Mot de passe : 4 caractères minimum."; return null; }
  return { user, pass, err };
}
function showAuth() { document.getElementById("auth-error").textContent = ""; show("screen-auth"); }

function signup() {
  const f = authFields(); if (!f) return;
  const db = usersDB();
  if (db[f.user]) { f.err.textContent = "Ce pseudo existe déjà — connecte-toi."; return; }
  // on récupère la progression faite en invité plutôt que de la jeter
  const carried = (db[GUEST] && db[GUEST].themes) || {};
  db[f.user] = { pass: toyHash(f.pass), premium: !!(db[GUEST] && db[GUEST].premium), themes: carried };
  if (db[GUEST]) db[GUEST] = { pass: null, premium: false, themes: {}, guest: true };
  saveUsers(db);
  localStorage.setItem("guessr_session", f.user);
  goHome();
}
function login() {
  const f = authFields(); if (!f) return;
  const db = usersDB();
  if (!db[f.user]) { f.err.textContent = "Compte inconnu — crée un compte."; return; }
  if (db[f.user].pass !== toyHash(f.pass)) { f.err.textContent = "Mot de passe incorrect."; return; }
  localStorage.setItem("guessr_session", f.user);
  goHome();
}
function logout() {
  localStorage.removeItem("guessr_session");
  document.getElementById("auth-pass").value = "";
  goHome();   // on retombe en invité : on ne bloque jamais l'accès au jeu
}

/* ------------------------------------------------------ paywall (fictif) */

function openPaywall() {
  document.getElementById("pay-error").textContent = "";
  document.getElementById("paywall").classList.add("open");
}
function closePaywall() { document.getElementById("paywall").classList.remove("open"); }

/* Le jeu est hébergé publiquement : un formulaire de carte a la même forme qu'une page
   de phishing. On met donc la carte de test à un clic, pour que personne n'ait de raison
   de saisir de vrais chiffres. 4242… est le numéro de test universel (Stripe), invalide
   pour un vrai paiement. */
function fillTestCard() {
  document.getElementById("pay-name").value = "CARTE DE TEST";
  document.getElementById("pay-card").value = "4242 4242 4242 4242";
  document.getElementById("pay-exp").value = "12/30";
  document.getElementById("pay-cvc").value = "123";
  document.getElementById("pay-error").textContent = "";
}

function pay() {
  const name = document.getElementById("pay-name").value.trim();
  const card = document.getElementById("pay-card").value.replace(/[\s-]/g, "");
  const exp = document.getElementById("pay-exp").value.trim();
  const cvc = document.getElementById("pay-cvc").value.trim();
  const err = document.getElementById("pay-error");
  err.textContent = "";
  if (name.length < 2) { err.textContent = "Nom manquant."; return; }
  if (!/^\d{13,19}$/.test(card)) { err.textContent = "Numéro de carte invalide (13 à 19 chiffres)."; return; }
  const m = exp.match(/^(\d{2})\/(\d{2})$/);
  if (!m || +m[1] < 1 || +m[1] > 12) { err.textContent = "Expiration au format MM/AA."; return; }
  const now = new Date();
  if (+("20" + m[2]) * 100 + +m[1] < now.getFullYear() * 100 + now.getMonth() + 1) { err.textContent = "Carte expirée."; return; }
  if (!/^\d{3,4}$/.test(cvc)) { err.textContent = "CVC invalide."; return; }
  const u = me(); u.premium = true; saveMe(u);   // démo : aucun échange réseau
  closePaywall();
  if (document.getElementById("screen-end").classList.contains("active")) endGame();
  else goHome();
}

/* ------------------------------------------------------ crédits images */

function openCredits() {
  const wrap = document.getElementById("credits-list");
  const rows = [];
  Object.entries(CONTENT).forEach(([tid, items]) => {
    items.forEach(i => {
      if (!i.credit) return;
      rows.push(`<li><a href="${i.credit.source}" target="_blank" rel="noopener">${i.name}</a> — ${i.credit.author} (${i.credit.license})</li>`);
    });
  });
  wrap.innerHTML = `<ul>${rows.join("")}</ul>`;
  document.getElementById("credits").classList.add("open");
}
function closeCredits() { document.getElementById("credits").classList.remove("open"); }

/* ------------------------------------------------------ init */

document.addEventListener("keydown", e => {
  if (e.key === "Enter" && document.getElementById("screen-game").classList.contains("active")
      && document.activeElement === document.getElementById("guess-input")) submitTyped();
  if (e.key === "Escape") { closePaywall(); closeCredits(); }
});

goHome();
