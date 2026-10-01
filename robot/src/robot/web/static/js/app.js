// Screens: home, play, tasks (pick a task to record), record, training, run (running a policy).
// The record and run screens follow the robot's mode; the rest are chosen with the remote.

import { get, post } from "./api.js";
import { ensureFocus, focusFirst, install } from "./nav.js";

let chosen = "home";
let shown = null;
let status = null;
let cameras = [];
let tasksJson = "";
let shownError = null;
let armedDelete = null;

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "onclick") node.onclick = value;
    else node.setAttribute(key, value);
  }
  node.append(...children);
  return node;
}

function screenFor(s) {
  if (s?.mode === "record") return "record";
  if (s?.mode === "run") return "run";
  return chosen;
}

// Only the visible screen streams its cameras.
function syncStreams() {
  for (const img of document.querySelectorAll(".cameras img")) {
    const active = img.closest(".screen").id === shown;
    const src = active ? img.dataset.src : "";
    if (img.getAttribute("src") !== src) img.src = src;
  }
}

function show(name) {
  if (name === shown) return;
  shown = name;
  for (const section of document.querySelectorAll(".screen")) {
    section.classList.toggle("active", section.id === name);
  }
  syncStreams();
  if (name === "tasks" || name === "training") {
    tasksJson = "";
    refreshTasks();
  }
  focusFirst($(name));
}

function goto(name) {
  if (name === "play") post("/api/play").catch(showError);
  chosen = name;
  show(screenFor(status));
}

function back() {
  const current = screenFor(status);
  if (current === "record" || current === "run") {
    post("/api/press", { action: "stop" }).catch(showError);
    return true;
  }
  if (current !== "home") {
    goto("home");
    return true;
  }
  return false;
}

function showError(error) {
  const text = error.message || String(error);
  if (text === shownError) return;
  shownError = text;
  $("error-text").textContent = text;
  $("error").hidden = false;
}

function hideError() {
  $("error").hidden = true;
}

function setupCameras(names) {
  cameras = names;
  for (const box of document.querySelectorAll(".cameras")) {
    box.replaceChildren(
      ...names.map((name) => el("img", { alt: name, "data-src": `/stream/${name}.mjpg` })),
    );
  }
  syncStreams();
}

const PHASES = {
  starting: () => "Starting",
  countdown: (s) => `Recording starts in ${Math.ceil(s.seconds_left)}`,
  recording: (s) => `Recording ${Math.ceil(s.seconds_left)}`,
  reset: (s) => `Reset the scene ${Math.ceil(s.seconds_left)}`,
  saving: () => "Saving episode",
};

function renderRecord(s) {
  const banner = $("record-banner");
  banner.textContent = (PHASES[s.phase] || PHASES.starting)(s);
  banner.className = `banner ${s.phase}`;
  $("record-bar").style.width = `${Math.min(100, (100 * s.episodes) / s.target)}%`;
  $("record-count").textContent = `${s.task.name}: ${s.episodes} of ${s.target} episodes`;
}

function renderRun(s) {
  $("run-banner").textContent =
    s.phase === "loading" ? `Loading policy: ${s.task.name}` : `Running: ${s.task.name}`;
}

function renderHeader(s) {
  const labels = { play: "Play", record: "Record", run: "Run", starting: "Starting" };
  $("mode-chip").textContent = s.connected ? labels[s.mode] || s.mode : "Robot not connected";
  const storage = $("storage");
  storage.textContent = s.storage.low
    ? `Low on space: ${s.storage.free_gb} GB free`
    : `${s.storage.free_gb} GB free`;
  storage.classList.toggle("low", s.storage.low);
  if (s.error) showError(new Error(s.error));
  else if (shownError) {
    shownError = null;
    hideError();
  }
}

async function poll() {
  try {
    status = await get("/api/status");
    if (cameras.join() !== status.cameras.join()) setupCameras(status.cameras);
    renderHeader(status);
    show(screenFor(status));
    if (status.mode === "record") renderRecord(status);
    if (status.mode === "run") renderRun(status);
  } catch {
    $("mode-chip").textContent = "Can't reach the robot";
  }
  ensureFocus();
}

