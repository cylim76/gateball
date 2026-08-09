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
  async weatherSearch(query) {
    const res = await fetch(`/api/weather/search?q=${encodeURIComponent(query)}`, { cache: "no-store" });
    return res.json();
  },
  async resultsMonth(year, month) {
    const res = await fetch(`/api/results/month?year=${year}&month=${month}`, { cache: "no-store" });
    return res.json();
  },
  async resultsDay(date) {
    const res = await fetch(`/api/results/day?date=${encodeURIComponent(date)}`, { cache: "no-store" });
    return res.json();
  },
  async resultMatch(id) {
    const res = await fetch(`/api/results/match?id=${encodeURIComponent(id)}`, { cache: "no-store" });
    return res.json();
  },
};

const keyBindingSpecs = [
  { id: "ball_1", name: "1号球", payload: { action: "select", ball: 1 }, defaults: [{ code: "Digit1", key: "1", label: "1" }, { code: "Numpad1", key: "1", label: "小键盘 1" }] },
  { id: "ball_2", name: "2号球", payload: { action: "select", ball: 2 }, defaults: [{ code: "Digit2", key: "2", label: "2" }, { code: "Numpad2", key: "2", label: "小键盘 2" }] },
  { id: "ball_3", name: "3号球", payload: { action: "select", ball: 3 }, defaults: [{ code: "Digit3", key: "3", label: "3" }, { code: "Numpad3", key: "3", label: "小键盘 3" }] },
  { id: "ball_4", name: "4号球", payload: { action: "select", ball: 4 }, defaults: [{ code: "Digit4", key: "4", label: "4" }, { code: "Numpad4", key: "4", label: "小键盘 4" }] },
  { id: "ball_5", name: "5号球", payload: { action: "select", ball: 5 }, defaults: [{ code: "Digit5", key: "5", label: "5" }, { code: "Numpad5", key: "5", label: "小键盘 5" }] },
  { id: "ball_6", name: "6号球", payload: { action: "select", ball: 6 }, defaults: [{ code: "Digit6", key: "6", label: "6" }, { code: "Numpad6", key: "6", label: "小键盘 6" }] },
  { id: "ball_7", name: "7号球", payload: { action: "select", ball: 7 }, defaults: [{ code: "Digit7", key: "7", label: "7" }, { code: "Numpad7", key: "7", label: "小键盘 7" }] },
  { id: "ball_8", name: "8号球", payload: { action: "select", ball: 8 }, defaults: [{ code: "Digit8", key: "8", label: "8" }, { code: "Numpad8", key: "8", label: "小键盘 8" }] },
  { id: "ball_9", name: "9号球", payload: { action: "select", ball: 9 }, defaults: [{ code: "Digit9", key: "9", label: "9" }, { code: "Numpad9", key: "9", label: "小键盘 9" }] },
  { id: "ball_10", name: "10号球", payload: { action: "select", ball: 10 }, defaults: [{ code: "Digit0", key: "0", label: "0" }, { code: "Numpad0", key: "0", label: "小键盘 0" }] },
  { id: "toggle_timer", name: "开始/暂停/继续", payload: { action: "toggle_timer" }, defaults: [{ code: "Enter", key: "Enter", label: "Enter" }, { code: "NumpadEnter", key: "Enter", label: "小键盘 Enter" }] },
  { id: "undo", name: "撤销", payload: { action: "undo" }, defaults: [{ code: "NumpadSubtract", key: "-", label: "小键盘 -" }, { code: "Minus", key: "-", label: "-" }] },
  { id: "advance", name: "得分", payload: { action: "advance" }, defaults: [{ code: "NumpadAdd", key: "+", label: "小键盘 +" }, { code: "Equal", key: "+", label: "+" }] },
  { id: "swap_team_names", name: "队名更换", payload: { action: "swap_team_names" }, defaults: [{ code: "Tab", key: "Tab", label: "Tab" }] },
  { id: "ten_second_countdown", name: "10秒倒计时", special: "ten-second-countdown", defaults: [{ code: "Backspace", key: "Backspace", label: "Backspace" }] },
  { id: "finish_dialog", name: "结束比赛", special: "finish-dialog", defaults: [{ code: "NumpadMultiply", key: "*", label: "小键盘 *" }] },
  { id: "finish_cancel", name: "结束取消", special: "finish-cancel", defaults: [{ code: "NumpadMultiply", key: "*", label: "小键盘 *" }, { code: "Escape", key: "Escape", label: "Esc" }] },
  { id: "settings_dialog", name: "打开设置", special: "remote-settings-dialog", defaults: [{ code: "NumpadDivide", key: "/", label: "小键盘 /" }] },
];

const keyBindingSpecById = Object.fromEntries(keyBindingSpecs.map((spec) => [spec.id, spec]));

let currentState = null;
let finishDialogOpen = false;
let finishPassword = "";
let finishVerifyInFlight = false;
let settingsDialogOpen = false;
let settingsPassword = "";
let settingsHydrated = false;
let swapTeamDialogOpen = false;
let editTeamDialogOpen = false;
let editTeamTarget = "";
let editTitleDialogOpen = false;
let remoteSettingsDialogOpen = false;
let settingsSavePasswordDialogOpen = false;
let pendingSettingsPayload = null;
let settingsSaveInFlight = false;
let keyCaptureAction = "";
let alertPromptAudio = null;
let finishPromptAudio = null;
let voiceManifestCache = {};
let voiceAudio = null;
let tenSecondCountdownIntroAudio = null;
let tenSecondCountdownAudio = null;
let tenSecondCountdownTimer = null;
let tenSecondCountdownIntroTimers = [];
let tenSecondCountdownRunId = 0;
let tenSecondCountdownActive = false;
let lastRenderedCountdownId = "";
let lastRenderedCountdownDigit = null;
let scoreboardAudioEnabled = false;
let speechHistoryInitialized = false;
let lastSpokenHistoryKey = "";
let weatherSearchTimer = null;
let wakeLockSentinel = null;
let wakeLockWanted = false;
let stateEventSource = null;
let refreshTimer = null;
let resultsYear = new Date().getFullYear();
let resultsMonth = new Date().getMonth() + 1;
let selectedResultsDate = "";
let resultDays = new Map();
const guardedActions = new Set(["toggle_timer", "undo", "advance", "swap_team_names", "ten-second-countdown", "ten_second_countdown"]);
const guardedActionTimes = new Map();
const ACTION_GUARD_MS = 800;

function two(num) {
  return String(num).padStart(2, "0");
}

function formatTime(seconds) {
  const min = Math.floor(seconds / 60);
  const sec = seconds % 60;
  return `${two(min)}:${two(sec)}`;
}

function finishPasswordLength() {
  const length = String(currentState?.finishPassword || "").length;
  return Math.min(6, Math.max(4, length || 4));
}

