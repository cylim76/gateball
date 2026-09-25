const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const source = fs.readFileSync(path.join(__dirname, "../web/static/app.js"), "utf8");

function functionSource(name) {
  const match = new RegExp(`(?:async )?function ${name}\\(`).exec(source);
  assert.ok(match, name);
  const rest = source.slice(match.index);
  const end = /\n(?:async )?function /.exec(rest);
  return end ? rest.slice(0, end.index) : rest;
}

test("keyboard rows update only when bindings or capture state change", () => {
  let replacements = 0;
  const list = { replaceChildren() { replacements++; }, appendChild() {} };
  const context = {
    remoteSettingsDialogOpen: true, currentState: { keyBindings: {} }, keyCaptureAction: "",
    renderedKeyBindings: new WeakMap(), keyboardBindableActions: [{ id: "ball_1" }],
    renderRfActionVisual: () => "1", bindingForSpec: () => ({ label: "1" }),
    document: { querySelectorAll: () => [list], createElement: () => ({ dataset: {}, append() {} }) },
  };
  vm.createContext(context);
  vm.runInContext(functionSource("renderKeyBindings"), context);
  for (let i = 0; i < 20; i++) context.renderKeyBindings();
  assert.equal(replacements, 1);
  context.keyCaptureAction = "ball_1";
  context.renderKeyBindings();
  assert.equal(replacements, 2);
  context.currentState.keyBindings = { ball_1: { key: "a" } };
  context.renderKeyBindings();
  assert.equal(replacements, 3);
  context.remoteSettingsDialogOpen = false;
  context.keyCaptureAction = "";
  context.renderKeyBindings();
  assert.equal(replacements, 3);
});

function loginContext(reply) {
  const events = [];
  const context = {
    settingsDialogOpen: true, settingsEntryInFlight: false, settingsEntryAttempt: 0,
    settingsPassword: "123", settingsPasswordLength: () => 4,
    document: { querySelector: () => null },
    api: { settingsLogin: async () => { events.push("login"); return reply; }, settingsLogout: async () => events.push("revoke") },
    closeSettingsDialog() { context.settingsDialogOpen = false; events.push("close"); },
    rememberSettingsToken: () => events.push("token"), enterSettings: () => events.push("enter"),
    speakWithError: () => events.push("wrong"), playPromptAudio: () => events.push("error"), getErrorPromptAudio() {},
  };
  vm.createContext(context);
  vm.runInContext(functionSource("tryEnterSettings"), context);
  return { context, events };
}

test("full-length correct password enters automatically; partial input waits", async () => {
  const { context, events } = loginContext({ ok: true, token: "test-token" });
  await context.tryEnterSettings();
  assert.deepEqual(events, []);
  context.settingsPassword = "1234";
  await context.tryEnterSettings();
  assert.deepEqual(events, ["login", "close", "token", "enter"]);
});

test("wrong password closes the dialog", async () => {
  const { context, events } = loginContext({ ok: false });
  context.settingsPassword = "1111";
  await context.tryEnterSettings();
  assert.deepEqual(events, ["login", "close", "wrong"]);
});

test("cancelled verification cannot reopen settings when a late reply arrives", async () => {
  const { context, events } = loginContext({ ok: true, token: "late-token" });
  let resolve;
  context.api.settingsLogin = () => new Promise(done => { resolve = done; });
  context.settingsPassword = "1234";
  const pending = context.tryEnterSettings();
  context.settingsEntryAttempt += 1;
  context.settingsDialogOpen = false;
  resolve({ ok: true, token: "late-token" });
  await pending;
  assert.deepEqual(events, ["revoke"]);
});

test("public password lengths support existing one-to-six digit passwords", () => {
  const context = { currentState: { settingsPasswordLength: 2, finishPasswordLength: 6 } };
  vm.createContext(context);
  vm.runInContext(functionSource("settingsPasswordLength") + functionSource("finishPasswordLength"), context);
  assert.equal(context.settingsPasswordLength(), 2);
  assert.equal(context.finishPasswordLength(), 6);
});

test("closing settings during save does not reopen the password prompt", async () => {
  let resolve;
  let sessions = 0;
  const context = {
    settingsSaveInFlight: false, settingsToken: "test-token", remoteSettingsDialogOpen: true,
    appearancePreviewRevision: 0,
    document: { querySelector: () => null },
    rememberVisibleRfReceiverDraft() {}, rememberVisibleRfSlotDraft() {},
    api: {
      action: () => new Promise(done => { resolve = done; }),
      settingsSession: async () => { sessions++; return { ok: true }; },
    },
  };
  vm.createContext(context);
  vm.runInContext(functionSource("saveSettings"), context);
  const pending = context.saveSettings({ action: "update_settings" });
  context.settingsToken = "";
  context.remoteSettingsDialogOpen = false;
  resolve({ ok: true });
  await pending;
  assert.equal(sessions, 0);
  assert.equal(context.settingsSaveInFlight, false);
});
