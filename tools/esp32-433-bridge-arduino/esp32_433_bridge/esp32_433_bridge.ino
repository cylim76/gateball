#include <Arduino.h>

#ifndef RF_DATA_PIN
#define RF_DATA_PIN 27
#endif

#ifndef RF_INVERT_INPUT
#define RF_INVERT_INPUT 0
#endif

#ifndef RF_INPUT_PULLUP
#define RF_INPUT_PULLUP 0
#endif

#ifndef RF_PRINT_RAW_FRAMES
#define RF_PRINT_RAW_FRAMES 0
#endif

#ifndef RF_PRINT_CANDIDATES
#define RF_PRINT_CANDIDATES 0
#endif

#ifndef RF_INFER_FF_BUTTON_FROM_PREFIX
#define RF_INFER_FF_BUTTON_FROM_PREFIX 1
#endif

struct Run {
  uint8_t level;
  uint32_t us;
};

struct Candidate {
  bool valid = false;
  uint32_t code = 0;
  uint8_t bits = 0;
  uint16_t pulseUs = 0;
  uint8_t polarity = 0;
  uint8_t mapping = 0;
  bool reversed = false;
  bool inferred = false;
  int score = -100000;
};

static constexpr uint16_t MAX_FRAME_RUNS = 180;
static constexpr uint16_t MAX_QUEUE_RUNS = 256;
static constexpr uint32_t FRAME_GAP_US = 7000;
static constexpr uint32_t MIN_PULSE_US = 60;
static constexpr uint32_t MAX_PULSE_US = 30000;
static constexpr uint8_t MIN_BITS = 12;
static constexpr uint8_t MAX_BITS = 32;
static constexpr uint8_t STABLE_REPEATS = 2;
static constexpr uint32_t STABLE_WINDOW_MS = 450;
static constexpr uint32_t DUPLICATE_SUPPRESS_MS = 350;

volatile Run runQueue[MAX_QUEUE_RUNS];
volatile uint16_t queueHead = 0;
volatile uint16_t queueTail = 0;
volatile uint32_t droppedRuns = 0;
volatile uint32_t lastEdgeUs = 0;
volatile uint8_t lastLevel = 0;

Run frame[MAX_FRAME_RUNS];
uint16_t frameLen = 0;

uint32_t stableCode = 0;
uint8_t stableBits = 0;
uint8_t stableCount = 0;
uint32_t stableAtMs = 0;
uint32_t lastPrintedCode = 0;
uint8_t lastPrintedBits = 0;
uint32_t lastPrintedAtMs = 0;
static constexpr uint8_t MAX_KNOWN_RF_ADDRESSES = 8;
uint16_t knownRfAddresses[MAX_KNOWN_RF_ADDRESSES];
uint8_t knownRfAddressCount = 0;

static uint8_t readRfLevel() {
  uint8_t level = digitalRead(RF_DATA_PIN) ? 1 : 0;
#if RF_INVERT_INPUT
  level = 1 - level;
#endif
  return level;
}

void IRAM_ATTR onRfEdge() {
  const uint32_t now = micros();
  const uint8_t newLevel = readRfLevel();
  uint32_t duration = now - lastEdgeUs;
  lastEdgeUs = now;

  const uint16_t nextHead = (queueHead + 1) % MAX_QUEUE_RUNS;
  if (nextHead == queueTail) {
    droppedRuns++;
  } else {
    runQueue[queueHead].level = lastLevel;
    runQueue[queueHead].us = duration;
    queueHead = nextHead;
  }
  lastLevel = newLevel;
}

static bool popRun(Run &run) {
  noInterrupts();
  if (queueTail == queueHead) {
    interrupts();
    return false;
  }
  run.level = runQueue[queueTail].level;
  run.us = runQueue[queueTail].us;
  queueTail = (queueTail + 1) % MAX_QUEUE_RUNS;
  interrupts();
  return true;
}