function settingsPasswordLength() {
  const length = String(currentState?.settingsPassword || "").length;
  return Math.min(6, Math.max(4, length || 4));
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

async function requestScreenWakeLock() {
  if (!wakeLockWanted || document.hidden || !("wakeLock" in navigator)) return;
  if (wakeLockSentinel) return;
  try {
    wakeLockSentinel = await navigator.wakeLock.request("screen");
    wakeLockSentinel.addEventListener("release", () => {
      wakeLockSentinel = null;
      if (wakeLockWanted && !document.hidden) {
        window.setTimeout(requestScreenWakeLock, 500);
      }
    });
  } catch (error) {
    console.warn("Screen wake lock unavailable", error);
  }
}

function initScreenWakeLock() {
  if (!document.querySelector("[data-scoreboard], [data-remote]")) return;
  wakeLockWanted = true;
  requestScreenWakeLock();
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;
    requestScreenWakeLock();
  });
  document.addEventListener("pointerdown", requestScreenWakeLock);
  document.addEventListener("keydown", requestScreenWakeLock);
}

function isoDate(year, month, day) {
  return `${year}-${two(month)}-${two(day)}`;
}

function bindingForSpec(spec) {
  const custom = currentState?.keyBindings?.[spec.id];
  if (custom && (custom.code || custom.key)) return custom;
  return spec.defaults[0];
}

function allBindingsForSpec(spec) {
  const custom = currentState?.keyBindings?.[spec.id];
  if (custom && (custom.code || custom.key)) return [custom];
  return spec.defaults;
}

function eventMatchesBindingSpec(event, spec) {
  return allBindingsForSpec(spec).some((binding) => (
    (binding.code && event.code === binding.code) || (binding.key && event.key === binding.key)
  ));
}

function keyLabelFromEvent(event) {
  if (event.code?.startsWith("Numpad")) {
    const suffix = event.code.replace("Numpad", "");
    const names = {
      Add: "+",
      Subtract: "-",
      Multiply: "*",
      Divide: "/",
      Decimal: ".",
      Enter: "Enter",
    };
    return `小键盘 ${names[suffix] || suffix}`;
  }
  if (event.key === " ") return "空格";
  if (event.key && event.key.length === 1) return event.key;
  return event.key || event.code;
}

function keyboardActionForEvent(event) {
  for (const spec of keyBindingSpecs) {
    if (eventMatchesBindingSpec(event, spec)) return spec;
  }
  return null;
}

function isMappedKeyboardEvent(event) {
  return Boolean(keyboardActionForEvent(event));
}

function shouldIgnoreGuardedAction(actionId) {
  if (!guardedActions.has(actionId)) return false;
  const now = Date.now();
  const last = guardedActionTimes.get(actionId) || 0;
  if (now - last < ACTION_GUARD_MS) return true;
  guardedActionTimes.set(actionId, now);
  return false;
}

