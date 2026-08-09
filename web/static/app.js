const api = {
  async state() {
    const res = await fetch("/api/state", { cache: "no-store" });
    return res.json();
  },
  async action(payload) {
    const res = await fetch("/api/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return res.json();
  },
};

const keyMap = {
  Digit1: { action: "select", ball: 1 },
  Digit2: { action: "select", ball: 2 },
  Digit3: { action: "select", ball: 3 },
  Digit4: { action: "select", ball: 4 },
  Digit5: { action: "select", ball: 5 },
  Digit6: { action: "select", ball: 6 },
  Digit7: { action: "select", ball: 7 },
  Digit8: { action: "select", ball: 8 },
  Digit9: { action: "select", ball: 9 },
  Digit0: { action: "select", ball: 10 },
  Numpad1: { action: "select", ball: 1 },
  Numpad2: { action: "select", ball: 2 },
  Numpad3: { action: "select", ball: 3 },
  Numpad4: { action: "select", ball: 4 },
  Numpad5: { action: "select", ball: 5 },
  Numpad6: { action: "select", ball: 6 },
  Numpad7: { action: "select", ball: 7 },
  Numpad8: { action: "select", ball: 8 },
  Numpad9: { action: "select", ball: 9 },
  Numpad0: { action: "select", ball: 10 },
  NumpadAdd: { action: "advance" },
  Equal: { action: "advance" },
  NumpadSubtract: { action: "undo" },
  Minus: { action: "undo" },
  Enter: { action: "toggle_timer" },
  NumpadEnter: { action: "toggle_timer" },
};

let currentState = null;
let finishDialogOpen = false;
let finishPassword = "";
let settingsDialogOpen = false;
let settingsPassword = "";
let settingsHydrated = false;
let audioContext = null;
let audioUnlocked = false;
let speechHistoryInitialized = false;
let lastSpokenHistoryKey = "";

function two(num) {
  return String(num).padStart(2, "0");
}

function formatTime(seconds) {
  const min = Math.floor(seconds / 60);
  const sec = seconds % 60;
  return `${two(min)}:${two(sec)}`;
}

function historyTime(entry) {
  const seconds = Number.isFinite(entry.remainingSeconds) ? entry.remainingSeconds : currentState.remainingSeconds;
  return formatTime(Math.max(0, seconds));
}

function clockTime(entry) {
  const value = entry.time || "";
  const match = value.match(/(\d{2}:\d{2}:\d{2})$/);
  return match ? match[1] : "";
}

function defaultTeamName(selector) {
  return selector.includes("white") ? ["白队", "White Team"] : ["红队", "Red Team"];
}

function teamNameLines(name) {
  const text = String(name || "").trim();
  const parts = text.split(/\s+/).filter(Boolean);
  if (parts.length < 2) return [text];

  const compactLength = parts.join("").length;
  const target = compactLength / 2;
  let bestIndex = 1;
  let bestDistance = Infinity;

  for (let index = 1; index < parts.length; index += 1) {
    const leftLength = parts.slice(0, index).join("").length;
    const distance = Math.abs(leftLength - target);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  }

  return [
    parts.slice(0, bestIndex).join(" "),
    parts.slice(bestIndex).join(" "),
  ];
}

function setTeamName(selector, name) {
  const element = document.querySelector(selector);
  if (!element) return;
  const text = String(name || "").trim();
  element.replaceChildren();
  element.classList.remove("scrolling");
  element.classList.remove("multi-line-team-name");
  element.classList.toggle("default-team-name", !text);
  element.style.removeProperty("--team-scroll-distance");

  if (!text) {
    defaultTeamName(selector).forEach((line, index) => {
      const span = document.createElement("span");
      span.className = index === 0 ? "team-name-primary" : "team-name-secondary";
      span.textContent = line;
      element.appendChild(span);
    });
    return;
  }

  const lines = teamNameLines(text);
  element.classList.toggle("multi-line-team-name", lines.length > 1);
  lines.forEach((line) => {
    const lineBox = document.createElement("span");
    lineBox.className = "team-name-line";

    const scrollText = document.createElement("span");
    scrollText.className = "team-name-scroll";
    scrollText.textContent = line;
    lineBox.appendChild(scrollText);
    element.appendChild(lineBox);
  });

  requestAnimationFrame(() => {
    element.querySelectorAll(".team-name-line").forEach((lineBox) => {
      const scrollText = lineBox.querySelector(".team-name-scroll");
      const distance = Math.ceil(scrollText.scrollWidth - lineBox.clientWidth);
      lineBox.classList.toggle("scrolling", distance > 4);
      if (distance > 4) {
        lineBox.style.setProperty("--team-scroll-distance", `${distance}px`);
      } else {
        lineBox.style.removeProperty("--team-scroll-distance");
      }
    });
  });
}

function speak(text) {
  if (!text) return;
  unlockAudio();
  playDing();
  if (!("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "zh-CN";
  utter.rate = 1;
  utter.onerror = (event) => console.warn("Speech failed", event.error);
  window.setTimeout(() => speechSynthesis.speak(utter), 240);
}

function unlockAudio() {
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (!AudioContext) return;
  if (!audioContext) audioContext = new AudioContext();
  if (audioContext.state === "suspended") audioContext.resume();
  audioUnlocked = true;
}

function playDing() {
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (!AudioContext) return;
  const ctx = audioContext || new AudioContext();
  audioContext = ctx;
  if (ctx.state === "suspended") ctx.resume();

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.setValueAtTime(1046.5, ctx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(1568, ctx.currentTime + 0.09);
  gain.gain.setValueAtTime(0.0001, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.22, ctx.currentTime + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.22);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.24);
}

function renderPillars(count) {
  if (count <= 0) return "";
  if (count === 1) return `<span class="pillar yellow"></span>`;
  if (count === 2) return `<span class="pillar green"></span><span class="pillar green"></span>`;
  return `<span class="pillar green"></span><span class="pillar-x">x${count}</span>`;
}

function renderRows(team) {
  const numbers = team === "red" ? [1, 3, 5, 7, 9] : [2, 4, 6, 8, 10];
  return numbers.map((number) => {
    const ball = currentState.balls.find((item) => item.number === number);
    const selected = currentState.selectedBall === number ? " selected" : "";
    const cells = [0, 1, 2, 3].map((step) => {
      const active = ball.step === step ? " active" : "";
      return `<td><span class="slot${active}"></span></td>`;
    }).join("");
    return `
      <tr class="${selected}">
        <th>${number}</th>
        ${cells}
        <td class="pillar-cell">${renderPillars(ball.pillarCount)}</td>
        <td class="score">${ball.score}</td>
      </tr>
    `;
  }).join("");
}

function renderScoreboard() {
  if (!currentState) return;
  document.querySelector("[data-title]").textContent = currentState.title;
  setTeamName("[data-red-team]", currentState.redTeam);
  setTeamName("[data-white-team]", currentState.whiteTeam);
  document.querySelector("[data-red-total]").textContent = currentState.redTotal;
  document.querySelector("[data-white-total]").textContent = currentState.whiteTotal;
  document.querySelector("[data-time]").textContent = formatTime(currentState.remainingSeconds);
  const timer = document.querySelector("[data-scoreboard-timer]");
  if (timer) {
    timer.classList.toggle("is-running", currentState.running);
    timer.classList.toggle("is-paused", !currentState.running && !currentState.timeExpired);
    timer.classList.toggle("is-expired", currentState.timeExpired);
  }
  document.querySelector("[data-match]").textContent = `第 ${currentState.matchNumber} 场`;
  document.querySelector("[data-status]").textContent = currentState.running ? "比赛中" : (currentState.timeExpired ? "时间到" : "暂停/待开始");
  renderRecentLog();
  document.querySelector("[data-red-rows]").innerHTML = renderRows("red");
  document.querySelector("[data-white-rows]").innerHTML = renderRows("white");
}

function renderRecentLog() {
  const log = document.querySelector("[data-recent-log]");
  if (!log) return;
  const entries = (currentState.history || [])
    .filter((entry) => entry.action !== "select")
    .slice(-3)
    .reverse();
  if (!entries.length) {
    log.innerHTML = `<div class="log-line">[${formatTime(currentState.remainingSeconds)}] ${currentState.lastMessage}</div>`;
    return;
  }
  log.innerHTML = entries.map((entry) => (
    `<div class="log-line"><span class="log-main"><span class="log-time">[${historyTime(entry)}]</span> ${entry.message}</span><span class="log-clock">${clockTime(entry)}</span></div>`
  )).join("");
}

function renderRemote() {
  if (!currentState) return;
  document.querySelector("[data-remote-title]").textContent = currentState.title;
  document.querySelector("[data-remote-time]").textContent = formatTime(currentState.remainingSeconds);
  setTeamName("[data-remote-red-team]", currentState.redTeam);
  setTeamName("[data-remote-white-team]", currentState.whiteTeam);
  document.querySelector("[data-remote-red-total]").textContent = currentState.redTotal;
  document.querySelector("[data-remote-white-total]").textContent = currentState.whiteTotal;
  document.querySelectorAll("[data-ball]").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.ball) === currentState.selectedBall);
  });
}