static uint32_t reverseBits(uint32_t value, uint8_t bits) {
  uint32_t out = 0;
  for (uint8_t i = 0; i < bits; i++) {
    out = (out << 1) | (value & 1U);
    value >>= 1;
  }
  return out;
}

static uint32_t maxU32(uint32_t a, uint32_t b) {
  return a > b ? a : b;
}

static uint8_t maxU8(uint8_t a, uint8_t b) {
  return a > b ? a : b;
}

static uint16_t minU16(uint16_t a, uint16_t b) {
  return a < b ? a : b;
}

static uint16_t medianSmallPulse(const Run *runs, uint16_t count, uint8_t polarity) {
  uint16_t values[MAX_FRAME_RUNS];
  uint16_t n = 0;
  for (uint16_t i = 0; i < count && n < MAX_FRAME_RUNS; i++) {
    uint32_t us = runs[i].us;
    if (us < 80 || us > 1200) continue;
    values[n++] = (uint16_t)us;
  }
  if (n == 0) return 0;
  for (uint16_t i = 1; i < n; i++) {
    uint16_t v = values[i];
    int j = i - 1;
    while (j >= 0 && values[j] > v) {
      values[j + 1] = values[j];
      j--;
    }
    values[j + 1] = v;
  }
  (void)polarity;
  return values[n / 2];
}

static bool nearUnits(uint32_t value, uint16_t base, uint8_t units) {
  if (base == 0) return false;
  const uint32_t target = (uint32_t)base * units;
  const uint32_t tolerance = maxU32(90, target / 2);
  return value + tolerance >= target && value <= target + tolerance;
}

static int levelAt(const Run &run, uint8_t polarity) {
  return polarity ? 1 - run.level : run.level;
}

static Candidate decodePwmPairs(const Run *runs, uint16_t count, uint8_t polarity, uint8_t mapping, bool reversed) {
  Candidate best;
  best.polarity = polarity;
  best.mapping = mapping;
  best.reversed = reversed;

  const uint16_t base = medianSmallPulse(runs, count, polarity);
  if (base < 70 || base > 900) return best;

  for (uint16_t offset = 0; offset < 4 && offset + (MIN_BITS * 2) <= count; offset++) {
    for (uint8_t bits = MIN_BITS; bits <= MAX_BITS; bits++) {
      const uint16_t needed = offset + bits * 2;
      if (needed > count) break;

      uint32_t code = 0;
      int score = 0;
      bool ok = true;
      for (uint8_t bit = 0; bit < bits; bit++) {
        const Run &a = runs[offset + bit * 2];
        const Run &b = runs[offset + bit * 2 + 1];
        const int la = levelAt(a, polarity);
        const int lb = levelAt(b, polarity);
        if (la == lb) {
          ok = false;
          break;
        }

        const bool aShort = nearUnits(a.us, base, 1);
        const bool bShort = nearUnits(b.us, base, 1);
        const bool aLong = nearUnits(a.us, base, 2) || nearUnits(a.us, base, 3);
        const bool bLong = nearUnits(b.us, base, 2) || nearUnits(b.us, base, 3);
        int value = -1;

        if (aShort && bLong) value = (mapping == 0) ? 0 : 1;
        else if (aLong && bShort) value = (mapping == 0) ? 1 : 0;
        else {
          ok = false;
          break;
        }

        code = (code << 1) | (uint32_t)value;
        score += 8;
        score -= abs((int)a.us - (int)base) / 40;
      }

      if (!ok) continue;
      if (bits == 24) score += 80;
      if (bits == 20 || bits == 25 || bits == 32) score += 20;
      if (offset == 0) score += 8;

      if (reversed) code = reverseBits(code, bits);
      if (score > best.score) {
        best.valid = true;
        best.code = code;
        best.bits = bits;
        best.pulseUs = base;
        best.score = score;
      }
    }
  }
  return best;
}

