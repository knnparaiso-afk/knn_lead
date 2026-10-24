const config = JSON.parse(document.getElementById("experience-config").textContent);
const $ = (id) => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const options = $("question-options");
let current, pending, failedAction, busy = false, graphic = null, lightMode = false;
let previewPosition = 0, graphicsPromise = null, selectedChoice = null;

async function request(url, data) {
  const response = await fetch(url, {
    method: data ? "POST" : "GET", credentials: "same-origin",
    headers: data ? { "Content-Type": "application/json", "X-CSRFToken": csrf } : {},
    body: data ? JSON.stringify(data) : undefined,
  });
  const type = response.headers.get("content-type") || "";
  const body = type.includes("application/json") ? await response.json() : null;
  if (!response.ok) throw new Error(body?.message || "Não foi possível confirmar sua resposta. Confira a conexão e tente novamente.");
  return body;
}

function setLightMode(message) {
  lightMode = true;
  graphic?.dispose();
  graphic = null;
  $("game-canvas").hidden = true;
  $("scene-loading").hidden = true;
  $("light-scene").hidden = false;
  $("mode-toggle").textContent = "Modo leve ativo";
  $("mode-toggle").disabled = true;
  if (message) $("mode-toggle").title = message;
}
$("mode-toggle").addEventListener("click", () => setLightMode("Você pode concluir os mesmos desafios neste modo."));
$("game-canvas").addEventListener("webglcontextlost", () => {
  setLightMode("O cenário foi interrompido. Seus desafios continuam disponíveis.");
});

async function showGraphics(question) {
  if (lightMode) return;
  if (!graphicsPromise) {
    graphicsPromise = import("./scene.js").then((module) => module.createAdventure(
      $("game-canvas"),
      (choice) => options.querySelectorAll("button")[choice]?.click(),
    ));
    graphicsPromise.then((controller) => { if (lightMode) controller.dispose(); }).catch(() => {});
  }
  try {
    const controller = await Promise.race([
      graphicsPromise,
      new Promise((_, reject) => setTimeout(() => reject(new Error("Tempo de carregamento excedido")), 20000)),
    ]);
    if (lightMode) { controller.dispose(); return; }
    graphic = controller;
    if (current?.question?.id !== question.id) return;
    await controller.show(question);
    if (current?.question?.id === question.id) $("game-canvas").dataset.scene = question.scene;
    $("scene-loading").hidden = true;
  } catch (error) {
    console.warn("Experiência em modo leve:", error.message, error.innerError?.stack || error.stack);
    setLightMode(error.message);
  }
}

function clearError() { $("game-error").hidden = true; $("retry-request").hidden = true; }
function showError(error, action) {
  $("game-error").textContent = error.message;
  $("game-error").hidden = false;
  $("retry-request").hidden = false;
  failedAction = action;
}

function previewState() {
  return { answered: previewPosition, total: config.questions.length,
    completed: previewPosition === config.questions.length,
    question: config.questions[previewPosition] ? { ...config.questions[previewPosition], position: previewPosition } : null };
}

function render(state) {
  current = state;
  clearError();
  $("answer-feedback").hidden = true;
  $("next-question").hidden = true;
  $("progress-label").textContent = state.answered + " de " + state.total + " concluídos";
  $("game-progress").setAttribute("aria-valuenow", state.answered);
  $("game-progress").firstElementChild.style.width = (state.answered / state.total * 100) + "%";
  if (state.expired) {
    options.replaceChildren();
    $("question-title").textContent = "Vamos começar de novo?";
    $("question-prompt").textContent = "Esta sessão expirou. Volte à página da campanha para iniciar outra experiência.";
    setLightMode();
    return;
  }
  if (state.completed) {
    if (config.preview) {
      document.querySelector(".game-layout").hidden = true;
      $("preview-complete").hidden = false;
      $("preview-complete").scrollIntoView({ behavior: "smooth", block: "center" });
      graphic?.dispose();
    } else {
      window.location.assign(config.resultUrl);
    }
    return;
  }
  const question = state.question;
  $("scene-label").textContent = question.scene === "cafe" ? "PRIMEIRA PARADA / CAFÉ" : "SEGUNDA PARADA / ENCONTRO";
  $("stage-location").textContent = question.scene === "cafe" ? "01 / CAFÉ" : "02 / ENCONTRO";
  $("light-scene").querySelector(".light-icon").textContent = question.scene === "cafe" ? "☕" : "✉";
  $("speaker-label").textContent = question.speaker.toUpperCase() + " · " + question.skill.toUpperCase();
  $("question-title").textContent = question.title;
  $("question-prompt").textContent = question.prompt;
  options.replaceChildren();
  question.options.forEach((text, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "answer-option";
    const label = document.createElement("span");
    label.textContent = String.fromCharCode(65 + index);
    button.append(label, document.createTextNode(text));
    button.addEventListener("click", () => choose(index));
    options.append(button);
  });
  if (state.answered > 0) $("question-title").focus({ preventScroll: true });
  void showGraphics(question);
}

async function choose(choice) {
  if (busy || !current?.question) return;
  busy = true;
  selectedChoice = choice;
  clearError();
  const position = current.question.position;
  const buttons = [...options.querySelectorAll("button")];
  buttons.forEach((button, index) => { button.disabled = true; button.classList.toggle("selected", index === choice); });
  try {
    let response;
    if (config.preview) {
      const question = config.questions[position];
      previewPosition = position + 1;
      response = { correct: choice === question.correct, explanation: question.explanation, state: previewState() };
    } else {
      response = await request(config.answerUrl, { position, choice });
    }
    pending = response.state;
    const feedback = $("answer-feedback");
    const title = document.createElement("strong");
    title.textContent = response.correct ? "Boa! Vamos continuar." : "Uma expressão nova para levar com você.";
    feedback.replaceChildren(title, document.createTextNode(response.explanation));
    feedback.hidden = false;
    $("next-question").hidden = false;
    $("next-question").textContent = pending.completed ? "Concluir minha experiência ↗" : "Próximo desafio →";
    graphic?.react(response.correct);
    $("next-question").focus({ preventScroll: true });
  } catch (error) {
    // Keep the original choice on retry; the server preserves the first answer.
    showError(error, () => choose(selectedChoice));
  } finally {
    busy = false;
  }
}

$("next-question").addEventListener("click", () => { if (pending) render(pending); });
$("retry-request").addEventListener("click", () => { if (!busy) failedAction?.(); });
async function begin() {
  try { render(config.preview ? previewState() : await request(config.stateUrl)); }
  catch (error) { showError(error, begin); $("scene-loading").hidden = true; }
}
window.addEventListener("pagehide", () => graphic?.dispose(), { once: true });
window.addEventListener("pageshow", (event) => { if (event.persisted) window.location.reload(); });
void begin();