function trainingLabel(t) {
  if (!t) return "";
  return {
    sending: "Sending",
    queued: "Waiting to train",
    training: `Training ${t.percent || 0}%`,
    done: "Trained",
    failed: `Training failed: ${t.error || "unknown error"}`,
  }[t.state];
}

function button(key, label, fn) {
  return el("button", { "data-key": key, onclick: () => fn().then(refreshTasks).catch(showError) }, label);
}

function deleteButton(task) {
  const key = `${task.slug}:delete`;
  const armed = armedDelete === task.slug;
  return el("button", {
    "data-key": key,
    class: armed ? "danger" : "",
    onclick: () => {
      if (!armed) {
        armedDelete = task.slug;
        setTimeout(() => { if (armedDelete === task.slug) armedDelete = null; renderLists(); }, 5000);
        renderLists();
        return;
      }
      armedDelete = null;
      post(`/api/tasks/${task.slug}/delete-recordings`).then(refreshTasks).catch(showError);
    },
  }, armed ? "Press again to delete" : "Delete recordings");
}

function renderTaskList(tasks) {
  $("task-list").replaceChildren(
    ...tasks
      .filter((t) => t.has_data || t.episodes === 0)
      .map((t) =>
        el("li", {},
          el("span", { class: "name" }, t.name),
          el("span", { class: "meta" }, `${t.episodes} of ${t.target} episodes`),
          button(`${t.slug}:record`, "Record more", () => post(`/api/tasks/${t.slug}/record`)),
        ),
      ),
  );
}

function renderTrainingList(tasks, trainingEnabled) {
  $("training-list").replaceChildren(
    ...tasks.map((t) => {
      const state = t.training?.state;
      const busy = ["sending", "queued", "training"].includes(state);
      const canSend = t.has_data && !busy &&
        (t.episodes > t.submitted_episodes || (state === "failed" && t.episodes > 0));
      const buttons = [];
      if (trainingEnabled && canSend) {
        buttons.push(button(`${t.slug}:send`, "Send to training computer",
          () => post(`/api/tasks/${t.slug}/submit`)));
      }
      if (t.has_policy) {
        buttons.push(button(`${t.slug}:run`, "Run", () => post(`/api/tasks/${t.slug}/run`)));
      }
      if (t.can_delete) buttons.push(deleteButton(t));
      return el("li", {},
        el("span", { class: "name" }, t.name),
        el("span", { class: "meta" }, t.has_data ? `${t.episodes} episodes` : "Recordings deleted"),
        el("span", { class: "meta" }, trainingLabel(t.training)),
        ...buttons,
      );
    }),
  );
}

// Re-render while keeping focus on the same button.
function renderLists() {
  if (!tasksJson) return;
  const { tasks, trainer_error } = JSON.parse(tasksJson);
  const focused = document.activeElement?.dataset?.key;
  renderTaskList(tasks);
  renderTrainingList(tasks, status?.training_enabled);
  $("trainer-error").hidden = !trainer_error;
  $("trainer-error").textContent = trainer_error
    ? `Can't reach the training computer: ${trainer_error}`
    : "";
  if (focused) document.querySelector(`[data-key="${focused}"]`)?.focus();
  ensureFocus();
}

async function refreshTasks() {
  if (shown !== "tasks" && shown !== "training") return;
  try {
    const json = JSON.stringify(await get("/api/tasks"));
    if (json === tasksJson) return;
    tasksJson = json;
    renderLists();
  } catch {
    // The header already shows when the robot can't be reached.
  }
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("button");
  if (!target) return;
  if (target.dataset.goto) goto(target.dataset.goto);
  if (target.dataset.press) post("/api/press", { action: target.dataset.press }).catch(showError);
  if (target.dataset.action === "dismiss") {
    hideError();
    post("/api/error/clear").catch(() => {});
  }
  if (target.dataset.action === "reconnect") {
    hideError();
    shownError = null;
    post("/api/reconnect").catch(showError);
  }
});

$("new-task").addEventListener("submit", (event) => {
  event.preventDefault();
  const name = $("task-name").value.trim();
  if (!name) return;
  post("/api/tasks", { name })
    .then(() => { $("task-name").value = ""; })
    .catch(showError);
});

install(back);
poll();
setInterval(poll, 500);
setInterval(refreshTasks, 3000);