static Candidate bestCandidate(const Run *runs, uint16_t count) {
  Candidate best;
  for (uint8_t polarity = 0; polarity < 2; polarity++) {
    for (uint8_t mapping = 0; mapping < 2; mapping++) {
      for (uint8_t rev = 0; rev < 2; rev++) {
        Candidate c = decodePwmPairs(runs, count, polarity, mapping, rev != 0);
        if (c.valid && c.score > best.score) best = c;
      }
    }
  }
  return best;
}

static void rememberRfAddress(uint16_t address) {
  for (uint8_t i = 0; i < knownRfAddressCount; i++) {
    if (knownRfAddresses[i] == address) return;
  }
  if (knownRfAddressCount < MAX_KNOWN_RF_ADDRESSES) {
    knownRfAddresses[knownRfAddressCount++] = address;
    return;
  }
  for (uint8_t i = 1; i < MAX_KNOWN_RF_ADDRESSES; i++) {
    knownRfAddresses[i - 1] = knownRfAddresses[i];
  }
  knownRfAddresses[MAX_KNOWN_RF_ADDRESSES - 1] = address;
}

static Candidate inferFfButtonFromKnownAddressPrefix(const Candidate &candidate) {
  Candidate inferred = candidate;
#if RF_INFER_FF_BUTTON_FROM_PREFIX
  if (!candidate.valid || candidate.bits < 12 || candidate.bits > 16) return inferred;
  for (uint8_t i = 0; i < knownRfAddressCount; i++) {
    const uint16_t address = knownRfAddresses[i];
    const uint16_t prefix = address >> (16 - candidate.bits);
    if (candidate.code == prefix) {
      inferred.code = ((uint32_t)address << 8) | 0xFFU;
      inferred.bits = 24;
      inferred.inferred = true;
      inferred.score += 96;
      return inferred;
    }
  }
#endif
  return inferred;
}

static void printHexValue(uint32_t value, uint8_t bits) {
  uint8_t width = maxU8(2, (bits + 3) / 4);
  Serial.print("0x");
  for (int8_t nibble = width - 1; nibble >= 0; nibble--) {
    uint8_t v = (value >> (nibble * 4)) & 0x0F;
    Serial.print((char)(v < 10 ? '0' + v : 'A' + v - 10));
  }
}

static void printJson(const Candidate &c) {
  const uint32_t button = c.code & 0xFFU;
  const uint32_t address = c.code >> 8;
  Serial.print("{\"raw\":\"");
  printHexValue(c.code, c.bits);
  Serial.print("\",\"address\":\"");
  printHexValue(address, maxU8(8, c.bits > 8 ? c.bits - 8 : 8));
  Serial.print("\",\"button\":\"");
  printHexValue(button, 8);
  Serial.print("\",\"bits\":");
  Serial.print(c.bits);
  Serial.print(",\"protocol\":\"pwm\",\"polarity\":\"");
  Serial.print(c.polarity ? "inverted" : "normal");
  Serial.print("\",\"mapping\":");
  Serial.print(c.mapping);
  Serial.print(",\"reversed\":");
  Serial.print(c.reversed ? "true" : "false");
  if (c.inferred) {
    Serial.print(",\"inferred\":true");
  }
  Serial.print(",\"pulseUs\":");
  Serial.print(c.pulseUs);
  Serial.println("}");
}

static void printCandidate(const Candidate &c) {
  Serial.print("candidate code=");
  printHexValue(c.code, c.bits);
  Serial.print(" bits=");
  Serial.print(c.bits);
  Serial.print(" address=");
  printHexValue(c.code >> 8, maxU8(8, c.bits > 8 ? c.bits - 8 : 8));
  Serial.print(" button=");
  printHexValue(c.code & 0xFFU, 8);
  Serial.print(" pulseUs=");
  Serial.print(c.pulseUs);
  Serial.print(" polarity=");
  Serial.print(c.polarity ? "inverted" : "normal");
  Serial.print(" mapping=");
  Serial.print(c.mapping);
  Serial.print(" reversed=");
  Serial.print(c.reversed ? "yes" : "no");
  if (c.inferred) Serial.print(" inferred=yes");
  Serial.print(" score=");
  Serial.println(c.score);
}

