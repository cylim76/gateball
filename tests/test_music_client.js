const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const source = fs.readFileSync(path.join(__dirname, "../web/static/app.js"), "utf8");

function functionSource(name) {
  const match = new RegExp(`(?:async )?function ${name}\\(`).exec(source);
  assert.ok(match, `missing ${name}`);
  const rest = source.slice(match.index);
  const end = /\n(?:async )?function /.exec(rest);
  return end ? rest.slice(0, end.index) : rest;
}

function runFunctions(context, ...names) {
  vm.createContext(context);
  for (const name of names) vm.runInContext(functionSource(name), context);
  return context;
}

function musicFixture() {
  const directory = { id: "dir:project:Sunday", type: "directory", name: "Sunday", source: "project" };
  const first = { id: "project:Sunday/01.mp3", type: "track", name: "Sunday/01.mp3", url: "/music/01.mp3" };
  const second = { id: "project:Sunday/02.mp3", type: "track", name: "Sunday/02.mp3", url: "/music/02.mp3" };
  return { directory, first, second };
}

test("saving a chosen music directory keeps the directory as the playlist", () => {
  const { directory, first, second } = musicFixture();
  const form = {
    classList: { contains: () => true },
    selectedMusicTrack: { value: directory.id },
    musicMode: { value: "sequence" },
  };
  const context = runFunctions({
    musicItems: [directory, first, second],
    musicTracks: [first, second],
    musicTracksLoaded: true,
    normalizeMusicVolumePercent: Number,
    normalizeMusicDuckPercent: Number,
  }, "musicItemForId", "musicTrackIdFromForm", "collectSettingsPayload");

  assert.equal(context.musicTrackIdFromForm(form), directory.id);
  const payload = context.collectSettingsPayload(form);
  assert.equal(payload.selectedMusicItem, directory.id);
  assert.equal(payload.musicMode, "sequence");
});

test("reopening music settings shows the chosen directory, not its first track", () => {
  const { directory, first, second } = musicFixture();
  const select = {
    options: [], _value: first.id,
    replaceChildren() { this.options = []; this._value = ""; },
    appendChild(option) { this.options.push(option); },
    get value() { return this._value; },
    set value(value) { this._value = this.options.some(option => option.value === value) ? value : ""; },
  };
  const form = { selectedMusicTrack: select };
  const context = runFunctions({
    currentState: { selectedMusicItem: directory.id, selectedMusicTrack: first.id },
    musicItems: [directory, first, second],
    settingsHydrated: true,
    musicSelectedItemDraft: null,
    document: {
      querySelectorAll: () => [form],
      createElement: () => ({ value: "", textContent: "" }),
    },
    syncMusicModeRadios() {},
    updateMusicOutput() {},
  }, "renderMusicSettings");

  context.renderMusicSettings();
  assert.equal(select.value, directory.id);
});

test("the test button reflects only the separate test player", () => {
  const button = { textContent: "", disabled: false };
  const form = {
    selectedMusicTrack: { value: "project:Sunday/01.mp3" },
    querySelector(selector) { return selector === "[data-action='test-music']" ? button : null; },
  };
  const context = runFunctions({
    musicAudio: { paused: false },
    musicTestAudio: null,
    musicTestPlaying: false,
    musicItems: [{ id: form.selectedMusicTrack.value, type: "track" }],
    normalizeMusicVolumePercent: Number,
    normalizeMusicDuckPercent: Number,
    musicTestTrackFromForm: () => ({ id: form.selectedMusicTrack.value }),
    musicItemForId: () => null,
    selectedMusicTrack: () => null,
  }, "updateMusicOutput");

  context.updateMusicOutput(form);
  assert.equal(button.textContent, "本机试听");
  assert.equal(button.disabled, false);

  context.musicTestAudio = { paused: false };
  context.musicTestPlaying = true;
  context.updateMusicOutput(form);
  assert.equal(button.textContent, "停止本机试听");
});