function historyKey(entry) {
  if (!entry) return "";
  return `${entry.time || ""}|${entry.remainingSeconds ?? ""}|${entry.action || ""}|${entry.message || ""}`;
}

function latestSpeakableHistoryEntry() {
  const speakableActions = new Set(["timer_warning", "time_expired"]);
  return [...(currentState?.history || [])].reverse().find((entry) => speakableActions.has(entry.action));
}

function autoSpeakServerEvents() {
  const latest = latestSpeakableHistoryEntry();
  const key = historyKey(latest);
  if (!speechHistoryInitialized) {
    speechHistoryInitialized = true;
    lastSpokenHistoryKey = key;
    return;
  }
  if (latest && key && key !== lastSpokenHistoryKey) {
    lastSpokenHistoryKey = key;
    speak(latest.message);
  }
}

function renderSettings() {
  if (!currentState) return;
  const form = document.querySelector("[data-settings-form]");
  if (!form) return;
  if (settingsHydrated) return;
  form.title.value = currentState.title;
  form.redTeam.value = currentState.redTeam;
  form.whiteTeam.value = currentState.whiteTeam;
  form.durationMinutes.value = Math.round(currentState.durationSeconds / 60);
  form.allowScoringWhenPaused.checked = currentState.allowScoringWhenPaused;
  settingsHydrated = true;
}