function runKeyboardAction(spec) {
  if (!spec) return;
  if (shouldIgnoreGuardedAction(spec.id)) return;
  if (spec.id === "toggle_timer" && currentState?.timeExpired && !currentState?.running) return;
  if (spec.special === "ten-second-countdown") return startTenSecondCountdown();
  if (spec.special === "finish-dialog") return openFinishDialog();
  if (spec.special === "finish-cancel") return closeFinishDialog();
  if (spec.special === "remote-settings-dialog") {
    if (document.querySelector("[data-remote-settings-dialog]")) return openRemoteSettingsDialog();
    return openSettingsDialog();
  }
  if (spec.payload) sendAction(spec.payload);
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

function voiceProfilePath() {
  return currentState?.voiceProfile === "male" ? "voice-male" : "voice";
}

function normalizeSpeechText(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}

function voiceKeyForText(text) {
  const normalized = normalizeSpeechText(text);
  const exact = {
    "比赛开始": "match_start",
    "比赛暂停": "match_pause",
    "比赛继续": "match_resume",
    "等待开始": "match_waiting",
    "下一场比赛，等待开始": "next_match_waiting",
    "时间到": "time_up",
    "请输入密码结束比赛": "finish_password_prompt",
    "密码错误": "password_wrong",
    "设置已保存": "settings_saved",
    "按键映射已保存": "key_binding_saved",
    "按键映射失败": "key_binding_failed",
    "请先选择球号": "selection_required",
    "暂停期间不能计分": "scoring_paused_denied",
    "红白队名已更换": "team_swap_saved",
    "队名为空": "team_name_empty",
    "红队队名已保存": "red_team_saved",
    "白队队名已保存": "white_team_saved",
    "未知队伍": "unknown_team",
    "未知操作": "unknown_action",
    "倒计时10秒": "countdown_10",
    "10秒倒计时": "countdown_10",
    "10秒倒计时已停止": "countdown_10_stopped",
  };
  if (exact[normalized]) return exact[normalized];

  let match = normalized.match(/^比赛时间剩余\s*(15|10|5|1)\s*分钟$/);
  if (match) return `time_remaining_${match[1]}min`;

  match = normalized.match(/^(\d{1,2})号球$/);
  if (match) return `ball_${match[1]}`;

  match = normalized.match(/^(\d{1,2})号球[，,](一门得分|二门得分|三门得分|中柱得分)$/);
  if (match) {
    const suffix = { 一门得分: "gate1", 二门得分: "gate2", 三门得分: "gate3", 中柱得分: "pillar" }[match[2]];
    return `ball_${match[1]}_${suffix}`;
  }

  match = normalized.match(/^(\d{1,2})号球已到上限$/);
  if (match) return `ball_${match[1]}_limit`;

  match = normalized.match(/^(\d{1,2})号球没有可撤销记录$/);
  if (match) return `ball_${match[1]}_no_undo`;

  match = normalized.match(/^撤销[，,](\d{1,2})号球[，,](一门得分|二门得分|三门得分|中柱得分|回到0分)$/);
  if (match) {
    const suffix = { 一门得分: "gate1", 二门得分: "gate2", 三门得分: "gate3", 中柱得分: "pillar", 回到0分: "zero" }[match[2]];
    return `undo_ball_${match[1]}_${suffix}`;
  }

  return "";
}

async function getVoiceManifest(profilePath) {
  if (!voiceManifestCache[profilePath]) {
    const response = await fetch(`/audio/${profilePath}/manifest.json`, { cache: "force-cache" });
    if (!response.ok) throw new Error(`Voice manifest missing: ${profilePath}`);
    voiceManifestCache[profilePath] = await response.json();
  }
  return voiceManifestCache[profilePath];
}

function speakWithBrowser(text, onComplete) {
  if (!text) {
    onComplete?.();
    return;
  }
  if (!("speechSynthesis" in window)) {
    onComplete?.();
    return;
  }
  speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "zh-CN";
  utter.rate = 1;
  utter.onend = () => onComplete?.();
  utter.onerror = (event) => {
    console.warn("Speech failed", event.error);
    onComplete?.();
  };
  speechSynthesis.speak(utter);
}

function speak(text, onComplete) {
  if (!text) {
    onComplete?.();
    return;
  }
  const key = voiceKeyForText(text);
  if (!key) return speakWithBrowser(text, onComplete);
  getVoiceManifest(voiceProfilePath()).then((manifest) => {
    const file = manifest.items?.[key]?.file;
    if (!file) {
      speakWithBrowser(text, onComplete);
      return;
    }
    if (!voiceAudio) voiceAudio = new Audio();
    voiceAudio.pause();
    voiceAudio.currentTime = 0;
    voiceAudio.src = file;
    voiceAudio.onended = () => onComplete?.();
    voiceAudio.onerror = () => speakWithBrowser(text, onComplete);
    const playResult = voiceAudio.play();
    if (playResult?.catch) {
      playResult.catch(() => {
        showScoreboardSoundPrompt();
        speakWithBrowser(text, onComplete);
      });
    }
  }).catch(() => {
    showScoreboardSoundPrompt();
    speakWithBrowser(text, onComplete);
  });
}

function getFinishPromptAudio() {
  if (!finishPromptAudio) {
    finishPromptAudio = new Audio("/audio/finished.mp3");
    finishPromptAudio.preload = "auto";
    finishPromptAudio.volume = 0.45;
  }
  return finishPromptAudio;
}

function getAlertPromptAudio() {
  if (!alertPromptAudio) {
    alertPromptAudio = new Audio("/audio/alert.mp3");
    alertPromptAudio.preload = "auto";
    alertPromptAudio.volume = 0.45;
  }
  return alertPromptAudio;
}

function getTenSecondCountdownAudio() {
  if (!tenSecondCountdownAudio) {
    tenSecondCountdownAudio = new Audio("/audio/timeout.mp3");
    tenSecondCountdownAudio.preload = "auto";
    tenSecondCountdownAudio.volume = 0.6;
  }
  return tenSecondCountdownAudio;
}

function getTenSecondCountdownIntroAudio() {
  if (!tenSecondCountdownIntroAudio) {
    tenSecondCountdownIntroAudio = new Audio("/audio/countdown.mp3");
    tenSecondCountdownIntroAudio.preload = "auto";
    tenSecondCountdownIntroAudio.volume = 0.5;
  }
  return tenSecondCountdownIntroAudio;
}

function prepareAudio(audio) {
  const originalVolume = audio.volume;
  audio.pause();
  audio.currentTime = 0;
  audio.volume = 0;
  const playResult = audio.play();
  const reset = () => {
    audio.pause();
    audio.currentTime = 0;
    audio.volume = originalVolume || 1;
  };
  window.setTimeout(reset, 80);
  if (playResult?.catch) {
    playResult.catch(() => {
      audio.volume = originalVolume || 1;
    });
  }
}

function prepareTenSecondCountdownAudio() {
  prepareAudio(getTenSecondCountdownIntroAudio());
  prepareAudio(getTenSecondCountdownAudio());
}

function playAudio(audio, warningLabel) {
  audio.pause();
  audio.currentTime = 0;
  const playResult = audio.play();
  if (playResult?.catch) {
    playResult.catch((error) => {
      console.warn(`${warningLabel} audio failed`, error);
      showScoreboardSoundPrompt();
    });
  }
}

function showScoreboardSoundPrompt() {
  const button = document.querySelector("[data-sound-enable]");
  if (button && !scoreboardAudioEnabled) button.hidden = false;
}

function hideScoreboardSoundPrompt() {
  const button = document.querySelector("[data-sound-enable]");
  if (button) button.hidden = true;
}

function enableScoreboardSound() {
  scoreboardAudioEnabled = true;
  hideScoreboardSoundPrompt();
  prepareAudio(getAlertPromptAudio());
  prepareAudio(getFinishPromptAudio());
  prepareTenSecondCountdownAudio();
  speak("声音已启用");
}

function playTenSecondCountdownIntroAudio() {
  playAudio(getTenSecondCountdownIntroAudio(), "10 second countdown intro");
}

function playTenSecondCountdownAudio() {
  playAudio(getTenSecondCountdownAudio(), "10 second countdown");
}

function playAlertPromptSound(onComplete) {
  const audio = getAlertPromptAudio();
  let completed = false;
  const complete = () => {
    if (completed) return;
    completed = true;
    onComplete?.();
  };

  audio.pause();
  audio.currentTime = 0;
  audio.onended = complete;
  audio.onerror = complete;
  const playResult = audio.play();
  if (playResult?.catch) {
    playResult.catch((error) => {
      console.warn("Alert prompt audio failed", error);
      complete();
    });
  }
}

function speakWithAlert(text) {
  playAlertPromptSound(() => speak(text));
}

function clearTenSecondCountdownTimers() {
  if (tenSecondCountdownTimer) {
    window.clearTimeout(tenSecondCountdownTimer);
    tenSecondCountdownTimer = null;
  }
  tenSecondCountdownIntroTimers.forEach((timer) => window.clearTimeout(timer));
  tenSecondCountdownIntroTimers = [];
}

function stopTenSecondCountdown(shouldNotify = true) {
  tenSecondCountdownRunId += 1;
  tenSecondCountdownActive = false;
  clearTenSecondCountdownTimers();
  getTenSecondCountdownIntroAudio().pause();
  getTenSecondCountdownAudio().pause();
  getTenSecondCountdownIntroAudio().currentTime = 0;
  getTenSecondCountdownAudio().currentTime = 0;
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  clearCountdownOverlay();
  if (shouldNotify) {
    sendAction({ action: "cancel_ten_second_countdown" }, false).catch((error) => {
      console.warn("10 second countdown cancel event failed", error);
    });
  }
}

function scheduleTenSecondCountdownIntro(runId, startedAt) {
  const countdownBeepOffsets = [0, 1000, 2000, 3000, 4000, 5000];
  countdownBeepOffsets.forEach((offset) => {
    const delay = Math.max(0, startedAt + offset - Date.now());
    const timer = window.setTimeout(() => {
      if (runId === tenSecondCountdownRunId) {
        playTenSecondCountdownIntroAudio();
      }
    }, delay);
    tenSecondCountdownIntroTimers.push(timer);
  });
}

function startTenSecondCountdown() {
  if (tenSecondCountdownActive) {
    stopTenSecondCountdown();
    return;
  }
  tenSecondCountdownRunId += 1;
  const runId = tenSecondCountdownRunId;
  tenSecondCountdownActive = true;
  clearTenSecondCountdownTimers();
  getTenSecondCountdownIntroAudio().pause();
  getTenSecondCountdownAudio().pause();
  prepareTenSecondCountdownAudio();
  speak("倒计时10秒", () => {
    if (runId !== tenSecondCountdownRunId) return;
    const startedAt = Date.now();
    scheduleTenSecondCountdownIntro(runId, startedAt);
    tenSecondCountdownTimer = window.setTimeout(() => {
      if (runId !== tenSecondCountdownRunId) return;
      tenSecondCountdownTimer = null;
      playTenSecondCountdownAudio();
    }, 6000);
    window.setTimeout(() => {
      if (runId === tenSecondCountdownRunId) {
        tenSecondCountdownActive = false;
      }
    }, 10000);
    sendAction({ action: "ten_second_countdown" }, false).catch((error) => {
      console.warn("10 second countdown event failed", error);
    });
  });
}

function playFinishPromptSound(onComplete) {
  const audio = getFinishPromptAudio();
  let completed = false;
  const complete = () => {
    if (completed) return;
    completed = true;
    onComplete?.();
  };

  audio.pause();
  audio.currentTime = 0;
  audio.onended = complete;
  audio.onerror = complete;
  const playResult = audio.play();
  if (playResult?.catch) {
    playResult.catch((error) => {
      console.warn("Finish prompt audio failed", error);
      complete();
    });
  }
}

function renderPillars(count) {
  if (count <= 0) return "";
  if (count === 1) return `<span class="pillar yellow"></span>`;
  if (count === 2) return `<span class="pillar green"></span><span class="pillar green"></span>`;
  return `<span class="pillar green"></span><span class="pillar-x">x${count}</span>`;
}

function renderRows(team) {
  const numbers = team === "red" ? [1, 3, 5, 7, 9] : [2, 4, 6, 8, 10];
  const showSelection = shouldShowBallSelection();
  return numbers.map((number) => {
    const ball = currentState.balls.find((item) => item.number === number);
    const selected = showSelection && currentState.selectedBall === number ? " selected" : "";
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
    timer.classList.toggle("is-waiting", !currentState.running && !currentState.timeExpired && !currentState.timerStarted);
    timer.classList.toggle("is-paused", !currentState.running && !currentState.timeExpired && currentState.timerStarted);
    timer.classList.toggle("is-expired", currentState.timeExpired);
  }
  document.querySelector("[data-match]").textContent = `第 ${currentState.matchNumber} 场`;
  document.querySelector("[data-status]").textContent = currentState.running ? "比赛中" : (currentState.timeExpired ? "时间到" : (currentState.timerStarted ? "比赛暂停" : "等待开始"));
  renderRecentLog();
  document.querySelector("[data-red-rows]").innerHTML = renderRows("red");
  document.querySelector("[data-white-rows]").innerHTML = renderRows("white");
  renderCountdownOverlay();
}

function renderRecentLog(selector = "[data-recent-log]", limit = 3) {
  const log = document.querySelector(selector);
  if (!log) return;
  const entries = (currentState.history || [])
    .filter((entry) => entry.action !== "select")
    .slice(-limit)
    .reverse();
  if (!entries.length) {
    log.innerHTML = `<div class="log-line"><span class="log-main"><span class="log-time">[${formatTime(currentState.remainingSeconds)}]</span> ${currentState.lastMessage}</span></div>`;
    return;
  }
  log.innerHTML = entries.map((entry) => (
    `<div class="log-line"><span class="log-main"><span class="log-time">[${historyTime(entry)}]</span> ${entry.message}</span><span class="log-clock">${clockTime(entry)}</span></div>`
  )).join("");
}

function renderRemote() {
  if (!currentState) return;
  document.querySelector("[data-remote-title]").textContent = currentState.title;
  const remoteTime = document.querySelector("[data-remote-time]");
  const remoteState = document.querySelector("[data-remote-state]");
  const remoteStatusTime = document.querySelector(".remote-status-time");
  if (remoteTime) remoteTime.textContent = formatTime(currentState.remainingSeconds);
  if (remoteState) remoteState.textContent = currentState.running ? "比赛中" : (currentState.timeExpired ? "时间到" : (currentState.timerStarted ? "比赛暂停" : "等待开始"));
  if (remoteStatusTime) {
    remoteStatusTime.classList.toggle("is-running", currentState.running);
    remoteStatusTime.classList.toggle("is-waiting", !currentState.running && !currentState.timeExpired && !currentState.timerStarted);
    remoteStatusTime.classList.toggle("is-paused", !currentState.running && !currentState.timeExpired && currentState.timerStarted);
    remoteStatusTime.classList.toggle("is-expired", currentState.timeExpired);
  }
  const timerAction = document.querySelector("[data-action='toggle_timer']");
  if (timerAction) {
    timerAction.textContent = currentState.running ? "暂停" : (currentState.timerStarted && !currentState.timeExpired ? "继续" : "开始");
    timerAction.disabled = currentState.timeExpired && !currentState.running;
    timerAction.classList.toggle("disabled", currentState.timeExpired && !currentState.running);
  }
  const countdownAction = document.querySelector("[data-action='ten-second-countdown']");
  if (countdownAction) {
    countdownAction.textContent = tenSecondCountdownActive ? "停止倒计时" : "10秒倒计时";
  }
  setTeamName("[data-remote-status-red-team]", currentState.redTeam);
  setTeamName("[data-remote-status-white-team]", currentState.whiteTeam);
  document.querySelector("[data-remote-red-total]").textContent = currentState.redTotal;
  document.querySelector("[data-remote-white-total]").textContent = currentState.whiteTotal;
  const showSelection = shouldShowBallSelection();
  document.querySelectorAll("[data-ball]").forEach((button) => {
    const number = Number(button.dataset.ball);
    const ball = currentState.balls.find((item) => item.number === number);
    button.classList.toggle("active", showSelection && number === currentState.selectedBall);
    const badge = button.querySelector(".ball-score-badge");
    if (badge && ball) badge.textContent = String(ball.score);
  });
  renderRecentLog("[data-remote-recent-log]", 6);
}

function historyKey(entry) {
  if (!entry) return "";
  if (entry.id) return String(entry.id);
  return `${entry.time || ""}|${entry.remainingSeconds ?? ""}|${entry.action || ""}|${entry.message || ""}`;
}

function historyEntryAgeSeconds(entry) {
  const timestamp = Number.parseFloat(entry?.id || "");
  if (Number.isFinite(timestamp)) {
    const serverTime = Number(currentState?.serverTime);
    const nowSeconds = Number.isFinite(serverTime) ? serverTime : Date.now() / 1000;
    return nowSeconds - timestamp;
  }
  return Infinity;
}

function isFreshTimerWarning(entry) {
  return historyEntryAgeSeconds(entry) <= 8;
}

function latestSelectEntry() {
  return [...(currentState?.history || [])].reverse().find((entry) => entry.action === "select");
}

function shouldShowBallSelection() {
  const selectedAt = Number(currentState?.selectedBallAt);
  if (Number.isFinite(selectedAt)) {
    const serverTime = Number(currentState?.serverTime);
    const nowSeconds = Number.isFinite(serverTime) ? serverTime : Date.now() / 1000;
    return nowSeconds - selectedAt <= 30;
  }
  const latest = latestSelectEntry();
  if (!latest) return false;
  return latest.ball === currentState?.selectedBall && historyEntryAgeSeconds(latest) <= 30;
}

function clearCountdownOverlay() {
  const overlay = document.querySelector("[data-countdown-overlay]");
  const number = document.querySelector("[data-countdown-number]");
  overlay?.classList.remove("show");
  number?.classList.remove("tick");
  if (number) number.textContent = "";
  lastRenderedCountdownDigit = null;
}

function renderCountdownOverlay() {
  const overlay = document.querySelector("[data-countdown-overlay]");
  const number = document.querySelector("[data-countdown-number]");
  if (!overlay || !number) return;
  const countdownId = currentState?.tenSecondCountdownId || "";
  const startedAt = Number(currentState?.tenSecondCountdownStartedAt);
  const serverTime = Number(currentState?.serverTime);
  if (!countdownId || !Number.isFinite(startedAt) || !Number.isFinite(serverTime)) {
    clearCountdownOverlay();
    return;
  }

  const elapsed = serverTime - startedAt;
  const digit = 10 - Math.floor(Math.max(0, elapsed));
  if (elapsed < 0 || elapsed >= 10 || digit < 1) {
    clearCountdownOverlay();
    return;
  }

  overlay.classList.add("show");
  if (countdownId !== lastRenderedCountdownId || digit !== lastRenderedCountdownDigit) {
    lastRenderedCountdownId = countdownId;
    lastRenderedCountdownDigit = digit;
    number.classList.remove("tick");
    number.textContent = String(digit);
    void number.offsetWidth;
    number.classList.add("tick");
  }
}

function latestSpeakableHistoryEntry() {
  const scoreboard = Boolean(document.querySelector("[data-scoreboard]"));
  const speakableActions = scoreboard
    ? new Set([
      "select",
      "advance",
      "undo",
      "selection_required",
      "toggle_timer",
      "ten_second_countdown",
      "cancel_ten_second_countdown",
      "next_match",
      "timer_warning",
      "time_expired",
    ])
    : new Set(["timer_warning", "time_expired"]);
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
    if (latest.action === "time_expired") {
      playFinishPromptSound(() => speak(latest.message));
    } else if (latest.action === "timer_warning") {
      if (isFreshTimerWarning(latest)) {
        speakWithAlert(latest.message);
      }
    } else if (latest.action === "toggle_timer") {
      speakWithAlert(latest.message);
    } else {
      speak(latest.message);
    }
  }
}

function renderSettings() {
  if (!currentState) return;
  const form = document.querySelector("[data-settings-form]");
  if (!form) return;
  if (settingsHydrated) return;
  form.title.value = currentState.title;
  form.durationMinutes.value = Math.round(currentState.durationSeconds / 60);
  if (form.voiceProfile) form.voiceProfile.value = currentState.voiceProfile || "female";
  if (form.weatherLocation) form.weatherLocation.value = currentState.weatherLocation || "";
  if (form.weatherLatitude) form.weatherLatitude.value = currentState.weatherLatitude ?? "";
  if (form.weatherLongitude) form.weatherLongitude.value = currentState.weatherLongitude ?? "";
  form.allowScoringWhenPaused.checked = currentState.allowScoringWhenPaused;
  settingsHydrated = true;
}

function renderKeyBindings() {
  const list = document.querySelector("[data-key-binding-list]");
  if (!list) return;
  list.replaceChildren();
  keyBindingSpecs.forEach((spec) => {
    const row = document.createElement("div");
    row.className = "key-binding-row";

    const name = document.createElement("span");
    name.className = "key-binding-name";
    name.textContent = spec.name;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "key-binding-button";
    button.dataset.action = "capture-key-binding";
    button.dataset.bindingAction = spec.id;
    const binding = bindingForSpec(spec);
    button.textContent = keyCaptureAction === spec.id ? "请按键..." : (binding.label || binding.code || binding.key || "未设置");

    row.append(name, button);
    list.appendChild(row);
  });
}

function clearWeatherResults(form) {
  const results = form?.querySelector("[data-weather-search-results]");
  if (results) results.replaceChildren();
}

async function searchWeatherLocation(input) {
  const form = input.closest("[data-settings-form]");
  const results = form?.querySelector("[data-weather-search-results]");
  if (!form || !results) return;
  const query = input.value.trim();
  form.weatherLatitude.value = "";
  form.weatherLongitude.value = "";
  results.replaceChildren();
  if (query.length < 2) return;

  const data = await api.weatherSearch(query);
  if (!data.ok || !data.results?.length) {
    const empty = document.createElement("div");
    empty.className = "weather-search-empty";
    empty.textContent = "没有找到位置，可试试拼音、上级城市，或清空使用自动定位";
    results.appendChild(empty);
    return;
  }

  data.results.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "weather-search-option";
    button.dataset.action = "select-weather-location";
    button.dataset.name = item.name;
    button.dataset.latitude = item.latitude;
    button.dataset.longitude = item.longitude;
    button.textContent = item.name;
    results.appendChild(button);
  });
}