test("saved music volume and speech ducking set audible browser volume", () => {
  const audio = { volume: 0 };
  const context = runFunctions({
    currentState: { musicVolumePercent: 60, musicDuckPercent: 25, musicDuckDuringSpeech: true, musicDuckingUntil: 0 },
    musicDuckDepth: 0,
    musicAudio: audio,
    serverNowSeconds: () => 100,
  }, "normalizeMusicVolumePercent", "normalizeMusicDuckPercent", "musicBaseVolumeMultiplier", "musicEffectiveVolume", "applyMusicVolume");

  context.applyMusicVolume();
  assert.equal(audio.volume, 0.6);
  context.musicDuckDepth = 1;
  context.applyMusicVolume();
  assert.equal(audio.volume, 0.15);
  context.currentState.musicVolumePercent = 0;
  context.applyMusicVolume();
  assert.equal(audio.volume, 0);
});

test("remote settings cannot start normal music on the phone", () => {
  const { first } = musicFixture();
  let audioConstructions = 0;
  const context = runFunctions({
    currentState: { musicEnabled: true, musicPlaying: true, selectedMusicTrack: first.id },
    musicTracksLoaded: true,
    musicTracks: [first],
    lastSyncedSelectedMusicTrack: "",
    lastMusicTrackId: "",
    musicAudio: null,
    musicTestPlaying: false,
    document: {
      querySelector(selector) {
        if (selector === "[data-remote]" || selector === "[data-settings-form]") return {};
        return null;
      },
    },
    Audio: class { constructor() { audioConstructions++; } },
    selectedMusicTrack: () => first,
    stopMusicPlayback() {},
    applyMusicVolume() {},
    updateMusicOutput() {},
    URL,
    window: { location: { href: "http://gb1/remote" } },
  }, "startMusicPlayback", "syncMusicPlayback");

  context.syncMusicPlayback();
  context.startMusicPlayback(first);
  assert.equal(audioConstructions, 0);
});

test("track end asks the server to advance instead of replaying a stale local choice", async () => {
  const { first, second } = musicFixture();
  const actions = [];
  let release;
  let syncs = 0;
  const context = runFunctions({
    currentState: { musicEnabled: true, musicPlaying: true, musicMode: "sequence", selectedMusicTrack: first.id, musicPlaybackEpoch: 4 },
    musicTrackEndInFlight: false,
    musicAdvanceRetryAfter: 0,
    musicAdvanceRetryTimer: null,
    lastMusicTrackId: first.id,
    lastMusicPlaybackEpoch: 4,
    musicProgressTask: Promise.resolve(),
    api: { action(payload) { actions.push(payload); return new Promise(resolve => { release = resolve; }); } },
    withTimeout: pending => pending,
    applyState(state) { context.currentState = state; },
    stopMusicProgressTimer() {},
    syncMusicPlayback() { syncs++; },
    nextMusicTrack() { throw new Error("local playlist advancement is stale"); },
    document: { querySelector: selector => selector === "[data-scoreboard]" ? {} : null },
    window: { setTimeout() {} },
  }, "handleMusicEnded");

  const pending = context.handleMusicEnded();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(actions.length, 1);
  assert.equal(actions[0].action, "music_track_ended");
  assert.equal(actions[0].trackId, first.id);
  assert.equal(actions[0].musicPlaybackEpoch, 4);
  assert.equal(context.currentState.selectedMusicTrack, first.id);
  assert.equal(syncs, 0);
  release({ ok: true, state: { selectedMusicTrack: second.id, musicPlaybackEpoch: 5, musicPlaying: true } });
  await pending;
  assert.equal(context.currentState.selectedMusicTrack, second.id);
  assert.equal(syncs, 1);
});

test("single-track repeat reports each natural end to reset the saved position", async () => {
  const { first } = musicFixture();
  const actions = [];
  const context = runFunctions({
    currentState: { musicPlaying: true, musicMode: "loop", selectedMusicTrack: first.id, musicPlaybackEpoch: 8 },
    lastMusicTrackId: first.id,
    lastMusicPlaybackEpoch: 8,
    musicTrackEndInFlight: false,
    musicAdvanceRetryAfter: 0,
    musicAdvanceRetryTimer: null,
    musicProgressTask: Promise.resolve(),
    document: { querySelector: selector => selector === "[data-scoreboard]" ? {} : null },
    stopMusicProgressTimer() {},
    syncMusicPlayback() {},
    api: { action(payload) { actions.push(payload); return Promise.resolve({ ok: true, state: { musicPlaying: true, musicMode: "loop", selectedMusicTrack: first.id, musicPlaybackEpoch: 9, musicPositionSeconds: 0 } }); } },
    withTimeout: pending => pending,
    applyState(state) { context.currentState = state; },
    window: { setTimeout() {} },
  }, "handleMusicEnded");

  await context.handleMusicEnded();
  assert.equal(actions.length, 1);
  assert.equal(actions[0].action, "music_track_ended");
  assert.equal(actions[0].musicPlaybackEpoch, 8);
  assert.equal(context.currentState.musicPositionSeconds, 0);
  assert.equal(context.currentState.musicPlaybackEpoch, 9);
});