async function refresh() {
  try {
    currentState = await api.state();
  } catch (error) {
    return;
  }
  if (document.querySelector("[data-scoreboard]")) renderScoreboard();
  if (document.querySelector("[data-remote]")) renderRemote();
  if (document.querySelector("[data-settings-form]")) renderSettings();
  autoSpeakServerEvents();
}

async function sendAction(payload, shouldSpeak = true) {
  const result = await api.action(payload);
  currentState = result.state;
  if (document.querySelector("[data-scoreboard]")) renderScoreboard();
  if (document.querySelector("[data-remote]")) renderRemote();
  if (shouldSpeak) speak(result.message);
  return result;
}

function openFinishDialog() {
  finishDialogOpen = true;
  finishPassword = "";
  document.querySelector("[data-finish-dialog]")?.classList.add("open");
  document.querySelector("[data-finish-password]").textContent = "";
  speak("请输入密码结束比赛");
}

function closeFinishDialog() {
  finishDialogOpen = false;
  finishPassword = "";
  document.querySelector("[data-finish-dialog]")?.classList.remove("open");
}

function openSettingsDialog() {
  settingsDialogOpen = true;
  settingsPassword = "";
  document.querySelector("[data-settings-dialog]")?.classList.add("open");
  document.querySelector("[data-settings-password]").textContent = "";
}