function scheduleWeatherSearch(input) {
  if (weatherSearchTimer) window.clearTimeout(weatherSearchTimer);
  weatherSearchTimer = window.setTimeout(() => searchWeatherLocation(input), 400);
}

function selectWeatherLocation(target) {
  const form = target.closest("[data-settings-form]");
  if (!form) return;
  form.weatherLocation.value = target.dataset.name || "";
  form.weatherLatitude.value = target.dataset.latitude || "";
  form.weatherLongitude.value = target.dataset.longitude || "";
  clearWeatherResults(form);
}

function initResultsPage() {
  if (!document.querySelector("[data-results]")) return;
  const yearSelect = document.querySelector("[data-results-year]");
  const monthSelect = document.querySelector("[data-results-month]");
  const now = new Date();
  resultsYear = now.getFullYear();
  resultsMonth = now.getMonth() + 1;

  if (yearSelect) {
    yearSelect.replaceChildren();
    for (let year = resultsYear - 5; year <= resultsYear + 1; year += 1) {
      const option = document.createElement("option");
      option.value = String(year);
      option.textContent = `${year}年`;
      option.selected = year === resultsYear;
      yearSelect.appendChild(option);
    }
  }
  if (monthSelect) {
    monthSelect.replaceChildren();
    for (let month = 1; month <= 12; month += 1) {
      const option = document.createElement("option");
      option.value = String(month);
      option.textContent = `${month}月`;
      option.selected = month === resultsMonth;
      monthSelect.appendChild(option);
    }
  }
  loadResultsMonth();
}