test("saved playback position is restored once when track metadata arrives", () => {
  const { first } = musicFixture();
  const listeners = new Map();
  let loadCount = 0;
  let playCount = 0;
  let actualSrc = "";
  const audio = {
    paused: true, currentTime: 0, duration: 300, loop: true,
    get src() { return actualSrc; },
    set src(value) { actualSrc = new URL(value, "http://gb1/scoreboard").href; },
    addEventListener(name, listener) {
      if (!listeners.has(name)) listeners.set(name, new Set());
      listeners.get(name).add(listener);
    },
    removeEventListener(name, listener) { listeners.get(name)?.delete(listener); },
    load() { loadCount++; },
    fire(name) { for (const listener of [...(listeners.get(name) || [])]) listener(); },
  };
  const context = runFunctions({
    currentState: { musicEnabled: true, musicPlaying: true, selectedMusicTrack: first.id, musicPositionSeconds: 123, musicPlaybackEpoch: 7 },
    musicPendingStartKey: "",
    musicPlaybackBlockedTrackId: "",
    lastMusicTrackId: "",
    lastMusicPlaybackEpoch: 0,
    musicAudio: audio,
    document: { querySelector: selector => selector === "[data-scoreboard]" ? {} : null },
    window: { location: { href: "http://gb1/scoreboard" } },
    URL,
    getMusicAudio: () => audio,
    stopMusicProgressTimer() {},
    applyMusicVolume() {},
    playMusicAudio() { playCount++; },
    startMusicProgressTimer() {},
  }, "startMusicPlayback");

  context.startMusicPlayback(first);
  assert.equal(loadCount, 1);
  assert.equal(audio.currentTime, 0);
  assert.equal(audio.loop, false);
  audio.fire("loadedmetadata");
  assert.equal(audio.currentTime, 123);
  assert.equal(playCount, 1);
  audio.currentTime = 140;
  audio.fire("loadedmetadata");
  context.startMusicPlayback(first);
  assert.equal(audio.currentTime, 140);
  assert.equal(loadCount, 1);
});

test("progress carries its playback epoch and stale epochs are not submitted", async () => {
  const { first } = musicFixture();
  const actions = [];
  const context = runFunctions({
    currentState: { selectedMusicTrack: first.id, musicPlaybackEpoch: 11 },
    musicAudio: { currentTime: 88.5, ended: false },
    lastMusicTrackId: first.id,
    lastMusicPlaybackEpoch: 11,
    musicTrackEndInFlight: false,
    musicPendingStartKey: "",
    musicProgressTask: Promise.resolve(),
    document: { querySelector: selector => selector === "[data-scoreboard]" ? {} : null },
    api: { action(payload) { actions.push(payload); return Promise.resolve({ ok: true }); } },
    withTimeout: pending => pending,
  }, "musicProgressPayload", "sendMusicProgress");

  await context.sendMusicProgress();
  assert.equal(actions.length, 1);
  assert.equal(actions[0].trackId, first.id);
  assert.equal(actions[0].positionSeconds, 88.5);
  assert.equal(actions[0].musicPlaybackEpoch, 11);

  context.currentState.musicPlaybackEpoch = 12;
  await context.sendMusicProgress();
  assert.equal(actions.length, 1);
});