static void printRawFrame(const Run *runs, uint16_t count) {
  Serial.print("raw pulses=");
  Serial.print(count);
  Serial.print(" sample=");
  const uint16_t limit = minU16(count, 48);
  for (uint16_t i = 0; i < limit; i++) {
    if (i) Serial.print(' ');
    Serial.print(runs[i].level);
    Serial.print(':');
    Serial.print(runs[i].us);
  }
  if (count > limit) Serial.print(" ...");
  Serial.println();
}

static void handleCandidate(const Candidate &c) {
  const uint32_t now = millis();
  if (c.valid && c.bits == 24) {
    rememberRfAddress((uint16_t)(c.code >> 8));
  }
  if (c.code == stableCode && c.bits == stableBits && now - stableAtMs <= STABLE_WINDOW_MS) {
    stableCount++;
  } else {
    stableCode = c.code;
    stableBits = c.bits;
    stableCount = 1;
  }
  stableAtMs = now;

  if (stableCount < STABLE_REPEATS) return;
  if (c.code == lastPrintedCode && c.bits == lastPrintedBits && now - lastPrintedAtMs < DUPLICATE_SUPPRESS_MS) return;

  printJson(c);
  lastPrintedCode = c.code;
  lastPrintedBits = c.bits;
  lastPrintedAtMs = now;
}

static void processFrame(const Run *runs, uint16_t count) {
  if (count < MIN_BITS * 2) return;
  Candidate c = bestCandidate(runs, count);
  c = inferFfButtonFromKnownAddressPrefix(c);
  if (c.valid) {
#if RF_PRINT_CANDIDATES
    printCandidate(c);
#endif
    handleCandidate(c);
  } else {
#if RF_PRINT_RAW_FRAMES
    printRawFrame(runs, count);
#endif
  }
}

static void appendRun(const Run &run) {
  if (run.us < MIN_PULSE_US) return;

  if (run.us > FRAME_GAP_US) {
    if (frameLen >= MIN_BITS * 2) processFrame(frame, frameLen);
    frameLen = 0;
    return;
  }

  if (run.us > MAX_PULSE_US) return;
  if (frameLen < MAX_FRAME_RUNS) {
    frame[frameLen++] = run;
  } else {
    processFrame(frame, frameLen);
    frameLen = 0;
  }
}

void setup() {
  Serial.begin(115200);
  delay(250);
#if RF_INPUT_PULLUP
  pinMode(RF_DATA_PIN, INPUT_PULLUP);
#else
  pinMode(RF_DATA_PIN, INPUT);
#endif
  lastLevel = readRfLevel();
  lastEdgeUs = micros();
  attachInterrupt(digitalPinToInterrupt(RF_DATA_PIN), onRfEdge, CHANGE);
  Serial.println();
  Serial.println("ESP32 433MHz RF bridge ready");
  Serial.print("DATA GPIO=");
  Serial.print(RF_DATA_PIN);
  Serial.print(" invert=");
  Serial.print(RF_INVERT_INPUT);
  Serial.print(" pullup=");
  Serial.println(RF_INPUT_PULLUP);
  Serial.println("Press a remote button. Stable decoded frames print JSON lines.");
}

void loop() {
  Run run;
  while (popRun(run)) {
    appendRun(run);
  }

  static uint32_t lastIdleFlush = 0;
  const uint32_t nowUs = micros();
  if (frameLen >= MIN_BITS * 2 && nowUs - lastEdgeUs > FRAME_GAP_US && millis() - lastIdleFlush > 20) {
    processFrame(frame, frameLen);
    frameLen = 0;
    lastIdleFlush = millis();
  }

  static uint32_t lastDropReport = 0;
  if (droppedRuns && millis() - lastDropReport > 1000) {
    noInterrupts();
    uint32_t dropped = droppedRuns;
    droppedRuns = 0;
    interrupts();
    Serial.print("warning dropped-runs=");
    Serial.println(dropped);
    lastDropReport = millis();
  }

  delay(1);
}