function closeSettingsDialog() {
  settingsDialogOpen = false;
  settingsPassword = "";
  document.querySelector("[data-settings-dialog]")?.classList.remove("open");
}

function confirmFinish() {
  sendAction({ action: "finish", password: finishPassword });
  closeFinishDialog();
}

function isEditableTarget(target) {
  if (!target) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

function handlePasswordKey(event) {
  const digit = event.key >= "0" && event.key <= "9" ? event.key : "";
  if (finishDialogOpen) {
    if (event.key === "*") return closeFinishDialog();
    if (digit && finishPassword.length < 4) finishPassword += digit;
    if (event.key === "Backspace") finishPassword = finishPassword.slice(0, -1);
    document.querySelector("[data-finish-password]").textContent = "●".repeat(finishPassword.length);
    if (event.key === "Enter" || event.code === "NumpadEnter") {
      confirmFinish();
    }
    return true;
  }
  if (settingsDialogOpen) {
    if (event.key === "/") return closeSettingsDialog();
    if (digit && settingsPassword.length < 4) settingsPassword += digit;
    if (event.key === "Backspace") settingsPassword = settingsPassword.slice(0, -1);
    document.querySelector("[data-settings-password]").textContent = "●".repeat(settingsPassword.length);
    if (event.key === "Enter" || event.code === "NumpadEnter") {
      window.location.href = `/set?password=${encodeURIComponent(settingsPassword)}`;
    }
    return true;
  }
  return false;
}

document.addEventListener("keydown", (event) => {
  if (!finishDialogOpen && !settingsDialogOpen && isEditableTarget(event.target)) {
    return;
  }
  if (["Backspace", "Tab", "Enter", "+", "-", "*", "/"].includes(event.key) || event.code in keyMap) {
    event.preventDefault();
  }
  if (handlePasswordKey(event)) return;
  if (event.key === "*") return openFinishDialog();
  if (event.key === "/") return openSettingsDialog();
  const mapped = keyMap[event.code] || keyMap[event.key];
  if (mapped) sendAction(mapped);
});

document.addEventListener("pointerdown", () => {
  if (!audioUnlocked) unlockAudio();
}, { once: true });

document.addEventListener("click", (event) => {
  if (!audioUnlocked) unlockAudio();
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  if (action === "finish-dialog") return openFinishDialog();
  if (action === "settings-dialog") return openSettingsDialog();
  if (action === "close-finish") return closeFinishDialog();
  if (action === "close-settings") return closeSettingsDialog();
  if (action === "confirm-finish") return confirmFinish();
  const payload = { action };
  if (target.dataset.ball) payload.ball = Number(target.dataset.ball);
  sendAction(payload);
});

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-settings-form]");
  if (!form) return;
  event.preventDefault();
  const params = new URLSearchParams(window.location.search);
  const resultEl = document.querySelector("[data-save-result]");
  const submitButton = form.querySelector("button[type='submit']");
  if (resultEl) resultEl.textContent = "正在保存...";
  if (submitButton) submitButton.disabled = true;
  const result = await sendAction({
    action: "update_settings",
    password: params.get("password") || form.password.value,
    title: form.title.value,
    redTeam: form.redTeam.value,
    whiteTeam: form.whiteTeam.value,
    durationMinutes: form.durationMinutes.value,
    allowScoringWhenPaused: form.allowScoringWhenPaused.checked,
    finishPassword: form.finishPassword.value,
    settingsPassword: form.settingsPassword.value,
  }, false);
  if (resultEl) {
    resultEl.textContent = result.message;
    resultEl.classList.toggle("error", !result.ok);
  }
  if (submitButton) submitButton.disabled = false;
  settingsHydrated = false;
});

refresh();
setInterval(refresh, 1000);