test("failed local music test clears the test state without pausing live music", async () => {
  const { first } = musicFixture();
  const button = { textContent: "", disabled: false };
  const result = { textContent: "", classList: { add() {} } };
  const form = {
    selectedMusicTrack: { value: first.id },
    musicVolumePercent: { value: "40" },
    querySelector(selector) {
      if (selector === "[data-action='test-music']") return button;
      if (selector === "[data-music-save-result]") return result;
      return null;
    },
  };
  let normalPauses = 0;
  let testPauses = 0;
  const testAudio = {
    paused: true, currentTime: 0,
    pause() { testPauses++; this.paused = true; },
    play() { this.paused = false; return Promise.reject(new Error("autoplay denied")); },
  };
  const context = runFunctions({
    musicAudio: { paused: false, pause() { normalPauses++; } },
    musicTestAudio: testAudio,
    musicTestPlaying: false,
    musicTestTrackId: "",
    musicTestGeneration: 0,
    remoteSettingsDialogOpen: true,
    settingsToken: "valid",
    currentState: {},
    musicTestTrackFromForm: () => first,
    getMusicTestAudio() { context.musicTestAudio = testAudio; return testAudio; },
    musicSettingsForm: () => form,
    musicItemForId: () => null,
    selectedMusicTrack: () => null,
    normalizeMusicVolumePercent: Number,
    normalizeMusicDuckPercent: Number,
    console: { warn() {} },
  }, "updateMusicOutput", "stopMusicTest", "showMusicTestError", "startMusicTest");

  context.startMusicTest(form);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(context.musicTestPlaying, false);
  assert.equal(testAudio.paused, true);
  assert.ok(testPauses >= 2);
  assert.equal(normalPauses, 0);
  assert.equal(button.textContent, "本机试听");
  assert.match(result.textContent, /试听失败/);
});

test("a late failure from an earlier test must not stop a restarted test of the same song", async () => {
  const { first } = musicFixture();
  const pendingPlays = [];
  const audios = [];
  const button = { textContent: "", disabled: false };
  const result = { textContent: "", classList: { add() {} } };
  const form = {
    selectedMusicTrack: { value: first.id },
    musicVolumePercent: { value: "40" },
    querySelector(selector) {
      if (selector === "[data-action='test-music']") return button;
      if (selector === "[data-music-save-result]") return result;
      return null;
    },
  };
  const context = runFunctions({
    musicAudio: null,
    musicTestAudio: null,
    musicTestPlaying: false,
    musicTestTrackId: "",
    musicTestGeneration: 0,
    remoteSettingsDialogOpen: true,
    settingsToken: "valid",
    currentState: {},
    musicTestTrackFromForm: () => first,
    getMusicTestAudio() {
      const audio = {
        paused: true, currentTime: 0,
        pause() { this.paused = true; },
        play() {
          this.paused = false;
          return new Promise((resolve, reject) => pendingPlays.push({ resolve, reject }));
        },
      };
      audios.push(audio);
      context.musicTestAudio = audio;
      return audio;
    },
    musicSettingsForm: () => form,
    musicItemForId: () => null,
    selectedMusicTrack: () => null,
    normalizeMusicVolumePercent: Number,
    normalizeMusicDuckPercent: Number,
    console: { warn() {} },
  }, "updateMusicOutput", "stopMusicTest", "startMusicTest");

  context.startMusicTest(form);
  context.stopMusicTest();
  context.startMusicTest(form);
  pendingPlays[0].reject(new Error("first attempt blocked"));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(context.musicTestPlaying, true);
  assert.equal(audios[0].paused, true);
  assert.equal(audios[1].paused, false);
  assert.equal(button.textContent, "停止本机试听");
  assert.equal(result.textContent, "");
  pendingPlays[1].resolve();
});

test("closing settings stops an active local music test", async () => {
  let stopped = 0;
  const context = runFunctions({
    settingsToken: "",
    settingsReturnTarget: "remote",
    cancelPendingRfLearn() {},
    stopMusicTest() { stopped++; },
    restoreSavedAppearance() {},
    clearRfLearnPolling() {},
    clearRfLearnTimeout() {},
    rememberSettingsToken() {},
    document: { querySelector: () => null, querySelectorAll: () => [] },
  }, "expireSettingsSession", "closeRemoteSettingsDialog");

  await context.closeRemoteSettingsDialog();
  assert.equal(stopped, 1);
});