async function loadResultsMonth() {
  if (!document.querySelector("[data-results]")) return;
  const data = await api.resultsMonth(resultsYear, resultsMonth);
  resultDays = new Map((data.days || []).map((day) => [day.date, day.count]));
  selectedResultsDate = "";
  renderResultsCalendar();
  renderResultsEmptyDay();
}

function renderResultsCalendar() {
  const grid = document.querySelector("[data-calendar-grid]");
  if (!grid) return;
  grid.replaceChildren();
  const firstWeekday = new Date(resultsYear, resultsMonth - 1, 1).getDay();
  const daysInMonth = new Date(resultsYear, resultsMonth, 0).getDate();

  for (let index = 0; index < firstWeekday; index += 1) {
    const empty = document.createElement("span");
    empty.className = "calendar-empty";
    grid.appendChild(empty);
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = isoDate(resultsYear, resultsMonth, day);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "calendar-day";
    button.dataset.action = "select-result-date";
    button.dataset.date = date;
    button.classList.toggle("has-results", resultDays.has(date));
    button.classList.toggle("selected", selectedResultsDate === date);
    button.innerHTML = `<span>${day}</span>${resultDays.has(date) ? '<i></i>' : ""}`;
    grid.appendChild(button);
  }
}

function renderResultsEmptyDay(message = "请选择有绿点的日期") {
  const title = document.querySelector("[data-selected-date-title]");
  const body = document.querySelector("[data-results-day-body]");
  if (title) title.textContent = selectedResultsDate || "请选择日期";
  if (body) body.innerHTML = `<tr><td colspan="4">${escapeHtml(message)}</td></tr>`;
}

