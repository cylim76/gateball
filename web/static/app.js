async function readJsonResponse(res, fallbackMessage = "服务返回格式不正确") {
  const contentType = res.headers.get("content-type") || "";
  const text = await res.text();
  if (!res.ok) {
    if (text.trim().startsWith("<")) {
      return { ok: false, message: "服务接口未更新，请重启门球服务后再试" };
    }
    return { ok: false, message: text || fallbackMessage };
  }
  if (!contentType.includes("application/json")) {
    return { ok: false, message: text.trim().startsWith("<") ? "服务接口未更新，请重启门球服务后再试" : fallbackMessage };
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    return { ok: false, message: fallbackMessage };
  }
}

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
  async networkStatus() {
    const res = await fetch("/api/network/status", { cache: "no-store" });
    return readJsonResponse(res, "网络状态读取失败");
  },
  async networkScan() {
    const res = await fetch("/api/network/scan", { cache: "no-store" });
    return readJsonResponse(res, "WiFi 扫描失败");
  },
  async networkConnect(payload) {
    const res = await fetch("/api/network/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return readJsonResponse(res, "WiFi 连接失败，热点会继续保留");
  },
  async teamNameAudio(payload) {
    const res = await fetch("/api/voice/team-name", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return readJsonResponse(res, "队名语音生成失败");
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
const DEFAULT_TITLE_COLOR = "#ffe23a";
const DEFAULT_TITLE_FONT_SCALE = 1;
const DEFAULT_TABLE_MARKER_SCALE = 1;

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
let errorPromptAudio = null;
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
let stylePreviewTimer = null;
let resultsYear = new Date().getFullYear();
let resultsMonth = new Date().getMonth() + 1;
let selectedResultsDate = "";
let resultDays = new Map();
let currentStateReceivedAt = 0;
let countdownOverlayTimer = null;
let networkStatusLoaded = false;
let lastNetworkStatus = null;
let wifiScanInFlight = false;
let wifiConnectInFlight = false;
let readySpeechTimer = null;
let matchTransitionInFlight = false;
let finishAdvanceInFlight = false;
let remoteFinishPlaybackLocked = false;
let celebrationAnimationFrame = null;
let celebrationParticles = [];
let celebrationLastBurstAt = 0;
let celebrationLastFrameAt = 0;
const teamNameAudioCache = new Map();
const guardedActions = new Set(["toggle_timer", "undo", "advance", "swap_team_names", "ten-second-countdown", "ten_second_countdown"]);
const guardedActionTimes = new Map();
const ACTION_GUARD_MS = 800;
const TIMEOUT_AUDIO_OFFSET_MS = 5500;
const READY_SPEECH_DELAY_MS = 30000;
const FINISH_SUMMARY_TAIL_CUT_MS = 450;
const MATCH_TRANSITION_HOLD_MS = 320;
const MATCH_TRANSITION_FALLBACK_MS = 45000;
const ERROR_PROMPT_LEAD_MS = 400;
const ERROR_PROMPT_FALLBACK_START_MS = 800;
const DEFAULT_GAMEPLAY_PLAYBACK_RATE = 1.2;
const VOICE_PROFILES = ["female", "male", "ko-female", "ko-male"];
const isKioskMode = new URLSearchParams(window.location.search).get("kiosk") === "1";

function two(num) {
  return String(num).padStart(2, "0");
}

function withTimeout(promise, ms, message) {
  let timer = null;
  const timeout = new Promise((_, reject) => {
    timer = window.setTimeout(() => reject(new Error(message)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => {
    if (timer) window.clearTimeout(timer);
  });
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

function vibrateRemoteTap(event) {
  if (!document.querySelector("[data-remote]")) return;
  if (!event.isPrimary) return;
  if (!event.target.closest("button, .results-link")) return;
  if (!("vibrate" in navigator)) return;
  navigator.vibrate(8);
}

function runKeyboardAction(spec) {
  if (!spec) return;
  if (remoteFinishPlaybackLocked && document.querySelector("[data-remote]")) return;
  if (shouldIgnoreGuardedAction(spec.id)) return;
  if (spec.id === "toggle_timer" && (currentState?.matchFinished || (currentState?.timeExpired && !currentState?.running))) return;
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

function resultTime(value) {
  const match = String(value || "").match(/(\d{2}:\d{2})(?::\d{2})?$/);
  return match ? match[1] : "";
}

function defaultTeamName(selector) {
  return selector.includes("white") ? ["白队", "White Team"] : ["红队", "Red Team"];
}

function hasHangul(text) {
  return /[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]/.test(String(text || ""));
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
  element.classList.toggle("has-hangul", hasHangul(text));
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
  const paths = {
    female: "voice-cn-female",
    male: "voice-cn-male",
    "ko-female": "voice-ko-female",
    "ko-male": "voice-ko-male",
  };
  return paths[currentState?.voiceProfile] || "voice-cn-female";
}

function voiceProfileName() {
  return currentState?.voiceProfile || "female";
}

function isDefaultTeamName(team, name) {
  const normalized = normalizeSpeechText(name);
  const defaults = {
    red: new Set(["", "红队", "홍팀", "Red Team"]),
    white: new Set(["", "白队", "백팀", "White Team"]),
  };
  return defaults[team]?.has(normalized) ?? !normalized;
}

function teamNameVoiceProfile(profile, name) {
  const isMale = profile === "male" || profile === "ko-male";
  const text = String(name || "");
  if (/[\uac00-\ud7af]/.test(text)) return isMale ? "ko-male" : "ko-female";
  if (/[\u3400-\u9fff]/.test(text)) return isMale ? "male" : "female";
  return profile || "female";
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
    "比赛结束": "match_finished",
    "请输入密码结束比赛": "finish_password_prompt",
    "密码错误": "password_wrong",
    "设置已保存": "settings_saved",
    "比赛标题已保存": "title_saved",
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

function playbackRateForVoiceKey(key) {
  if (/^(ball|undo_ball)_/.test(key)) {
    const rate = Number(currentState?.voicePlaybackRate);
    return Number.isFinite(rate) ? Math.min(2, Math.max(0.8, rate)) : DEFAULT_GAMEPLAY_PLAYBACK_RATE;
  }
  return 1;
}

function isErrorVoiceKey(key) {
  return key === "password_wrong"
    || key === "key_binding_failed"
    || key === "selection_required"
    || key === "scoring_paused_denied"
    || key === "unknown_team"
    || key === "unknown_action"
    || /^ball_\d+_(limit|no_undo)$/.test(key || "");
}

function isErrorSpeechText(text) {
  return isErrorVoiceKey(voiceKeyForText(text));
}

async function getVoiceManifest(profilePath) {
  if (!voiceManifestCache[profilePath]) {
    const response = await fetch(`/audio/${profilePath}/manifest.json`, { cache: "force-cache" });
    if (!response.ok) throw new Error(`Voice manifest missing: ${profilePath}`);
    voiceManifestCache[profilePath] = await response.json();
  }
  return voiceManifestCache[profilePath];
}

function playVoiceFile(file, playbackRate = 1, tailCutMs = 0) {
  return new Promise((resolve) => {
    if (!file) {
      resolve();
      return;
    }
    let completed = false;
    let tailTimer = null;
    const complete = () => {
      if (completed) return;
      completed = true;
      if (tailTimer) window.clearTimeout(tailTimer);
      resolve();
    };
    if (!voiceAudio) voiceAudio = new Audio();
    voiceAudio.pause();
    voiceAudio.currentTime = 0;
    voiceAudio.src = file;
    voiceAudio.defaultPlaybackRate = playbackRate;
    voiceAudio.playbackRate = playbackRate;
    voiceAudio.onloadedmetadata = () => {
      if (!tailCutMs || !Number.isFinite(voiceAudio.duration)) return;
      const durationMs = (voiceAudio.duration * 1000) / playbackRate;
      const waitMs = Math.max(60, durationMs - tailCutMs);
      tailTimer = window.setTimeout(complete, waitMs);
    };
    voiceAudio.onended = complete;
    voiceAudio.onerror = complete;
    const playResult = voiceAudio.play();
    if (playResult?.catch) {
      playResult.catch((error) => {
        console.warn("Voice audio failed", error);
        showScoreboardSoundPrompt();
        complete();
      });
    }
  });
}

async function playVoiceKey(key, playbackRate = 1, tailCutMs = 0) {
  const manifest = await getVoiceManifest(voiceProfilePath());
  await playVoiceFile(manifest.items?.[key]?.file, playbackRate, tailCutMs);
}

async function playVoiceItems(items, playbackRate = 1, tailCutMs = 0) {
  for (const item of items.filter(Boolean)) {
    if (item.key) {
      await playVoiceKey(item.key, playbackRate, tailCutMs);
    } else if (item.file) {
      await playVoiceFile(item.file, playbackRate, tailCutMs);
    }
  }
}

function playVoiceItemsWithCallback(items, onComplete, playbackRate = 1, tailCutMs = 0) {
  playVoiceItems(items, playbackRate, tailCutMs).then(() => onComplete?.()).catch((error) => {
    console.warn("Voice queue failed", error);
    onComplete?.();
  });
}

function scoreKey(score) {
  const value = Math.max(0, Math.min(100, Number(score) || 0));
  return `score_${value}`;
}

function scoreForTeam(snapshot, team) {
  return Number(team === "red" ? snapshot?.redTotal : snapshot?.whiteTotal) || 0;
}

async function teamNameVoiceItem(team, name) {
  if (isDefaultTeamName(team, name)) return null;
  const profile = teamNameVoiceProfile(voiceProfileName(), name);
  const cacheKey = `${profile}:${team}:${normalizeSpeechText(name)}`;
  if (!teamNameAudioCache.has(cacheKey)) {
    teamNameAudioCache.set(cacheKey, api.teamNameAudio({ profile, team, name }).catch((error) => ({ ok: false, message: error.message })));
  }
  const result = await teamNameAudioCache.get(cacheKey);
  return result?.ok && result.file ? { file: result.file } : null;
}

function precacheTeamNameAudio(team, name) {
  if (isDefaultTeamName(team, name)) return;
  const profiles = new Set(VOICE_PROFILES.map((profile) => teamNameVoiceProfile(profile, name)));
  profiles.forEach((profile) => {
    const cacheKey = `${profile}:${team}:${normalizeSpeechText(name)}`;
    if (!teamNameAudioCache.has(cacheKey)) {
      teamNameAudioCache.set(cacheKey, api.teamNameAudio({ profile, team, name }).catch((error) => ({ ok: false, message: error.message })));
    }
  });
}

async function teamScoreItems(team, name, score) {
  const items = [{ key: team === "red" ? "red_team" : "white_team" }];
  const nameItem = await teamNameVoiceItem(team, name);
  if (nameItem) items.push(nameItem);
  items.push({ key: "score_total" }, { key: scoreKey(score) });
  return items;
}

async function winnerItems(snapshot) {
  const redScore = scoreForTeam(snapshot, "red");
  const whiteScore = scoreForTeam(snapshot, "white");
  if (redScore === whiteScore) return [{ key: "draw_game" }];
  const team = redScore > whiteScore ? "red" : "white";
  const name = team === "red" ? snapshot?.redTeam : snapshot?.whiteTeam;
  const items = [{ key: team === "red" ? "winner_red_prefix" : "winner_white_prefix" }];
  const nameItem = await teamNameVoiceItem(team, name);
  if (nameItem) items.push(nameItem);
  items.push({ key: "winner_suffix" });
  return items;
}

async function finishSummaryItems(snapshot) {
  const items = [];
  items.push(...await teamScoreItems("red", snapshot?.redTeam, scoreForTeam(snapshot, "red")));
  items.push(...await teamScoreItems("white", snapshot?.whiteTeam, scoreForTeam(snapshot, "white")));
  items.push(...await winnerItems(snapshot));
  return items;
}

async function playFinishSummary(snapshot, options = {}) {
  const { openingKey = "time_up" } = options;
  const playbackRate = playbackRateForVoiceKey(openingKey);
  cancelReadySpeech();
  await playPromptAudio(getFinishPromptAudio(), "Finish prompt");
  if (openingKey) {
    await playVoiceKey(openingKey, playbackRate, FINISH_SUMMARY_TAIL_CUT_MS);
  }
  const items = await finishSummaryItems(snapshot);
  await playVoiceItems(items, playbackRate, FINISH_SUMMARY_TAIL_CUT_MS);
}

function waitMs(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function waitForAnimation(element, fallbackMs = 800) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      element.removeEventListener("animationend", finish);
      resolve();
    };
    element.addEventListener("animationend", finish, { once: true });
    window.setTimeout(finish, fallbackMs);
  });
}

function elementCenter(element) {
  if (!element) return null;
  const rect = element.getBoundingClientRect();
  if (!rect.width && !rect.height) return null;
  return {
    x: rect.left + rect.width / 2,
    y: rect.top + rect.height / 2,
  };
}

function matchTransitionOrigin() {
  const remoteButton = document.querySelector("[data-remote] .timer-action");
  const remoteCenter = elementCenter(remoteButton);
  if (remoteCenter) return remoteCenter;

  const redTotal = document.querySelector("[data-scoreboard] [data-red-total]");
  const whiteTotal = document.querySelector("[data-scoreboard] [data-white-total]");
  if (redTotal && whiteTotal) {
    const redRect = redTotal.getBoundingClientRect();
    const whiteRect = whiteTotal.getBoundingClientRect();
    if ((redRect.width || redRect.height) && (whiteRect.width || whiteRect.height)) {
      return {
        x: (redRect.right + whiteRect.left) / 2,
        y: Math.max(redRect.bottom, whiteRect.bottom) + 18,
      };
    }
  }

  return { x: window.innerWidth / 2, y: window.innerHeight / 2 };
}

async function runMatchTransition(updateState) {
  const overlay = document.querySelector("[data-match-transition]");
  const shape = document.querySelector("[data-match-transition-shape]");
  if (!overlay || !shape || matchTransitionInFlight) {
    await updateState?.();
    return;
  }
  matchTransitionInFlight = true;
  const shapes = ["circle", "diamond", "square", "ellipse-wide", "ellipse-tall"];
  const shapeName = shapes[Math.floor(Math.random() * shapes.length)];
  const origin = matchTransitionOrigin();
  overlay.style.setProperty("--transition-origin-x", `${origin.x}px`);
  overlay.style.setProperty("--transition-origin-y", `${origin.y}px`);
  overlay.classList.add("active");
  shape.className = `match-transition-shape ${shapeName}`;
  void shape.offsetWidth;
  try {
    shape.classList.add("cover");
    await waitForAnimation(shape);
    await waitMs(MATCH_TRANSITION_HOLD_MS);
    await updateState?.();
    shape.classList.remove("cover");
    void shape.offsetWidth;
    shape.classList.add("reveal");
    await waitForAnimation(shape);
  } finally {
    shape.className = "match-transition-shape";
    overlay.classList.remove("active");
    matchTransitionInFlight = false;
  }
}

async function advanceToNextMatchWithTransition() {
  if (finishAdvanceInFlight) return;
  finishAdvanceInFlight = true;
  try {
    await runMatchTransition(async () => {
      await sendAction({ action: "advance_to_next_match" }, false, { skipTransition: true });
    });
    scheduleReadySpeech();
  } catch (error) {
    console.warn("Advance to next match failed", error);
  } finally {
    finishAdvanceInFlight = false;
  }
}

async function playFinishThenAdvance(snapshot, options = {}) {
  let advanced = false;
  remoteFinishPlaybackLocked = Boolean(document.querySelector("[data-remote]"));
  if (remoteFinishPlaybackLocked) renderRemote();
  const advanceOnce = async () => {
    if (advanced) return;
    advanced = true;
    await advanceToNextMatchWithTransition();
  };
  const fallback = window.setTimeout(() => {
    advanceOnce();
  }, MATCH_TRANSITION_FALLBACK_MS);
  try {
    await playFinishSummary(snapshot, options);
  } finally {
    window.clearTimeout(fallback);
    await advanceOnce();
    if (remoteFinishPlaybackLocked) {
      remoteFinishPlaybackLocked = false;
      renderRemote();
    }
  }
}

async function matchStartItems(snapshot = currentState) {
  const items = [{ key: "match_start" }];
  const redName = await teamNameVoiceItem("red", snapshot?.redTeam);
  const whiteName = await teamNameVoiceItem("white", snapshot?.whiteTeam);
  if (redName || whiteName) {
    items.push({ key: "red_team" });
    if (redName) items.push(redName);
    items.push({ key: "white_team" });
    if (whiteName) items.push(whiteName);
  }
  return items;
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
  playVoiceKey(key, playbackRateForVoiceKey(key)).then(() => onComplete?.()).catch(() => {
    showScoreboardSoundPrompt();
    onComplete?.();
  });
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

function getErrorPromptAudio() {
  if (!errorPromptAudio) {
    errorPromptAudio = new Audio("/audio/error.mp3");
    errorPromptAudio.preload = "auto";
    errorPromptAudio.volume = 0.55;
  }
  return errorPromptAudio;
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
  if (isKioskMode) return;
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
  prepareAudio(getErrorPromptAudio());
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

function playPromptAudio(audio, warningLabel) {
  return new Promise((resolve) => {
    let completed = false;
    const complete = () => {
      if (completed) return;
      completed = true;
      resolve();
    };
    audio.pause();
    audio.currentTime = 0;
    audio.onended = complete;
    audio.onerror = complete;
    const playResult = audio.play();
    if (playResult?.catch) {
      playResult.catch((error) => {
        console.warn(`${warningLabel} audio failed`, error);
        complete();
      });
    }
  });
}

function playPromptLeadAudio(audio, warningLabel, leadMs, fallbackStartMs, onLead) {
  return new Promise((resolve) => {
    let completed = false;
    let leadTimer = null;
    const clearLeadTimer = () => {
      if (leadTimer) {
        window.clearTimeout(leadTimer);
        leadTimer = null;
      }
    };
    const startLead = () => {
      if (completed) return;
      clearLeadTimer();
      onLead?.();
    };
    const complete = () => {
      if (completed) return;
      completed = true;
      clearLeadTimer();
      resolve();
    };
    audio.pause();
    audio.currentTime = 0;
    audio.onended = complete;
    audio.onerror = complete;
    const durationMs = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration * 1000 : 0;
    const delayMs = durationMs ? Math.max(0, durationMs - leadMs) : fallbackStartMs;
    leadTimer = window.setTimeout(startLead, delayMs);
    const playResult = audio.play();
    if (playResult?.catch) {
      playResult.catch((error) => {
        console.warn(`${warningLabel} audio failed`, error);
        startLead();
        complete();
      });
    }
  });
}

function speakWithAlert(text) {
  playPromptAudio(getAlertPromptAudio(), "Alert prompt").then(() => speak(text));
}

function speakWithError(text) {
  playPromptLeadAudio(
    getErrorPromptAudio(),
    "Error prompt",
    ERROR_PROMPT_LEAD_MS,
    ERROR_PROMPT_FALLBACK_START_MS,
    () => speak(text)
  );
}

function speakWithPromptForText(text) {
  if (isErrorSpeechText(text)) {
    speakWithError(text);
  } else {
    speakWithAlert(text);
  }
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
  stopCountdownOverlayTicker();
  if (currentState) {
    currentState.tenSecondCountdownId = null;
    currentState.tenSecondCountdownStartedAt = null;
  }
  if (voiceAudio) {
    voiceAudio.pause();
    voiceAudio.currentTime = 0;
  }
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
  prepareTenSecondCountdownAudio();
  speak("倒计时10秒", () => {
    if (runId !== tenSecondCountdownRunId) return;
    const startedAt = Date.now();
    scheduleTenSecondCountdownIntro(runId, startedAt);
    tenSecondCountdownTimer = window.setTimeout(() => {
      if (runId !== tenSecondCountdownRunId) return;
      tenSecondCountdownTimer = null;
      playTenSecondCountdownAudio();
    }, TIMEOUT_AUDIO_OFFSET_MS);
    window.setTimeout(() => {
      if (runId === tenSecondCountdownRunId) {
        tenSecondCountdownActive = false;
        renderRemote();
      }
    }, 10000);
    sendAction({ action: "ten_second_countdown" }, false).catch((error) => {
      console.warn("10 second countdown event failed", error);
    });
  });
}

function playFinishPromptSound(onComplete) {
  playPromptAudio(getFinishPromptAudio(), "Finish prompt").then(() => speak("请输入密码结束比赛", onComplete));
}

function renderPillars(count) {
  if (count <= 0) return "";
  if (count === 1) return `<span class="pillar yellow"></span>`;
  if (count === 2) return `<span class="pillar green"></span><span class="pillar green"></span>`;
  return `<span class="pillar green"></span><span class="pillar-x">x${count}</span>`;
}

function matchStatusText() {
  if (currentState?.matchFinished) return "\u6bd4\u8d5b\u7ed3\u675f";
  if (currentState?.running) return "\u6bd4\u8d5b\u4e2d";
  if (currentState?.timeExpired) return "\u65f6\u95f4\u5230";
  if (currentState?.timerStarted) return "\u6bd4\u8d5b\u6682\u505c";
  return "\u7b49\u5f85\u5f00\u59cb";
}

function resizeCelebrationCanvas(canvas) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.max(1, Math.floor(window.innerWidth * dpr));
  const height = Math.max(1, Math.floor(window.innerHeight * dpr));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  canvas.style.width = `${window.innerWidth}px`;
  canvas.style.height = `${window.innerHeight}px`;
  return dpr;
}

function addCelebrationBurst(canvas, dpr) {
  const winner = document.body.classList.contains("finish-white-winner") ? "white" : (document.body.classList.contains("finish-red-winner") ? "red" : "draw");
  const sideBias = winner === "red" ? 0.24 : (winner === "white" ? 0.76 : (Math.random() > 0.5 ? 0.24 : 0.76));
  const x = (sideBias + (Math.random() - 0.5) * 0.2) * canvas.width;
  const y = (0.14 + Math.random() * 0.26) * canvas.height;
  const colors = winner === "white"
    ? ["#ffffff", "#f4f4f4", "#ffd43b", "#9ee7ff"]
    : ["#ffd43b", "#fff2a6", "#ff3b3b", "#ffffff"];
  const particleCount = winner === "draw" ? 32 : 48;
  for (let index = 0; index < particleCount; index += 1) {
    const angle = Math.random() * Math.PI * 2;
    const speed = (1.2 + Math.random() * 3.8) * dpr;
    celebrationParticles.push({
      x,
      y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - (0.6 * dpr),
      life: 58 + Math.random() * 22,
      age: 0,
      size: (2 + Math.random() * 2.6) * dpr,
      color: colors[Math.floor(Math.random() * colors.length)],
    });
  }
}

function drawCelebrationFrame(timestamp) {
  const canvas = document.querySelector("[data-celebration-canvas]");
  if (!canvas || !document.body.classList.contains("finish-summary-active")) {
    stopCelebrationEffect();
    return;
  }
  const dpr = resizeCelebrationCanvas(canvas);
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  if (!celebrationLastFrameAt) celebrationLastFrameAt = timestamp;
  const delta = Math.min(2, Math.max(0.6, (timestamp - celebrationLastFrameAt) / 16.7));
  celebrationLastFrameAt = timestamp;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!celebrationLastBurstAt || timestamp - celebrationLastBurstAt > 620) {
    addCelebrationBurst(canvas, dpr);
    celebrationLastBurstAt = timestamp;
  }
  ctx.globalCompositeOperation = "lighter";
  celebrationParticles = celebrationParticles.filter((particle) => {
    particle.age += delta;
    particle.x += particle.vx * delta;
    particle.y += particle.vy * delta;
    particle.vy += 0.045 * dpr * delta;
    const opacity = Math.max(0, 1 - particle.age / particle.life);
    if (opacity <= 0) return false;
    ctx.globalAlpha = opacity;
    ctx.fillStyle = particle.color;
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, particle.size * opacity, 0, Math.PI * 2);
    ctx.fill();
    return true;
  });
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";
  celebrationAnimationFrame = requestAnimationFrame(drawCelebrationFrame);
}

function startCelebrationEffect() {
  if (!document.querySelector("[data-scoreboard]") || celebrationAnimationFrame) return;
  celebrationParticles = [];
  celebrationLastBurstAt = 0;
  celebrationLastFrameAt = 0;
  celebrationAnimationFrame = requestAnimationFrame(drawCelebrationFrame);
}

function stopCelebrationEffect() {
  if (celebrationAnimationFrame) {
    cancelAnimationFrame(celebrationAnimationFrame);
    celebrationAnimationFrame = null;
  }
  celebrationParticles = [];
  celebrationLastBurstAt = 0;
  celebrationLastFrameAt = 0;
  const canvas = document.querySelector("[data-celebration-canvas]");
  const ctx = canvas?.getContext("2d");
  if (canvas && ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
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
  const boardBody = document.body;
  const redScore = Number(currentState.redTotal) || 0;
  const whiteScore = Number(currentState.whiteTotal) || 0;
  boardBody.classList.toggle("finish-summary-active", Boolean(currentState.matchFinished));
  boardBody.classList.toggle("finish-red-winner", Boolean(currentState.matchFinished && redScore > whiteScore));
  boardBody.classList.toggle("finish-white-winner", Boolean(currentState.matchFinished && whiteScore > redScore));
  boardBody.classList.toggle("finish-draw", Boolean(currentState.matchFinished && redScore === whiteScore));
  if (currentState.matchFinished) {
    startCelebrationEffect();
  } else {
    stopCelebrationEffect();
  }
  const title = document.querySelector("[data-title]");
  title.textContent = currentState.title;
  title.classList.toggle("has-hangul", hasHangul(currentState.title));
  applyTitleColor(currentState.titleColor);
  applyTitleFontScale(currentState.titleFontScale);
  applyTableMarkerScale(currentState.tableMarkerAutoSize, currentState.tableMarkerScale);
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
  document.querySelector("[data-status]").textContent = matchStatusText();
  const courtName = document.querySelector("[data-court-name]");
  if (courtName) courtName.textContent = currentState.courtName || "红星门球场1";
  renderRecentLog();
  document.querySelector("[data-red-rows]").innerHTML = renderRows("red");
  document.querySelector("[data-white-rows]").innerHTML = renderRows("white");
  requestAnimationFrame(() => syncTableMarkerAutoSize(currentState.tableMarkerAutoSize, currentState.tableMarkerScale));
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
  const remoteLocked = remoteFinishPlaybackLocked;
  const remoteTitle = document.querySelector("[data-remote-title]");
  remoteTitle.textContent = currentState.title;
  remoteTitle.classList.toggle("has-hangul", hasHangul(currentState.title));
  const remoteTime = document.querySelector("[data-remote-time]");
  const remoteState = document.querySelector("[data-remote-state]");
  const remoteStatusTime = document.querySelector(".remote-status-time");
  if (remoteTime) remoteTime.textContent = formatTime(currentState.remainingSeconds);
  if (remoteState) remoteState.textContent = matchStatusText();
  if (remoteStatusTime) {
    remoteStatusTime.classList.toggle("is-running", currentState.running);
    remoteStatusTime.classList.toggle("is-waiting", !currentState.running && !currentState.timeExpired && !currentState.timerStarted);
    remoteStatusTime.classList.toggle("is-paused", !currentState.running && !currentState.timeExpired && currentState.timerStarted);
    remoteStatusTime.classList.toggle("is-expired", currentState.timeExpired);
  }
  const timerAction = document.querySelector("[data-action='toggle_timer']");
  if (timerAction) {
    timerAction.textContent = currentState.running ? "暂停" : (currentState.timerStarted && !currentState.timeExpired ? "继续" : "开始");
    timerAction.disabled = remoteLocked || currentState.matchFinished || (currentState.timeExpired && !currentState.running);
    timerAction.classList.toggle("disabled", remoteLocked || currentState.matchFinished || (currentState.timeExpired && !currentState.running));
  }
  const countdownAction = document.querySelector("[data-action='ten-second-countdown']");
  if (countdownAction) {
    countdownAction.textContent = tenSecondCountdownActive ? "⏰ 停止倒计时" : "⏰ 10秒倒计时";
  }
  setTeamName("[data-remote-status-red-team]", currentState.redTeam);
  setTeamName("[data-remote-status-white-team]", currentState.whiteTeam);
  document.querySelector("[data-remote-red-total]").textContent = currentState.redTotal;
  document.querySelector("[data-remote-white-total]").textContent = currentState.whiteTotal;
  document.querySelector(".remote-total-scoreline")?.classList.toggle("red-double-digit", Number(currentState.redTotal) >= 10);
  const showSelection = shouldShowBallSelection();
  document.querySelectorAll("[data-ball]").forEach((button) => {
    const number = Number(button.dataset.ball);
    const ball = currentState.balls.find((item) => item.number === number);
    button.disabled = remoteLocked;
    button.classList.toggle("active", showSelection && number === currentState.selectedBall);
    const badge = button.querySelector(".ball-score-badge");
    if (badge && ball) badge.textContent = String(ball.score);
  });
  document.querySelectorAll("[data-remote] .remote-actions button").forEach((button) => {
    button.disabled = remoteLocked;
    button.classList.toggle("remote-finish-locked", remoteLocked);
  });
  document.querySelectorAll("[data-remote] .results-link").forEach((link) => {
    link.classList.toggle("remote-finish-locked", remoteLocked);
    link.setAttribute("aria-disabled", remoteLocked ? "true" : "false");
  });
  renderRecentLog("[data-remote-recent-log]", 6);
  renderCountdownOverlay();
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

function estimatedServerTime() {
  const serverTime = Number(currentState?.serverTime);
  if (!Number.isFinite(serverTime)) return NaN;
  if (!currentStateReceivedAt) return serverTime;
  return serverTime + ((Date.now() - currentStateReceivedAt) / 1000);
}

function hasActiveCountdownOverlay() {
  const countdownId = currentState?.tenSecondCountdownId || "";
  const startedAt = Number(currentState?.tenSecondCountdownStartedAt);
  const serverTime = estimatedServerTime();
  if (!countdownId || !Number.isFinite(startedAt) || !Number.isFinite(serverTime)) return false;
  const elapsed = serverTime - startedAt;
  return elapsed >= 0 && elapsed < 10;
}

function stopCountdownOverlayTicker() {
  if (!countdownOverlayTimer) return;
  window.clearInterval(countdownOverlayTimer);
  countdownOverlayTimer = null;
}

function syncCountdownOverlayTicker() {
  if (!hasActiveCountdownOverlay()) {
    stopCountdownOverlayTicker();
    return;
  }
  if (countdownOverlayTimer) return;
  countdownOverlayTimer = window.setInterval(() => {
    renderCountdownOverlay();
    if (!hasActiveCountdownOverlay()) stopCountdownOverlayTicker();
  }, 100);
}

function renderCountdownOverlay() {
  const overlay = document.querySelector("[data-countdown-overlay]");
  const number = document.querySelector("[data-countdown-number]");
  if (!overlay || !number) return;
  const countdownId = currentState?.tenSecondCountdownId || "";
  const startedAt = Number(currentState?.tenSecondCountdownStartedAt);
  const serverTime = estimatedServerTime();
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
      playFinishSummary(currentState);
    } else if (latest.action === "timer_warning") {
      if (isFreshTimerWarning(latest)) {
        speakWithAlert(latest.message);
      }
    } else if (latest.action === "toggle_timer") {
      if (latest.message === "比赛开始") {
        cancelReadySpeech();
        playPromptAudio(getAlertPromptAudio(), "Alert prompt")
          .then(() => matchStartItems(currentState))
          .then((items) => playVoiceItems(items));
      } else {
        speakWithPromptForText(latest.message);
      }
    } else if (latest.action === "next_match") {
      scheduleReadySpeech();
    } else if (latest.action === "select") {
      speak(latest.message);
    } else {
      speakWithPromptForText(latest.message);
    }
  }
}

function cancelReadySpeech() {
  if (!readySpeechTimer) return;
  window.clearTimeout(readySpeechTimer);
  readySpeechTimer = null;
}

function scheduleReadySpeech() {
  cancelReadySpeech();
  readySpeechTimer = window.setTimeout(() => {
    readySpeechTimer = null;
    if (currentState?.running || currentState?.timerStarted) return;
    speak("等待开始");
  }, READY_SPEECH_DELAY_MS);
}

function renderSettings() {
  if (!currentState) return;
  const form = document.querySelector("[data-settings-form]");
  if (form && !settingsHydrated) {
    form.durationMinutes.value = Math.round(currentState.durationSeconds / 60);
    if (form.voiceProfile) form.voiceProfile.value = currentState.voiceProfile || "female";
    if (form.voicePlaybackRate) form.voicePlaybackRate.value = Number(currentState.voicePlaybackRate || DEFAULT_GAMEPLAY_PLAYBACK_RATE).toFixed(1);
    if (form.titleColor) form.titleColor.value = normalizeHexColor(currentState.titleColor);
    if (form.titleFontScale) form.titleFontScale.value = normalizeTitleFontScale(currentState.titleFontScale).toFixed(2);
    if (form.tableMarkerAutoSize) form.tableMarkerAutoSize.checked = currentState.tableMarkerAutoSize !== false;
    if (form.tableMarkerScale) form.tableMarkerScale.value = normalizeTableMarkerScale(currentState.tableMarkerScale).toFixed(2);
    updateVoicePlaybackRateOutput(form);
    updateTitleFontScaleOutput(form);
    updateTableMarkerScaleOutput(form);
    updateTableMarkerControls(form);
    if (form.weatherLocation) form.weatherLocation.value = currentState.weatherLocation || "";
    if (form.weatherLatitude) form.weatherLatitude.value = currentState.weatherLatitude ?? "";
    if (form.weatherLongitude) form.weatherLongitude.value = currentState.weatherLongitude ?? "";
    form.allowScoringWhenPaused.checked = currentState.allowScoringWhenPaused;
  }
  applyTitleColor(currentState.titleColor);
  applyTitleFontScale(currentState.titleFontScale);
  applyTableMarkerScale(currentState.tableMarkerAutoSize, currentState.tableMarkerScale);
  renderNetworkSettings();
  settingsHydrated = true;
}

function renderNetworkSettings() {
  const form = document.querySelector("[data-network-settings-form]");
  if (!form || !currentState || settingsHydrated) return;
  form.courtName.value = currentState.courtName || "红星门球场1";
  form.hotspotPassword.value = currentState.hotspotPassword || "12345678";
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

function switchSettingsTab(tabName) {
  document.querySelectorAll("[data-settings-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.settingsTab === tabName);
  });
  document.querySelectorAll("[data-settings-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.settingsPanel === tabName);
  });
  if (tabName === "network") loadNetworkStatus();
}

function setNetworkResult(text, isError = false, selector = "[data-network-result]") {
  const element = document.querySelector(selector);
  if (!element) return;
  element.textContent = text;
  element.classList.toggle("error", isError);
}

function renderNetworkStatus(status) {
  const box = document.querySelector("[data-network-status]");
  if (!box) return;
  const local = (status.localAddresses || []).map((address) => `http://${address}:8000`).join(" / ") || "未检测到";
  box.innerHTML = `
    <div><strong>球场：</strong>${escapeHtml(status.courtName || "红星门球场1")}</div>
    <div><strong>热点：</strong>${escapeHtml(status.hotspotSsid || status.courtName || "红星门球场1")}</div>
    <div><strong>固定入口：</strong>${escapeHtml(status.hotspotAddress || "http://menqiu.hongxing")}</div>
    <div><strong>备用地址：</strong>${escapeHtml(status.fallbackAddress || "http://192.168.50.1:8000")}</div>
    <div><strong>本机地址：</strong>${escapeHtml(local)}</div>
    <div><strong>外部 WiFi：</strong>${escapeHtml(status.activeWifi || "未连接")}</div>
    <div><strong>互联网：</strong>${status.internetOk ? "可用" : "不可用"}</div>
    <div><strong>系统网络配置：</strong>${status.supported ? "可用" : "仅树莓派/Linux nmcli 可用"}</div>
  `;
}

async function loadNetworkStatus() {
  if (!document.querySelector("[data-network-status]")) return;
  try {
    const status = await withTimeout(api.networkStatus(), 8000, "网络状态读取超时");
    lastNetworkStatus = status;
    if (status.ok === false) {
      setNetworkResult(status.message || "网络状态读取失败", true);
    } else {
      renderNetworkStatus(status);
    }
    networkStatusLoaded = true;
  } catch (error) {
    setNetworkResult("网络状态读取失败", true);
  }
}

function signalLabel(signal) {
  const value = Number(signal) || 0;
  if (value >= 75) return "强";
  if (value >= 45) return "中";
  return "弱";
}

function updateVoicePlaybackRateOutput(form) {
  const input = form?.voicePlaybackRate;
  const output = form?.querySelector?.("[data-voice-playback-rate-output]");
  if (!input || !output) return;
  const rate = Number(input.value || DEFAULT_GAMEPLAY_PLAYBACK_RATE);
  output.textContent = `${(Number.isFinite(rate) ? rate : DEFAULT_GAMEPLAY_PLAYBACK_RATE).toFixed(1)}x`;
}

function normalizeTitleFontScale(value) {
  const scale = Number(value);
  if (!Number.isFinite(scale)) return DEFAULT_TITLE_FONT_SCALE;
  return Math.min(1.4, Math.max(0.7, scale));
}

function updateTitleFontScaleOutput(form) {
  const input = form?.titleFontScale;
  const output = form?.querySelector?.("[data-title-font-scale-output]");
  if (!input || !output) return;
  const scale = normalizeTitleFontScale(input.value);
  output.textContent = `${Math.round(scale * 100)}%`;
}

function applyTitleFontScale(value) {
  const scale = normalizeTitleFontScale(value);
  document.documentElement.style.setProperty("--title-font-scale", scale.toFixed(2));
  document.querySelectorAll("[data-title]").forEach((title) => {
    title.style.removeProperty("font-size");
    const baseSize = parseFloat(window.getComputedStyle(title).fontSize);
    if (Number.isFinite(baseSize)) title.style.fontSize = `${Math.round(baseSize * scale)}px`;
  });
}

function previewScoreboardStyle(form) {
  if (!form) return;
  applyTitleColor(form.titleColor?.value);
  applyTitleFontScale(form.titleFontScale?.value);
  const autoSize = form.tableMarkerAutoSize?.checked !== false;
  const markerScale = normalizeTableMarkerScale(form.tableMarkerScale?.value);
  applyTableMarkerScale(autoSize, markerScale);
  updateTableMarkerControls(form);
  sendAction({
    action: "preview_title_style",
    titleColor: normalizeHexColor(form.titleColor?.value),
    titleFontScale: normalizeTitleFontScale(form.titleFontScale?.value),
    tableMarkerAutoSize: autoSize,
    tableMarkerScale: markerScale,
  }, false).catch(() => {});
}

function previewTitleStyle(form) {
  previewScoreboardStyle(form);
}

function stepTitleFontScale(form, delta) {
  const input = form?.titleFontScale;
  if (!input) return;
  const next = normalizeTitleFontScale(normalizeTitleFontScale(input.value) + delta);
  input.value = next.toFixed(2);
  updateTitleFontScaleOutput(form);
  previewTitleStyle(form);
}

function normalizeTableMarkerScale(value) {
  const scale = Number(value);
  if (!Number.isFinite(scale)) return DEFAULT_TABLE_MARKER_SCALE;
  return Math.min(1.8, Math.max(0.5, scale));
}

function updateTableMarkerScaleOutput(form) {
  const input = form?.tableMarkerScale;
  const output = form?.querySelector?.("[data-table-marker-scale-output]");
  if (!input || !output) return;
  const scale = normalizeTableMarkerScale(input.value);
  output.textContent = `${Math.round(scale * 100)}%`;
}

function updateTableMarkerControls(form) {
  const auto = form?.tableMarkerAutoSize?.checked !== false;
  form?.querySelectorAll?.("[data-action='table-marker-size-down'], [data-action='table-marker-size-up']").forEach((button) => {
    button.classList.toggle("auto-will-disable", auto);
    button.setAttribute("aria-pressed", auto ? "false" : "true");
  });
}

function applyTableMarkerScale(autoSize, value) {
  const scale = autoSize === false ? normalizeTableMarkerScale(value) : DEFAULT_TABLE_MARKER_SCALE;
  document.documentElement.style.setProperty("--table-marker-scale", scale.toFixed(2));
  syncTableMarkerAutoSize(autoSize, value);
  requestAnimationFrame(() => syncTableMarkerAutoSize(autoSize, value));
}

function setPxVariable(name, value) {
  if (Number.isFinite(value)) document.documentElement.style.setProperty(name, `${Math.round(value)}px`);
}

function setPxStyle(selector, property, value) {
  if (!Number.isFinite(value)) return;
  const text = `${Math.round(value)}px`;
  document.querySelectorAll(selector).forEach((element) => {
    element.style[property] = text;
  });
}

function syncTableMarkerAutoSize(autoSize = currentState?.tableMarkerAutoSize, value = currentState?.tableMarkerScale) {
  const body = document.querySelector(".tables tbody");
  if (!body) return;
  const rowHeight = body.getBoundingClientRect().height / 5;
  if (!Number.isFinite(rowHeight) || rowHeight <= 0) return;
  const scale = autoSize === false ? normalizeTableMarkerScale(value) : DEFAULT_TABLE_MARKER_SCALE;
  const slotSize = rowHeight * .92 * scale;
  const ballFontSize = Math.max(10, Math.min(92, rowHeight * .7 * scale));
  const scoreFontSize = Math.max(10, Math.min(92, rowHeight * .7 * scale));
  const pillarSize = Math.max(5, Math.min(42, rowHeight * .26 * scale));
  const pillarXSize = Math.max(9, Math.min(58, rowHeight * .44 * scale));
  setPxVariable("--table-slot-size", Math.max(8, Math.min(112, slotSize)));
  setPxVariable("--table-ball-font-size", ballFontSize);
  setPxVariable("--table-score-font-size", scoreFontSize);
  setPxVariable("--table-pillar-size", pillarSize);
  setPxVariable("--table-pillar-x-size", pillarXSize);
  setPxStyle(".tables .slot", "width", Math.max(8, Math.min(112, slotSize)));
  setPxStyle(".tables tbody th", "fontSize", ballFontSize);
  setPxStyle(".tables .score", "fontSize", scoreFontSize);
  setPxStyle(".tables .pillar", "width", pillarSize);
  setPxStyle(".tables .pillar-x", "fontSize", pillarXSize);
}

function previewTableMarkerStyle(form) {
  previewScoreboardStyle(form);
}

function stepTableMarkerScale(form, delta) {
  const input = form?.tableMarkerScale;
  if (!input) return;
  if (form.tableMarkerAutoSize) form.tableMarkerAutoSize.checked = false;
  const next = normalizeTableMarkerScale(normalizeTableMarkerScale(input.value) + delta);
  input.value = next.toFixed(2);
  updateTableMarkerScaleOutput(form);
  previewTableMarkerStyle(form);
}

function normalizeHexColor(value) {
  const color = String(value || "").trim();
  return /^#[0-9a-fA-F]{6}$/.test(color) ? color.toLowerCase() : DEFAULT_TITLE_COLOR;
}

function hexToRgb(color) {
  const normalized = normalizeHexColor(color).slice(1);
  return {
    r: parseInt(normalized.slice(0, 2), 16),
    g: parseInt(normalized.slice(2, 4), 16),
    b: parseInt(normalized.slice(4, 6), 16),
  };
}

function applyTitleColor(color) {
  const normalized = normalizeHexColor(color);
  const { r, g, b } = hexToRgb(normalized);
  document.documentElement.style.setProperty("--title-color", normalized);
  document.documentElement.style.setProperty("--title-stroke-color", `rgba(${Math.min(255, r + 35)}, ${Math.min(255, g + 35)}, ${Math.min(255, b + 35)}, .9)`);
  document.documentElement.style.setProperty("--title-glow-tight", `rgba(${Math.min(255, r + 55)}, ${Math.min(255, g + 55)}, ${Math.min(255, b + 55)}, 1)`);
  document.documentElement.style.setProperty("--title-glow-mid", `rgba(${r}, ${g}, ${b}, .86)`);
  document.documentElement.style.setProperty("--title-glow-wide", `rgba(${r}, ${g}, ${b}, .42)`);
}

async function scanWifiNetworks() {
  const list = document.querySelector("[data-wifi-list]");
  if (!list) return;
  if (wifiScanInFlight) return;
  const button = document.querySelector("[data-action='scan-wifi']");
  const originalText = button?.textContent || "查找 WiFi 网络";
  wifiScanInFlight = true;
  if (button) {
    button.disabled = true;
    button.textContent = "正在查找...";
  }
  list.innerHTML = `<div class="weather-search-empty">正在查找 WiFi 网络...</div>`;
  setNetworkResult("");
  try {
    if (!networkStatusLoaded || !lastNetworkStatus) await loadNetworkStatus();
    if (lastNetworkStatus?.ok === false) {
      list.innerHTML = `<div class="weather-search-empty">${escapeHtml(lastNetworkStatus.message || "网络接口不可用，请重启服务")}</div>`;
      return;
    }
    if (lastNetworkStatus && !lastNetworkStatus.supported) {
      list.innerHTML = `<div class="weather-search-empty">当前系统不支持 WiFi 扫描。树莓派/Linux 安装 nmcli 后可用。</div>`;
      return;
    }
    const data = await withTimeout(api.networkScan(), 22000, "WiFi 扫描超时，请稍后重试");
    if (!data.ok) {
      list.innerHTML = `<div class="weather-search-empty">${escapeHtml(data.message || "WiFi 扫描失败")}</div>`;
      return;
    }
    if (!data.networks?.length) {
      list.innerHTML = `<div class="weather-search-empty">没有找到 WiFi 信号</div>`;
      return;
    }
    list.innerHTML = data.networks.map((network) => `
      <button class="wifi-option" type="button" data-action="select-wifi" data-ssid="${escapeHtml(network.ssid)}">
        <span>${escapeHtml(network.ssid)}</span>
        <span class="wifi-signal">${signalLabel(network.signal)} ${Number(network.signal) || 0}%</span>
      </button>
    `).join("");
  } catch (error) {
    list.innerHTML = `<div class="weather-search-empty">${escapeHtml(error.message || "WiFi 扫描失败")}</div>`;
  } finally {
    wifiScanInFlight = false;
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

function selectWifiNetwork(target) {
  document.querySelectorAll(".wifi-option").forEach((button) => button.classList.remove("active"));
  target.classList.add("active");
  const input = document.querySelector("[data-wifi-ssid]");
  if (input) input.value = target.dataset.ssid || "";
  document.querySelector("[data-wifi-password]")?.focus();
}

function collectNetworkSettingsPayload(form) {
  const courtName = form.courtName?.value.trim() || "红星门球场1";
  return {
    action: "update_settings",
    courtName,
    hotspotSsid: courtName,
    hotspotPassword: form.hotspotPassword?.value || "",
  };
}

function validateNetworkSettings(form) {
  const result = document.querySelector("[data-network-save-result]");
  if (result) {
    result.textContent = "";
    result.classList.remove("error");
  }
  const password = form.hotspotPassword?.value.trim() || "";
  if (password.length < 8) {
    if (result) {
      result.textContent = "热点密码至少 8 位";
      result.classList.add("error");
    }
    form.hotspotPassword?.focus();
    return false;
  }
  return true;
}

async function connectSelectedWifi() {
  const ssid = document.querySelector("[data-wifi-ssid]")?.value.trim() || "";
  const password = document.querySelector("[data-wifi-password]")?.value || "";
  if (wifiConnectInFlight) return;
  if (!ssid) {
    setNetworkResult("请先选择 WiFi", true);
    return;
  }
  const button = document.querySelector("[data-action='connect-wifi']");
  const originalText = button?.textContent || "连接 WiFi";
  wifiConnectInFlight = true;
  if (button) {
    button.disabled = true;
    button.textContent = "正在连接...";
  }
  setNetworkResult("正在连接 WiFi...");
  try {
    const result = await withTimeout(api.networkConnect({ ssid, password }), 45000, "WiFi 连接超时，热点会继续保留");
    setNetworkResult(result.message || (result.ok ? "WiFi 连接成功" : "WiFi 连接失败"), !result.ok);
    loadNetworkStatus();
  } catch (error) {
    setNetworkResult(error.message || "WiFi 连接失败，热点会继续保留", true);
  } finally {
    wifiConnectInFlight = false;
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
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
  if (body) body.innerHTML = `<tr><td colspan="6">${escapeHtml(message)}</td></tr>`;
}

async function selectResultDate(date) {
  selectedResultsDate = date;
  renderResultsCalendar();
  const title = document.querySelector("[data-selected-date-title]");
  if (title) title.textContent = date;
  const body = document.querySelector("[data-results-day-body]");
  if (!body) return;
  body.innerHTML = `<tr><td colspan="6">正在读取...</td></tr>`;
  const data = await api.resultsDay(date);
  const matches = data.matches || [];
  if (!matches.length) {
    renderResultsEmptyDay("当天没有比赛记录");
    return;
  }
  body.innerHTML = matches.map((match, index) => `
    <tr class="result-row" data-action="open-result-match" data-match-id="${match.id}">
      <td class="result-seq-cell">${index + 1}</td>
      <td class="result-time-cell">${resultTime(match.ended_at)}</td>
      <td class="ellipsis">${escapeHtml(match.red_team || "红队")}</td>
      <td class="score-cell">${match.red_score}</td>
      <td class="score-cell white-score-text">${match.white_score}</td>
      <td class="ellipsis">${escapeHtml(match.white_team || "白队")}</td>
    </tr>
  `).join("");
}

function ballStepLabel(step) {
  return ["0分", "一门", "二门", "三门"][Number(step)] || "0分";
}

function renderDetailTeamTable(team, title, balls) {
  return `
    <section class="detail-team-table ${team}-detail-table">
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
              <th><span class="detail-ball-number">${ball.number}</span></th>
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
      <div class="red-detail-score"><span>${escapeHtml(match.red_team || "红队")}</span><strong>${match.red_score}</strong></div>
      <b>:</b>
      <div class="white-detail-score"><span>${escapeHtml(match.white_team || "白队")}</span><strong>${match.white_score}</strong></div>
    </section>
    <div class="detail-tables">
      ${renderDetailTeamTable("red", "红队", redBalls)}
      ${renderDetailTeamTable("white", "白队", whiteBalls)}
    </div>
  `;
  dialog.classList.add("open");
}

function closeResultDetail() {
  document.querySelector("[data-result-detail-dialog]")?.classList.remove("open");
}

function shouldTransitionBetweenStates(previousState, nextState, options = {}) {
  if (options.skipTransition || matchTransitionInFlight) return false;
  if (!previousState || !nextState) return false;
  return previousState.matchFinished
    && !nextState.matchFinished
    && !nextState.running
    && !nextState.timerStarted
    && Number(nextState.matchNumber || 0) > Number(previousState.matchNumber || 0);
}

function renderState(options = {}) {
  currentStateReceivedAt = Date.now();
  if (document.querySelector("[data-scoreboard]")) renderScoreboard();
  if (document.querySelector("[data-remote]")) renderRemote();
  if (document.querySelector("[data-settings-form]")) renderSettings();
  renderKeyBindings();
  syncCountdownOverlayTicker();
  if (options.speakEvents !== false) autoSpeakServerEvents();
}

function applyState(state, options = {}) {
  const previousState = currentState;
  if (shouldTransitionBetweenStates(previousState, state, options)) {
    runMatchTransition(() => {
      currentState = state;
      renderState(options);
    });
    return;
  }
  currentState = state;
  renderState(options);
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

function startStylePreviewPolling() {
  if (!document.querySelector("[data-scoreboard]") || stylePreviewTimer) return;
  stylePreviewTimer = window.setInterval(async () => {
    try {
      const state = await api.state();
      if (!currentState) {
        applyState(state, { speakEvents: false });
        return;
      }
      const changed = state.titleColor !== currentState.titleColor
        || state.titleFontScale !== currentState.titleFontScale
        || state.tableMarkerAutoSize !== currentState.tableMarkerAutoSize
        || state.tableMarkerScale !== currentState.tableMarkerScale;
      if (changed) applyState(state, { speakEvents: false, skipTransition: true });
    } catch (error) {
      return;
    }
  }, 300);
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

async function sendAction(payload, shouldSpeak = true, applyOptions = {}) {
  const result = await api.action(payload);
  if (!applyOptions.noApply) {
    applyState(result.state, { speakEvents: false, ...applyOptions });
  }
  if (shouldSpeak) {
    if (payload.action === "toggle_timer") {
      if (result.message === "比赛开始") {
        cancelReadySpeech();
        playPromptAudio(getAlertPromptAudio(), "Alert prompt")
          .then(() => matchStartItems(result.state || currentState))
          .then((items) => playVoiceItems(items));
      } else {
        speakWithPromptForText(result.message);
      }
    } else if (payload.action === "select") {
      speak(result.message);
    } else {
      speakWithPromptForText(result.message);
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
  playFinishPromptSound();
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
    durationMinutes: form.durationMinutes.value,
    voiceProfile: form.voiceProfile?.value || "female",
    voicePlaybackRate: form.voicePlaybackRate?.value || DEFAULT_GAMEPLAY_PLAYBACK_RATE,
    titleColor: normalizeHexColor(form.titleColor?.value),
    titleFontScale: normalizeTitleFontScale(form.titleFontScale?.value),
    tableMarkerAutoSize: form.tableMarkerAutoSize?.checked !== false,
    tableMarkerScale: normalizeTableMarkerScale(form.tableMarkerScale?.value),
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
  precacheTeamNameAudio(editTeamTarget, name);
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
  const wasAlreadyFinished = Boolean(currentState?.matchFinished);
  const resultEl = document.querySelector("[data-finish-result]");
  if (resultEl) {
    resultEl.textContent = "正在检查...";
    resultEl.classList.remove("error");
  }
  try {
    const result = await sendAction({ action: "finish", password: finishPassword }, false);
    if (result.ok) {
      const snapshot = result.finishedMatch || currentState;
      closeFinishDialog();
      if (wasAlreadyFinished) {
        finishVerifyInFlight = false;
        finishPassword = "";
        advanceToNextMatchWithTransition();
      } else {
        playFinishThenAdvance(snapshot, { openingKey: "match_finished" });
      }
    } else {
      finishVerifyInFlight = false;
      finishPassword = "";
      speakWithError("密码错误");
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
    playPromptAudio(getErrorPromptAudio(), "Error prompt");
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
  if (remoteFinishPlaybackLocked && document.querySelector("[data-remote]") && event.target.closest(".results-link")) {
    event.preventDefault();
    return;
  }
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  if (remoteFinishPlaybackLocked && document.querySelector("[data-remote]")) {
    event.preventDefault();
    return;
  }
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
  if (action === "settings-tab") return switchSettingsTab(target.dataset.settingsTab || "general");
  if (action === "scan-wifi") return scanWifiNetworks();
  if (action === "select-wifi") return selectWifiNetwork(target);
  if (action === "connect-wifi") return connectSelectedWifi();
  if (action === "capture-key-binding") {
    keyCaptureAction = target.dataset.bindingAction || "";
    renderKeyBindings();
    return;
  }
  if (action === "reset-title-color") {
    const form = target.closest("[data-settings-form]");
    if (form?.titleColor) {
      form.titleColor.value = DEFAULT_TITLE_COLOR;
      previewTitleStyle(form);
    }
    return;
  }
  if (action === "title-size-down") {
    stepTitleFontScale(target.closest("[data-settings-form]"), -0.05);
    return;
  }
  if (action === "title-size-up") {
    stepTitleFontScale(target.closest("[data-settings-form]"), 0.05);
    return;
  }
  if (action === "table-marker-size-down") {
    stepTableMarkerScale(target.closest("[data-settings-form]"), -0.05);
    return;
  }
  if (action === "table-marker-size-up") {
    stepTableMarkerScale(target.closest("[data-settings-form]"), 0.05);
    return;
  }
  if (action === "confirm-swap-team") return confirmSwapTeam();
  if (action === "toggle_timer" && (currentState?.matchFinished || (currentState?.timeExpired && !currentState?.running))) return;
  const payload = { action };
  if (target.dataset.ball) payload.ball = Number(target.dataset.ball);
  sendAction(payload);
});

document.addEventListener("input", (event) => {
  const rateInput = event.target.closest("input[name='voicePlaybackRate']");
  if (rateInput) updateVoicePlaybackRateOutput(rateInput.form);

  const titleColorInput = event.target.closest("input[name='titleColor']");
  if (titleColorInput) previewTitleStyle(titleColorInput.form);

  const tableMarkerAutoInput = event.target.closest("input[name='tableMarkerAutoSize']");
  if (tableMarkerAutoInput) {
    updateTableMarkerControls(tableMarkerAutoInput.form);
    previewTableMarkerStyle(tableMarkerAutoInput.form);
  }

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
  vibrateRemoteTap(event);
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

  const networkForm = event.target.closest("[data-network-settings-form]");
  if (networkForm) {
    event.preventDefault();
    if (!validateNetworkSettings(networkForm)) return;
    openSettingsSavePasswordDialog(collectNetworkSettingsPayload(networkForm));
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

window.addEventListener("resize", () => {
  if (currentState?.titleFontScale) applyTitleFontScale(currentState.titleFontScale);
  syncTableMarkerAutoSize(currentState?.tableMarkerAutoSize, currentState?.tableMarkerScale);
});

initScreenWakeLock();
initResultsPage();
startStateEvents();
startStylePreviewPolling();