async function selectResultDate(date) {
  selectedResultsDate = date;
  renderResultsCalendar();
  const title = document.querySelector("[data-selected-date-title]");
  if (title) title.textContent = date;
  const body = document.querySelector("[data-results-day-body]");
  if (!body) return;
  body.innerHTML = `<tr><td colspan="4">正在读取...</td></tr>`;
  const data = await api.resultsDay(date);
  const matches = data.matches || [];
  if (!matches.length) {
    renderResultsEmptyDay("当天没有比赛记录");
    return;
  }
  body.innerHTML = matches.map((match) => `
    <tr class="result-row" data-action="open-result-match" data-match-id="${match.id}">
      <td class="ellipsis">${escapeHtml(match.red_team || "红队")}</td>
      <td class="score-cell">${match.red_score}</td>
      <td class="score-cell">${match.white_score}</td>
      <td class="ellipsis">${escapeHtml(match.white_team || "白队")}</td>
    </tr>
  `).join("");
}

function ballStepLabel(step) {
  return ["0分", "一门", "二门", "三门"][Number(step)] || "0分";
}

function renderDetailTeamTable(title, balls) {
  return `
    <section class="detail-team-table">
      <h3>${escapeHtml(title)}</h3>
      <table>
        <thead>
          <tr>
            <th>球号</th>
            <th>位置</th>
            <th>中柱</th>
            <th>分数</th>
          </tr>
        </thead>
        <tbody>
          ${balls.map((ball) => `
            <tr>
              <th>${ball.number}</th>
              <td>${ballStepLabel(ball.step)}</td>
              <td class="pillar-cell">${renderPillars(ball.pillarCount || 0)}</td>
              <td class="score-cell">${ball.score}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </section>
  `;
}

async function openResultMatch(matchId) {
  const data = await api.resultMatch(matchId);
  if (!data.ok) return;
  const match = data.match;
  const balls = match.balls || [];
  const redBalls = balls.filter((ball) => ball.number % 2 === 1);
  const whiteBalls = balls.filter((ball) => ball.number % 2 === 0);
  const dialog = document.querySelector("[data-result-detail-dialog]");
  const box = document.querySelector("[data-result-detail-box]");
  if (!dialog || !box) return;
  box.innerHTML = `
    <header class="detail-head">
      <strong>${escapeHtml(match.title || "比赛成绩")}</strong>
      <span>${escapeHtml(match.ended_at || "")}</span>
    </header>
    <section class="detail-score-line">
      <div><span>${escapeHtml(match.red_team || "红队")}</span><strong>${match.red_score}</strong></div>
      <b>:</b>
      <div><strong>${match.white_score}</strong><span>${escapeHtml(match.white_team || "白队")}</span></div>
    </section>
    <div class="detail-tables">
      ${renderDetailTeamTable("红队", redBalls)}
      ${renderDetailTeamTable("白队", whiteBalls)}
    </div>
  `;
  dialog.classList.add("open");
}

function closeResultDetail() {
  document.querySelector("[data-result-detail-dialog]")?.classList.remove("open");
}

function applyState(state, options = {}) {
  currentState = state;
  if (document.querySelector("[data-scoreboard]")) renderScoreboard();
  if (document.querySelector("[data-remote]")) renderRemote();
  if (document.querySelector("[data-settings-form]")) renderSettings();
  renderKeyBindings();
  if (options.speakEvents !== false) autoSpeakServerEvents();
}

async function refresh() {
  try {
    applyState(await api.state());
  } catch (error) {
    return;
  }
}

function startPolling() {
  if (refreshTimer) return;
  refresh();
  refreshTimer = window.setInterval(refresh, 1000);
}

function stopPolling() {
  if (!refreshTimer) return;
  window.clearInterval(refreshTimer);
  refreshTimer = null;
}

function startStateEvents() {
  if (document.querySelector("[data-results]")) return;
  if (!("EventSource" in window)) {
    startPolling();
    return;
  }
  refresh();
  stateEventSource = new EventSource("/api/events");
  stateEventSource.onmessage = (event) => {
    try {
      applyState(JSON.parse(event.data));
      stopPolling();
    } catch (error) {
      console.warn("State event parse failed", error);
    }
  };
  stateEventSource.onerror = () => {
    startPolling();
  };
}

async function sendAction(payload, shouldSpeak = true) {
  const result = await api.action(payload);
  applyState(result.state, { speakEvents: false });
  if (shouldSpeak) {
    if (payload.action === "toggle_timer") {
      speakWithAlert(result.message);
    } else {
      speak(result.message);
    }
    const latest = latestSpeakableHistoryEntry();
    if (latest) {
      speechHistoryInitialized = true;
      lastSpokenHistoryKey = historyKey(latest);
    }
  }
  return result;
}

function openFinishDialog() {
  if (finishDialogOpen) {
    closeFinishDialog();
    return;
  }
  finishDialogOpen = true;
  finishPassword = "";
  finishVerifyInFlight = false;
  document.querySelector("[data-finish-dialog]")?.classList.add("open");
  const input = document.querySelector("[data-finish-password]");
  if (input) input.value = "";
  const result = document.querySelector("[data-finish-result]");
  if (result) {
    result.textContent = "";
    result.classList.remove("error");
  }
  window.setTimeout(() => input?.focus(), 0);
  playFinishPromptSound(() => speak("请输入密码结束比赛"));
}

function closeFinishDialog() {
  finishDialogOpen = false;
  finishPassword = "";
  finishVerifyInFlight = false;
  const input = document.querySelector("[data-finish-password]");
  if (input) input.value = "";
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

function openRemoteSettingsDialog() {
  remoteSettingsDialogOpen = true;
  keyCaptureAction = "";
  settingsHydrated = false;
  document.querySelector("[data-remote-settings-dialog]")?.classList.add("open");
  renderSettings();
  renderKeyBindings();
}

function closeRemoteSettingsDialog() {
  remoteSettingsDialogOpen = false;
  keyCaptureAction = "";
  document.querySelector("[data-remote-settings-dialog]")?.classList.remove("open");
  renderKeyBindings();
}

function collectSettingsPayload(form) {
  return {
    action: "update_settings",
    title: form.title.value,
    durationMinutes: form.durationMinutes.value,
    voiceProfile: form.voiceProfile?.value || "female",
    weatherLocation: form.weatherLocation?.value || "",
    weatherLatitude: form.weatherLatitude?.value || "",
    weatherLongitude: form.weatherLongitude?.value || "",
    allowScoringWhenPaused: form.allowScoringWhenPaused.checked,
    finishPassword: form.finishPassword.value.replace(/\D/g, "").slice(0, 6),
    settingsPassword: form.settingsPassword.value.replace(/\D/g, "").slice(0, 6),
  };
}

function validateWeatherLocation(form) {
  const location = form.weatherLocation?.value.trim() || "";
  const latitude = form.weatherLatitude?.value.trim() || "";
  const longitude = form.weatherLongitude?.value.trim() || "";
  if (!location || (latitude && longitude)) return true;

  const resultEl = document.querySelector("[data-save-result]");
  if (resultEl) {
    resultEl.textContent = "请先从天气搜索结果中选择位置，或清空位置使用自动定位";
    resultEl.classList.add("error");
  }
  form.weatherLocation?.focus();
  return false;
}

function openSettingsSavePasswordDialog(payload) {
  pendingSettingsPayload = payload;
  settingsSavePasswordDialogOpen = true;
  const dialog = document.querySelector("[data-settings-save-password-dialog]");
  const input = document.querySelector("[data-settings-save-password-input]");
  const result = document.querySelector("[data-settings-save-password-result]");
  if (input) input.value = "";
  if (result) {
    result.textContent = "";
    result.classList.remove("error");
  }
  dialog?.classList.add("open");
  window.setTimeout(() => input?.focus(), 0);
}

function closeSettingsSavePasswordDialog() {
  settingsSavePasswordDialogOpen = false;
  pendingSettingsPayload = null;
  settingsSaveInFlight = false;
  document.querySelector("[data-settings-save-password-dialog]")?.classList.remove("open");
}

async function trySavePendingSettings() {
  const input = document.querySelector("[data-settings-save-password-input]");
  const resultEl = document.querySelector("[data-settings-save-password-result]");
  const password = (input?.value || "").replace(/\D/g, "").slice(0, settingsPasswordLength());
  if (input) input.value = password;
  if (!pendingSettingsPayload || settingsSaveInFlight || password.length < settingsPasswordLength()) return;
  settingsSaveInFlight = true;
  if (resultEl) {
    resultEl.textContent = "正在检查...";
    resultEl.classList.remove("error");
  }
  try {
    const result = await sendAction({ ...pendingSettingsPayload, password }, false);
    if (result.ok) {
      const saveResult = document.querySelector("[data-save-result]");
      if (saveResult) {
        saveResult.textContent = result.message;
        saveResult.classList.remove("error");
      }
      settingsHydrated = false;
      closeSettingsSavePasswordDialog();
    } else if (resultEl) {
      resultEl.textContent = "密码错误";
      resultEl.classList.add("error");
    }
  } finally {
    settingsSaveInFlight = false;
  }
}

async function saveKeyBindingFromEvent(event) {
  const spec = keyBindingSpecById[keyCaptureAction];
  if (!spec) return;
  const bindingAction = spec.id;
  keyCaptureAction = "";
  const result = await sendAction({
    action: "update_key_binding",
    bindingAction,
    code: event.code || "",
    key: event.key || "",
    label: keyLabelFromEvent(event),
  }, false);
  currentState = result.state;
  renderKeyBindings();
}

function openSwapTeamDialog() {
  swapTeamDialogOpen = true;
  document.querySelector("[data-swap-team-dialog]")?.classList.add("open");
}

function closeSwapTeamDialog() {
  swapTeamDialogOpen = false;
  document.querySelector("[data-swap-team-dialog]")?.classList.remove("open");
}

function openEditTeamDialog(team) {
  editTeamTarget = team === "white" ? "white" : "red";
  editTeamDialogOpen = true;
  const isWhite = editTeamTarget === "white";
  const currentName = isWhite ? currentState?.whiteTeam : currentState?.redTeam;
  const dialog = document.querySelector("[data-edit-team-dialog]");
  const title = document.querySelector("[data-edit-team-title]");
  const input = document.querySelector("[data-edit-team-input]");
  if (title) title.textContent = isWhite ? "修改白队队名" : "修改红队队名";
  if (input) input.value = currentName || "";
  dialog?.classList.add("open");
  window.setTimeout(() => input?.focus(), 0);
}

function closeEditTeamDialog() {
  editTeamDialogOpen = false;
  editTeamTarget = "";
  document.querySelector("[data-edit-team-dialog]")?.classList.remove("open");
}

function saveEditedTeamName() {
  const input = document.querySelector("[data-edit-team-input]");
  const name = input ? input.value.trim() : "";
  sendAction({ action: "set_team_name", team: editTeamTarget, name });
  closeEditTeamDialog();
}

function openEditTitleDialog() {
  editTitleDialogOpen = true;
  const dialog = document.querySelector("[data-edit-title-dialog]");
  const input = document.querySelector("[data-edit-title-input]");
  if (input) input.value = currentState?.title || "";
  dialog?.classList.add("open");
  window.setTimeout(() => input?.focus(), 0);
}

function closeEditTitleDialog() {
  editTitleDialogOpen = false;
  document.querySelector("[data-edit-title-dialog]")?.classList.remove("open");
}

function saveEditedTitle() {
  const input = document.querySelector("[data-edit-title-input]");
  const title = input ? input.value.trim() : "";
  sendAction({ action: "set_title", title });
  closeEditTitleDialog();
}

function confirmSwapTeam() {
  sendAction({ action: "swap_team_names" });
  closeSwapTeamDialog();
}

async function tryFinishWithPassword() {
  if (finishVerifyInFlight || finishPassword.length < finishPasswordLength()) return;
  finishVerifyInFlight = true;
  const resultEl = document.querySelector("[data-finish-result]");
  if (resultEl) {
    resultEl.textContent = "正在检查...";
    resultEl.classList.remove("error");
  }
  try {
    const result = await sendAction({ action: "finish", password: finishPassword }, false);
    if (result.ok) {
      speak(result.message);
      closeFinishDialog();
    } else {
      finishVerifyInFlight = false;
      finishPassword = "";
      const input = document.querySelector("[data-finish-password]");
      if (input) input.value = "";
      if (resultEl) {
        resultEl.textContent = "密码错误";
        resultEl.classList.add("error");
      }
    }
  } catch (error) {
    finishVerifyInFlight = false;
    finishPassword = "";
    const input = document.querySelector("[data-finish-password]");
    if (input) input.value = "";
    if (resultEl) {
      resultEl.textContent = "校验失败";
      resultEl.classList.add("error");
    }
  }
}

function isEditableTarget(target) {
  if (!target) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

function handlePasswordKey(event) {
  const digit = event.key >= "0" && event.key <= "9" ? event.key : "";
  if (swapTeamDialogOpen) {
    if (event.key === "Enter" || event.code === "NumpadEnter") confirmSwapTeam();
    if (event.key === "Backspace" || event.key === "Escape") closeSwapTeamDialog();
    return true;
  }
  if (editTeamDialogOpen) {
    if (event.key === "Enter" || event.code === "NumpadEnter") saveEditedTeamName();
    if (event.key === "Escape") closeEditTeamDialog();
    return event.key === "Enter" || event.code === "NumpadEnter" || event.key === "Escape";
  }
  if (editTitleDialogOpen) {
    if (event.key === "Enter" || event.code === "NumpadEnter") saveEditedTitle();
    if (event.key === "Escape") closeEditTitleDialog();
    return event.key === "Enter" || event.code === "NumpadEnter" || event.key === "Escape";
  }
  if (settingsSavePasswordDialogOpen) {
    if (event.key === "Escape") closeSettingsSavePasswordDialog();
    return event.key === "Escape";
  }
  if (finishDialogOpen) {
    if (eventMatchesBindingSpec(event, keyBindingSpecById.finish_dialog)) return closeFinishDialog();
    if (eventMatchesBindingSpec(event, keyBindingSpecById.finish_cancel)) return closeFinishDialog();
    if (digit && finishPassword.length < finishPasswordLength()) finishPassword += digit;
    if (event.key === "Backspace") {
      finishPassword = finishPassword.slice(0, -1);
      finishVerifyInFlight = false;
      const result = document.querySelector("[data-finish-result]");
      if (result) {
        result.textContent = "";
        result.classList.remove("error");
      }
    }
    const input = document.querySelector("[data-finish-password]");
    if (input) input.value = finishPassword;
    if (finishPassword.length >= finishPasswordLength()) tryFinishWithPassword();
    return true;
  }
  if (settingsDialogOpen) {
    if (event.key === "/") return closeSettingsDialog();
    if (digit && settingsPassword.length < settingsPasswordLength()) settingsPassword += digit;
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
  if (keyCaptureAction) {
    event.preventDefault();
    saveKeyBindingFromEvent(event);
    return;
  }
  if (settingsSavePasswordDialogOpen && isEditableTarget(event.target)) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeSettingsSavePasswordDialog();
    }
    return;
  }
  if (editTitleDialogOpen && isEditableTarget(event.target)) {
    if (event.key === "Enter" || event.code === "NumpadEnter") {
      event.preventDefault();
      saveEditedTitle();
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeEditTitleDialog();
    }
    return;
  }
  if (editTeamDialogOpen && isEditableTarget(event.target)) {
    if (event.key === "Enter" || event.code === "NumpadEnter") {
      event.preventDefault();
      saveEditedTeamName();
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeEditTeamDialog();
    }
    return;
  }
  if (remoteSettingsDialogOpen && event.key === "Escape" && !isEditableTarget(event.target)) {
    event.preventDefault();
    closeRemoteSettingsDialog();
    return;
  }
  if (remoteSettingsDialogOpen && isEditableTarget(event.target)) {
    return;
  }
  if (remoteSettingsDialogOpen) {
    event.preventDefault();
    return;
  }
  if (!finishDialogOpen && !settingsDialogOpen && !swapTeamDialogOpen && !editTeamDialogOpen && !editTitleDialogOpen && !remoteSettingsDialogOpen && isEditableTarget(event.target)) {
    return;
  }
  if (["Backspace", "Tab", "Enter", "+", "-", "*", "/"].includes(event.key) || isMappedKeyboardEvent(event)) {
    event.preventDefault();
  }
  if (handlePasswordKey(event)) return;
  const mapped = keyboardActionForEvent(event);
  if (mapped) runKeyboardAction(mapped);
});

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  if (shouldIgnoreGuardedAction(action)) {
    event.preventDefault();
    return;
  }
  if (action === "finish-dialog") return openFinishDialog();
  if (action === "ten-second-countdown") return startTenSecondCountdown();
  if (action === "edit-title-dialog") return openEditTitleDialog();
  if (action === "edit-team-dialog") return openEditTeamDialog(target.dataset.team);
  if (action === "swap-team-dialog") return openSwapTeamDialog();
  if (action === "settings-dialog") return openSettingsDialog();
  if (action === "remote-settings-dialog") return openRemoteSettingsDialog();
  if (action === "close-finish") return closeFinishDialog();
  if (action === "close-settings") return closeSettingsDialog();
  if (action === "close-remote-settings") return closeRemoteSettingsDialog();
  if (action === "close-settings-save-password") return closeSettingsSavePasswordDialog();
  if (action === "close-swap-team") return closeSwapTeamDialog();
  if (action === "close-edit-team") return closeEditTeamDialog();
  if (action === "close-edit-title") return closeEditTitleDialog();
  if (action === "select-weather-location") return selectWeatherLocation(target);
  if (action === "select-result-date") return selectResultDate(target.dataset.date);
  if (action === "open-result-match") return openResultMatch(target.dataset.matchId);
  if (action === "enable-scoreboard-sound") return enableScoreboardSound();
  if (action === "capture-key-binding") {
    keyCaptureAction = target.dataset.bindingAction || "";
    renderKeyBindings();
    return;
  }
  if (action === "confirm-swap-team") return confirmSwapTeam();
  if (action === "toggle_timer" && currentState?.timeExpired && !currentState?.running) return;
  const payload = { action };
  if (target.dataset.ball) payload.ball = Number(target.dataset.ball);
  sendAction(payload);
});

document.addEventListener("input", (event) => {
  const weatherInput = event.target.closest("[data-weather-location-input]");
  if (weatherInput) {
    scheduleWeatherSearch(weatherInput);
    return;
  }
  const finishInput = event.target.closest("[data-finish-password]");
  if (finishInput) {
    finishPassword = finishInput.value.replace(/\D/g, "").slice(0, finishPasswordLength());
    finishInput.value = finishPassword;
    finishVerifyInFlight = false;
    const result = document.querySelector("[data-finish-result]");
    if (result) {
      result.textContent = "";
      result.classList.remove("error");
    }
    if (finishPassword.length >= finishPasswordLength()) tryFinishWithPassword();
    return;
  }
  const numericPasswordInput = event.target.closest("input[name='finishPassword'], input[name='settingsPassword']");
  if (numericPasswordInput) {
    numericPasswordInput.value = numericPasswordInput.value.replace(/\D/g, "").slice(0, 6);
    return;
  }
  if (!event.target.closest("[data-settings-save-password-input]")) return;
  trySavePendingSettings();
});

document.addEventListener("change", (event) => {
  const yearSelect = event.target.closest("[data-results-year]");
  if (yearSelect) {
    resultsYear = Number(yearSelect.value);
    loadResultsMonth();
    return;
  }
  const monthSelect = event.target.closest("[data-results-month]");
  if (monthSelect) {
    resultsMonth = Number(monthSelect.value);
    loadResultsMonth();
  }
});

document.addEventListener("pointerdown", (event) => {
  const dialog = event.target.closest("[data-result-detail-dialog]");
  if (dialog && event.target === dialog) closeResultDetail();
});

document.addEventListener("submit", async (event) => {
  const editTitleForm = event.target.closest("[data-edit-title-form]");
  if (editTitleForm) {
    event.preventDefault();
    saveEditedTitle();
    return;
  }

  const editTeamForm = event.target.closest("[data-edit-team-form]");
  if (editTeamForm) {
    event.preventDefault();
    saveEditedTeamName();
    return;
  }

  const form = event.target.closest("[data-settings-form]");
  if (!form) return;
  event.preventDefault();
  const resultEl = document.querySelector("[data-save-result]");
  if (resultEl) {
    resultEl.textContent = "";
    resultEl.classList.remove("error");
  }
  if (!validateWeatherLocation(form)) return;
  openSettingsSavePasswordDialog(collectSettingsPayload(form));
});

initScreenWakeLock();
initResultsPage();
startStateEvents();
