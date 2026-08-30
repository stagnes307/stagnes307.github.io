#!/usr/bin/env node

/**
 * Audit every visual-v2 cc.html in real headless Chrome.
 *
 * The script deliberately uses only Node built-ins and the Chrome DevTools
 * Protocol, so it runs on Windows without a Playwright/Puppeteer install.
 */

import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";


const DEFAULT_CONCURRENCY = 4;
const MAX_CONCURRENCY = 8;
const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_SETTLE_MS = 80;
const DEFAULT_LAYOUT_TOLERANCE_PX = 1.5;
const DEFAULT_COLLISION_TOLERANCE_PX = 1.5;
const DEFAULT_AUX_TEXT_MIN_PX = 10;
const DEFAULT_CORE_TEXT_MIN_PX = 12;
const STROKE_SAMPLE_TARGET_SPACING_PX = 1;
const STROKE_MAX_SAMPLE_POINTS = 4_096;
const STROKE_MIN_CONSECUTIVE_POINTS = 3;
const STROKE_MIN_INTERSECTION_LENGTH_PX = 4;
const TEXT_TEXT_MINIMUM_OVERLAP_RATIO = 0.15;
const MARKER_MAX_PATH_DATA_CHARACTERS = 200_000;
const MARKER_MAX_PATH_TOKENS = 50_000;
const MARKER_MAX_PLACEMENTS_PER_POSITION = 512;
const MARKER_MAX_PAINT_ITEMS_PER_PLACEMENT = 128;
const MARKER_MAX_PAINT_RECORDS_PER_HOST = 4_096;
const FILL_SAMPLE_TARGET_SPACING_PX = 3;
const FILL_MAX_SAMPLE_POINTS = 4_096;
const FILL_MIN_INTERSECTION_POINTS = 2;
const FILL_MIN_INTERSECTION_AREA_PX = 4;
const TOTAL_MAX_SAMPLE_POINTS_PER_SVG = 100_000;
const COLLISION_MAX_COARSE_CANDIDATES_PER_SVG = 50_000;
const COLLISION_MAX_PAIR_INSPECTIONS_PER_SVG = 100_000;
const COLLISION_MAX_RESULTS_PER_KIND_PER_SVG = 500;
const MOBILE_VIEWPORTS = [
  { name: "mobile-360", width: 360, height: 800, mobile: true },
  { name: "mobile-390", width: 390, height: 844, mobile: true },
];
const DESKTOP_VIEWPORT = {
  name: "desktop-1440",
  width: 1440,
  height: 1000,
  mobile: false,
};

const HELP = `Usage:
  node study/factory/scripts/audit_visual_cc_chrome.mjs \\
    --base-url http://127.0.0.1:8765 \\
    --course quality-management-engineer-written \\
    --course quality-management-engineer-practical \\
    --course industrial-safety-engineer-written \\
    --course industrial-safety-engineer-practical \\
    --output C:\\temp\\visual-cc-audit.json

  node study/factory/scripts/audit_visual_cc_chrome.mjs \\
    http://127.0.0.1:8765 COURSE_ID COURSE_ID COURSE_ID COURSE_ID

Required:
  --base-url URL          Local HTTP origin serving this repository. It may also
                          be the first positional argument.
  --course ID             Course ID to audit; repeat it. Course IDs may instead
                          be positional arguments after the base URL.
  --target COURSE:LESSON  Audit only this lesson; repeat it. Target courses are
                          included automatically, with or without --course.

Options:
  --output PATH           JSON report path (default: visual-cc-chrome-audit.json).
                          Use '-' to write JSON to stdout; progress stays stderr.
  --desktop               Also audit at 1440px. Mobile 360px and 390px are always run.
  --concurrency N         Parallel Chrome tabs, 1-${MAX_CONCURRENCY} (default: ${DEFAULT_CONCURRENCY}).
  --chrome PATH           Chrome/Chromium executable; CHROME_PATH is also honored.
  --timeout-ms N          Navigation/CDP timeout (default: ${DEFAULT_TIMEOUT_MS}).
  --settle-ms N           Extra delay after fonts and two animation frames
                          (default: ${DEFAULT_SETTLE_MS}).
  --layout-tolerance-px N Allowed horizontal boundary error (default: ${DEFAULT_LAYOUT_TOLERANCE_PX}).
  --collision-tolerance-px N  Text-text bbox allowance and stroke-edge allowance
                          (default: ${DEFAULT_COLLISION_TOLERANCE_PX}).
  --aux-text-min-px N     Minimum actual rendered height for auxiliary SVG text
                          (default: ${DEFAULT_AUX_TEXT_MIN_PX}).
  --core-text-min-px N    Minimum actual rendered height for core SVG text
                          (default: ${DEFAULT_CORE_TEXT_MIN_PX}).
  --limit N               Audit at most N lessons per course (smoke-test aid).
  --help                  Show this help.

Exit status:
  0  every rendered case passed
  1  one or more pages failed a visual/runtime audit
  2  invalid arguments, discovery failure, or Chrome/auditor failure
`;


function failUsage(message) {
  const error = new Error(message);
  error.isUsageError = true;
  throw error;
}


function consumeValue(argv, index, option) {
  if (index + 1 >= argv.length || argv[index + 1].startsWith("--")) {
    failUsage(`${option} requires a value`);
  }
  return argv[index + 1];
}


function finiteNumber(value, option, { min = 0, integer = false } = {}) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || (integer && !Number.isInteger(parsed))) {
    failUsage(`${option} must be ${integer ? "an integer" : "a number"} >= ${min}`);
  }
  return parsed;
}


function parseArgs(argv) {
  const options = {
    baseUrl: null,
    courses: [],
    targets: [],
    output: "visual-cc-chrome-audit.json",
    desktop: false,
    concurrency: DEFAULT_CONCURRENCY,
    chromePath: null,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    settleMs: DEFAULT_SETTLE_MS,
    layoutTolerancePx: DEFAULT_LAYOUT_TOLERANCE_PX,
    collisionTolerancePx: DEFAULT_COLLISION_TOLERANCE_PX,
    auxiliaryTextMinPx: DEFAULT_AUX_TEXT_MIN_PX,
    coreTextMinPx: DEFAULT_CORE_TEXT_MIN_PX,
    limit: null,
    help: false,
  };
  const positional = [];

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--help" || argument === "-h") {
      options.help = true;
    } else if (argument === "--desktop") {
      options.desktop = true;
    } else if (argument === "--base-url") {
      options.baseUrl = consumeValue(argv, index, argument);
      index += 1;
    } else if (argument === "--course") {
      options.courses.push(consumeValue(argv, index, argument));
      index += 1;
    } else if (argument === "--target") {
      options.targets.push(consumeValue(argv, index, argument));
      index += 1;
    } else if (argument === "--output") {
      options.output = consumeValue(argv, index, argument);
      index += 1;
    } else if (argument === "--concurrency") {
      options.concurrency = finiteNumber(
        consumeValue(argv, index, argument),
        argument,
        { min: 1, integer: true },
      );
      index += 1;
    } else if (argument === "--chrome") {
      options.chromePath = consumeValue(argv, index, argument);
      index += 1;
    } else if (argument === "--timeout-ms") {
      options.timeoutMs = finiteNumber(
        consumeValue(argv, index, argument),
        argument,
        { min: 1_000, integer: true },
      );
      index += 1;
    } else if (argument === "--settle-ms") {
      options.settleMs = finiteNumber(
        consumeValue(argv, index, argument),
        argument,
        { min: 0, integer: true },
      );
      index += 1;
    } else if (argument === "--layout-tolerance-px") {
      options.layoutTolerancePx = finiteNumber(
        consumeValue(argv, index, argument),
        argument,
      );
      index += 1;
    } else if (argument === "--collision-tolerance-px") {
      options.collisionTolerancePx = finiteNumber(
        consumeValue(argv, index, argument),
        argument,
      );
      index += 1;
    } else if (argument === "--aux-text-min-px") {
      options.auxiliaryTextMinPx = finiteNumber(
        consumeValue(argv, index, argument),
        argument,
      );
      index += 1;
    } else if (argument === "--core-text-min-px") {
      options.coreTextMinPx = finiteNumber(
        consumeValue(argv, index, argument),
        argument,
      );
      index += 1;
    } else if (argument === "--limit") {
      options.limit = finiteNumber(
        consumeValue(argv, index, argument),
        argument,
        { min: 1, integer: true },
      );
      index += 1;
    } else if (argument.startsWith("--")) {
      failUsage(`unknown option: ${argument}`);
    } else {
      positional.push(argument);
    }
  }

  if (options.help) return options;
  if (!options.baseUrl && positional[0] && /^https?:\/\//i.test(positional[0])) {
    options.baseUrl = positional.shift();
  }
  options.courses.push(...positional);

  if (!options.baseUrl) failUsage("--base-url (or a positional base URL) is required");
  const parsedTargets = [];
  const seenTargets = new Set();
  for (const target of options.targets) {
    const separator = target.indexOf(":");
    if (separator <= 0 || separator === target.length - 1 ||
        target.indexOf(":", separator + 1) !== -1) {
      failUsage(`--target must be COURSE_ID:LESSON_ID, got ${target}`);
    }
    const courseId = target.slice(0, separator);
    const lessonId = target.slice(separator + 1);
    if (!/^[a-z0-9][a-z0-9-]*$/.test(courseId) ||
        !/^\d+(?:-\d+){3}$/.test(lessonId)) {
      failUsage(`invalid --target: ${target}`);
    }
    const key = `${courseId}:${lessonId}`;
    if (seenTargets.has(key)) failUsage(`duplicate --target: ${key}`);
    seenTargets.add(key);
    parsedTargets.push({ courseId, lessonId, key });
    options.courses.push(courseId);
  }
  options.targets = parsedTargets;
  options.courses = [...new Set(options.courses)];
  if (options.courses.length === 0) {
    failUsage("at least one course ID or --target is required");
  }
  if (options.targets.length && options.limit !== null) {
    failUsage("--limit cannot be combined with --target");
  }
  if (options.concurrency > MAX_CONCURRENCY) {
    failUsage(`--concurrency is capped at ${MAX_CONCURRENCY}`);
  }
  if (options.auxiliaryTextMinPx > options.coreTextMinPx) {
    failUsage("--aux-text-min-px must not exceed --core-text-min-px");
  }
  for (const courseId of options.courses) {
    if (!/^[a-z0-9][a-z0-9-]*$/.test(courseId)) {
      failUsage(`invalid course ID: ${courseId}`);
    }
  }

  let parsedBase;
  try {
    parsedBase = new URL(options.baseUrl);
  } catch {
    failUsage(`invalid base URL: ${options.baseUrl}`);
  }
  if (!new Set(["http:", "https:"]).has(parsedBase.protocol)) {
    failUsage("base URL must use http or https");
  }
  const hostname = parsedBase.hostname.toLowerCase();
  const local = hostname === "localhost" || hostname === "::1" ||
    hostname === "0.0.0.0" || /^127(?:\.\d{1,3}){3}$/.test(hostname);
  if (!local) failUsage(`base URL must be local, got hostname ${parsedBase.hostname}`);
  parsedBase.hash = "";
  parsedBase.search = "";
  options.baseUrl = parsedBase.href.replace(/\/+$/, "");
  return options;
}


function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}


async function fetchJson(url, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
    const contentType = response.headers.get("content-type") ?? "";
    const value = await response.json();
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new Error(`JSON root must be an object: ${url}`);
    }
    return { value, contentType };
  } finally {
    clearTimeout(timer);
  }
}


function lessonsFromCurriculum(courseId, curriculum, baseUrl) {
  if (curriculum.course_id !== courseId) {
    throw new Error(
      `curriculum course_id mismatch: expected ${courseId}, got ${curriculum.course_id}`,
    );
  }
  const lessons = [];
  for (const section of curriculum.sections ?? []) {
    for (const unit of section.units ?? []) {
      for (const group of unit.lessons ?? []) {
        for (const lesson of group.sublessons ?? []) {
          if (!lesson?.id || !lesson?.slug) {
            throw new Error(`${courseId}: a sublesson is missing id or slug`);
          }
          const lessonDirectory = `${encodeURIComponent(lesson.id)}-${encodeURIComponent(lesson.slug)}`;
          const relativeUrl = `/study/courses/${encodeURIComponent(courseId)}/lessons/${lessonDirectory}/cc.html`;
          lessons.push({
            courseId,
            courseTitle: curriculum.title ?? courseId,
            lessonId: lesson.id,
            lessonTitle: lesson.title ?? "",
            slug: lesson.slug,
            relativeUrl,
            url: `${baseUrl}${relativeUrl}`,
          });
        }
      }
    }
  }
  if (lessons.length === 0) throw new Error(`${courseId}: curriculum contains no lessons`);
  const unique = new Set(lessons.map((lesson) => lesson.url));
  if (unique.size !== lessons.length) throw new Error(`${courseId}: duplicate lesson URL detected`);
  return lessons;
}


async function discoverCourses(options) {
  const courses = [];
  for (const courseId of options.courses) {
    const curriculumUrl = `${options.baseUrl}/study/curricula/${encodeURIComponent(courseId)}.json`;
    const { value: curriculum } = await fetchJson(curriculumUrl, options.timeoutMs);
    const discoveredLessons = lessonsFromCurriculum(courseId, curriculum, options.baseUrl);
    const discoveredLessonCount = discoveredLessons.length;
    let lessons;
    if (options.targets.length) {
      lessons = [];
      for (const target of options.targets.filter((value) => value.courseId === courseId)) {
        const matches = discoveredLessons.filter((lesson) => lesson.lessonId === target.lessonId);
        if (matches.length !== 1) {
          throw new Error(
            `${target.key}: expected exactly one curriculum lesson, found ${matches.length}`,
          );
        }
        lessons.push(matches[0]);
      }
    } else {
      lessons = options.limit === null ? discoveredLessons : discoveredLessons.slice(0, options.limit);
    }
    courses.push({
      courseId,
      courseTitle: curriculum.title ?? courseId,
      curriculumUrl,
      discoveredLessonCount,
      selectedLessonCount: lessons.length,
      lessons,
    });
  }
  if (options.targets.length) {
    const selected = new Set(courses.flatMap((course) =>
      course.lessons.map((lesson) => `${lesson.courseId}:${lesson.lessonId}`)));
    for (const target of options.targets) {
      if (!selected.has(target.key)) throw new Error(`${target.key}: target was not selected`);
    }
  }
  return courses;
}


function chromeCandidates(explicitPath) {
  return [
    explicitPath,
    process.env.CHROME_PATH,
    ...(process.platform === "win32" ? [
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files\\Chromium\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
      "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    ] : process.platform === "darwin" ? [
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ] : [
      "/usr/bin/google-chrome",
      "/usr/bin/google-chrome-stable",
      "/usr/bin/chromium",
      "/usr/bin/chromium-browser",
    ]),
  ].filter(Boolean);
}


function resolveChromePath(explicitPath) {
  const candidate = chromeCandidates(explicitPath).find((value) => fs.existsSync(value));
  if (!candidate) {
    throw new Error("Chrome/Chromium was not found; pass --chrome PATH or set CHROME_PATH");
  }
  return path.resolve(candidate);
}


async function reservePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : null;
      server.close((error) => {
        if (error) reject(error);
        else if (port === null) reject(new Error("could not allocate a CDP port"));
        else resolve(port);
      });
    });
  });
}


async function waitForDevTools(port, child, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    if (child.spawnError) {
      throw new Error(`Chrome could not start: ${child.spawnError.message}`);
    }
    if (child.exitCode !== null) {
      throw new Error(`Chrome exited before DevTools started (exit ${child.exitCode})`);
    }
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (response.ok) return response.json();
    } catch (error) {
      lastError = error;
    }
    await delay(100);
  }
  throw new Error(`Chrome DevTools endpoint did not start: ${lastError?.message ?? "timeout"}`);
}


class CDP {
  constructor(webSocketUrl, timeoutMs) {
    this.socket = new WebSocket(webSocketUrl);
    this.timeoutMs = timeoutMs;
    this.nextId = 1;
    this.pending = new Map();
    this.waiters = new Map();
    this.events = [];
    this.socket.onmessage = ({ data }) => this.#receive(JSON.parse(data));
    this.socket.onclose = () => this.#rejectPending(new Error("CDP socket closed"));
    this.socket.addEventListener(
      "error",
      () => this.#rejectPending(new Error("CDP socket error")),
    );
  }

  #receive(message) {
    if (message.id) {
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      clearTimeout(pending.timer);
      if (message.error) pending.reject(new Error(message.error.message ?? JSON.stringify(message.error)));
      else pending.resolve(message.result ?? {});
      return;
    }
    this.events.push(message);
    const queue = this.waiters.get(message.method);
    if (queue?.length) {
      const waiter = queue.shift();
      clearTimeout(waiter.timer);
      waiter.resolve(message.params ?? {});
    }
  }

  #rejectPending(error) {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
    for (const queue of this.waiters.values()) {
      for (const waiter of queue) {
        clearTimeout(waiter.timer);
        waiter.reject(error);
      }
    }
    this.waiters.clear();
  }

  async open() {
    if (this.socket.readyState === WebSocket.OPEN) return;
    await new Promise((resolve, reject) => {
      const cleanup = () => {
        this.socket.removeEventListener("open", handleOpen);
        this.socket.removeEventListener("error", handleError);
      };
      const handleOpen = () => {
        clearTimeout(timer);
        cleanup();
        resolve();
      };
      const handleError = () => {
        clearTimeout(timer);
        cleanup();
        reject(new Error("failed to open CDP socket"));
      };
      const timer = setTimeout(() => {
        cleanup();
        reject(new Error("timed out opening CDP socket"));
      }, this.timeoutMs);
      this.socket.addEventListener("open", handleOpen, { once: true });
      this.socket.addEventListener("error", handleError, { once: true });
    });
  }

  call(method, params = {}) {
    if (this.socket.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error(`CDP socket is not open for ${method}`));
    }
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`timed out calling ${method}`));
      }, this.timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  waitEvent(method) {
    return new Promise((resolve, reject) => {
      const queue = this.waiters.get(method) ?? [];
      const waiter = { resolve, reject, timer: null };
      waiter.timer = setTimeout(() => {
        const current = this.waiters.get(method) ?? [];
        const index = current.indexOf(waiter);
        if (index >= 0) current.splice(index, 1);
        reject(new Error(`timed out waiting for ${method}`));
      }, this.timeoutMs);
      queue.push(waiter);
      this.waiters.set(method, queue);
    });
  }

  resetEvents() {
    this.events = [];
  }

  cancelWaiters(method, error = new Error(`cancelled wait for ${method}`)) {
    const queue = this.waiters.get(method) ?? [];
    this.waiters.delete(method);
    for (const waiter of queue) {
      clearTimeout(waiter.timer);
      waiter.reject(error);
    }
  }

  close() {
    if (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING) {
      this.socket.close();
    }
  }
}


function buildAuditExpression(options) {
  const config = JSON.stringify({
    layoutTolerancePx: options.layoutTolerancePx,
    collisionTolerancePx: options.collisionTolerancePx,
    auxiliaryTextMinPx: options.auxiliaryTextMinPx,
    coreTextMinPx: options.coreTextMinPx,
    strokeSampleTargetSpacingPx: STROKE_SAMPLE_TARGET_SPACING_PX,
    strokeMaxSamplePoints: STROKE_MAX_SAMPLE_POINTS,
    strokeMinConsecutivePoints: STROKE_MIN_CONSECUTIVE_POINTS,
    strokeMinIntersectionLengthPx: STROKE_MIN_INTERSECTION_LENGTH_PX,
    textTextMinimumOverlapRatio: TEXT_TEXT_MINIMUM_OVERLAP_RATIO,
    markerMaxPathDataCharacters: MARKER_MAX_PATH_DATA_CHARACTERS,
    markerMaxPathTokens: MARKER_MAX_PATH_TOKENS,
    markerMaxPlacementsPerPosition: MARKER_MAX_PLACEMENTS_PER_POSITION,
    markerMaxPaintItemsPerPlacement: MARKER_MAX_PAINT_ITEMS_PER_PLACEMENT,
    markerMaxPaintRecordsPerHost: MARKER_MAX_PAINT_RECORDS_PER_HOST,
    fillSampleTargetSpacingPx: FILL_SAMPLE_TARGET_SPACING_PX,
    fillMaxSamplePoints: FILL_MAX_SAMPLE_POINTS,
    fillMinIntersectionPoints: FILL_MIN_INTERSECTION_POINTS,
    fillMinIntersectionAreaPx: FILL_MIN_INTERSECTION_AREA_PX,
    totalMaxSamplePointsPerSvg: TOTAL_MAX_SAMPLE_POINTS_PER_SVG,
    collisionMaxCoarseCandidatesPerSvg: COLLISION_MAX_COARSE_CANDIDATES_PER_SVG,
    collisionMaxPairInspectionsPerSvg: COLLISION_MAX_PAIR_INSPECTIONS_PER_SVG,
    collisionMaxResultsPerKindPerSvg: COLLISION_MAX_RESULTS_PER_KIND_PER_SVG,
  });
  return String.raw`(() => {
    const config = ${config};
    const root = document.documentElement;
    const body = document.body;
    const round = (value) => Number.isFinite(value) ? Math.round(value * 100) / 100 : null;
    let activeSampleBudget = null;
    const samplingLimitError = (code, scope, observed, limit) => {
      const error = new Error(
        scope + " observed " + observed + "; limit is " + limit,
      );
      error.auditLimit = { code, scope, observed, limit, action: "skipped" };
      return error;
    };
    const reserveSamplePoints = (count, scope) => {
      if (!activeSampleBudget) return;
      const observed = activeSampleBudget.used + count;
      if (observed > activeSampleBudget.limit) {
        activeSampleBudget.exhausted = true;
        throw samplingLimitError(
          "svg-sample-point-limit",
          scope,
          observed,
          activeSampleBudget.limit,
        );
      }
      activeSampleBudget.used = observed;
    };
    const rectValue = (rect) => ({
      left: round(rect.left),
      top: round(rect.top),
      right: round(rect.right),
      bottom: round(rect.bottom),
      width: round(rect.width),
      height: round(rect.height),
    });
    const displayed = (element) => {
      const style = getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden" ||
          Number(style.opacity || 1) <= 0 || element.getClientRects().length === 0) {
        return false;
      }
      let ancestor = element.parentElement;
      while (ancestor) {
        if (Number(getComputedStyle(ancestor).opacity || 1) <= 0) return false;
        ancestor = ancestor.parentElement;
      }
      return true;
    };
    const visibleBox = (element) => {
      if (!displayed(element)) return false;
      const rect = element.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    };
    const simpleName = (element) => {
      if (!element) return "";
      const id = element.id ? "#" + element.id : "";
      const classValue = typeof element.className === "string" ? element.className :
        (element.className?.baseVal ?? "");
      const classes = classValue.trim().split(/\s+/).filter(Boolean).slice(0, 3)
        .map((name) => "." + name).join("");
      return element.tagName.toLowerCase() + id + classes;
    };
    const selector = (element) => {
      const parts = [];
      let current = element;
      while (current && current.nodeType === Node.ELEMENT_NODE && parts.length < 5) {
        let part = simpleName(current);
        if (current.id) {
          parts.unshift(part);
          break;
        }
        const siblings = current.parentElement ?
          [...current.parentElement.children].filter((node) => node.tagName === current.tagName) : [];
        if (siblings.length > 1) part += ":nth-of-type(" + (siblings.indexOf(current) + 1) + ")";
        parts.unshift(part);
        current = current.parentElement;
      }
      return parts.join(" > ");
    };
    const describe = (element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        selector: selector(element),
        tag: element.tagName.toLowerCase(),
        rect: rectValue(rect),
        clientWidth: round(Number(element.clientWidth) || 0),
        scrollWidth: round(Number(element.scrollWidth) || 0),
        overflowX: style.overflowX,
      };
    };
    const horizontalOutside = (inner, outer, tolerance) => ({
      outside: inner.left < outer.left - tolerance || inner.right > outer.right + tolerance,
      leftOverflowPx: round(Math.max(0, outer.left - inner.left)),
      rightOverflowPx: round(Math.max(0, inner.right - outer.right)),
    });
    const boundsOutside = (inner, outer, tolerance) => {
      const leftOverflowPx = Math.max(0, outer.left - inner.left);
      const rightOverflowPx = Math.max(0, inner.right - outer.right);
      const topOverflowPx = Math.max(0, outer.top - inner.top);
      const bottomOverflowPx = Math.max(0, inner.bottom - outer.bottom);
      const left = leftOverflowPx > tolerance;
      const right = rightOverflowPx > tolerance;
      const top = topOverflowPx > tolerance;
      const bottom = bottomOverflowPx > tolerance;
      return {
        outside: left || right || top || bottom,
        horizontalOutside: left || right,
        verticalOutside: top || bottom,
        sides: { left, right, top, bottom },
        leftOverflowPx: round(leftOverflowPx),
        rightOverflowPx: round(rightOverflowPx),
        topOverflowPx: round(topOverflowPx),
        bottomOverflowPx: round(bottomOverflowPx),
      };
    };
    const quadForElement = (element, fallbackRect = null) => {
      try {
        const box = element.getBBox();
        const matrix = element.getScreenCTM();
        if (!matrix) throw new Error("screen transform unavailable");
        return [
          new DOMPoint(box.x, box.y),
          new DOMPoint(box.x + box.width, box.y),
          new DOMPoint(box.x + box.width, box.y + box.height),
          new DOMPoint(box.x, box.y + box.height),
        ].map((point) => point.matrixTransform(matrix));
      } catch {
        const rect = fallbackRect || element.getBoundingClientRect();
        return [
          { x: rect.left, y: rect.top },
          { x: rect.right, y: rect.top },
          { x: rect.right, y: rect.bottom },
          { x: rect.left, y: rect.bottom },
        ];
      }
    };
    const rectForPoints = (points) => {
      if (!points.length || !points.every((point) =>
        Number.isFinite(point.x) && Number.isFinite(point.y))) return null;
      const left = Math.min(...points.map((point) => point.x));
      const top = Math.min(...points.map((point) => point.y));
      const right = Math.max(...points.map((point) => point.x));
      const bottom = Math.max(...points.map((point) => point.y));
      return { left, top, right, bottom, width: right - left, height: bottom - top };
    };
    const polygonSignedArea = (points) => points.reduce((area, point, index) => {
      const next = points[(index + 1) % points.length];
      return area + point.x * next.y - next.x * point.y;
    }, 0) / 2;
    const crossProduct = (left, right) => left.x * right.y - left.y * right.x;
    const clipEdgeEnabled = (edgeIndex, clipHorizontal, clipVertical) =>
      (edgeIndex % 2 === 0 ? clipVertical : clipHorizontal);
    const pointInsideClipEdges = (
      point,
      clipPolygon,
      clipHorizontal,
      clipVertical,
      tolerance = 1e-7,
    ) => {
      const orientation = polygonSignedArea(clipPolygon) >= 0 ? 1 : -1;
      return clipPolygon.every((start, edgeIndex) => {
        if (!clipEdgeEnabled(edgeIndex, clipHorizontal, clipVertical)) return true;
        const end = clipPolygon[(edgeIndex + 1) % clipPolygon.length];
        const edge = { x: end.x - start.x, y: end.y - start.y };
        const relative = { x: point.x - start.x, y: point.y - start.y };
        const edgeLength = Math.max(Math.hypot(edge.x, edge.y), 1e-9);
        return orientation * crossProduct(edge, relative) >= -tolerance * edgeLength;
      });
    };
    const clipConvexPolygon = (
      subjectPolygon,
      clipPolygon,
      clipHorizontal,
      clipVertical,
    ) => {
      let output = subjectPolygon.map((point) => ({ x: point.x, y: point.y }));
      if (!output.length) return output;
      const orientation = polygonSignedArea(clipPolygon) >= 0 ? 1 : -1;
      const intersection = (start, end, clipStart, clipEnd) => {
        const subjectDirection = { x: end.x - start.x, y: end.y - start.y };
        const clipDirection = { x: clipEnd.x - clipStart.x, y: clipEnd.y - clipStart.y };
        const denominator = crossProduct(subjectDirection, clipDirection);
        if (Math.abs(denominator) <= 1e-9) return { x: end.x, y: end.y };
        const delta = { x: clipStart.x - start.x, y: clipStart.y - start.y };
        const ratio = crossProduct(delta, clipDirection) / denominator;
        return {
          x: start.x + ratio * subjectDirection.x,
          y: start.y + ratio * subjectDirection.y,
        };
      };
      for (let edgeIndex = 0; edgeIndex < clipPolygon.length; edgeIndex += 1) {
        if (!clipEdgeEnabled(edgeIndex, clipHorizontal, clipVertical)) continue;
        const input = output;
        output = [];
        if (!input.length) break;
        const clipStart = clipPolygon[edgeIndex];
        const clipEnd = clipPolygon[(edgeIndex + 1) % clipPolygon.length];
        const inside = (point) => orientation * crossProduct(
          { x: clipEnd.x - clipStart.x, y: clipEnd.y - clipStart.y },
          { x: point.x - clipStart.x, y: point.y - clipStart.y },
        ) >= -1e-7;
        let previous = input[input.length - 1];
        let previousInside = inside(previous);
        for (const current of input) {
          const currentInside = inside(current);
          if (currentInside) {
            if (!previousInside) {
              output.push(intersection(previous, current, clipStart, clipEnd));
            }
            output.push(current);
          } else if (previousInside) {
            output.push(intersection(previous, current, clipStart, clipEnd));
          }
          previous = current;
          previousInside = currentInside;
        }
      }
      return output;
    };
    const polygonOutside = (subjectPolygon, clipPolygon, tolerance) => {
      const orientation = polygonSignedArea(clipPolygon) >= 0 ? 1 : -1;
      const distances = clipPolygon.map((start, edgeIndex) => {
        const end = clipPolygon[(edgeIndex + 1) % clipPolygon.length];
        const edge = { x: end.x - start.x, y: end.y - start.y };
        const edgeLength = Math.max(Math.hypot(edge.x, edge.y), 1e-9);
        return Math.max(0, ...subjectPolygon.map((point) => -orientation * crossProduct(
          edge,
          { x: point.x - start.x, y: point.y - start.y },
        ) / edgeLength));
      });
      const [topOverflowPx, rightOverflowPx, bottomOverflowPx, leftOverflowPx] = distances;
      const sides = {
        left: leftOverflowPx > tolerance,
        right: rightOverflowPx > tolerance,
        top: topOverflowPx > tolerance,
        bottom: bottomOverflowPx > tolerance,
      };
      return {
        outside: Object.values(sides).some(Boolean),
        horizontalOutside: sides.left || sides.right,
        verticalOutside: sides.top || sides.bottom,
        sides,
        leftOverflowPx: round(leftOverflowPx),
        rightOverflowPx: round(rightOverflowPx),
        topOverflowPx: round(topOverflowPx),
        bottomOverflowPx: round(bottomOverflowPx),
      };
    };
    const paintQuadForElement = (element, fallbackRect) => {
      try {
        const box = element.getBBox();
        const matrix = element.getScreenCTM();
        if (!matrix) throw new Error("screen transform unavailable");
        const style = getComputedStyle(element);
        const parsedStrokeWidth = Number.parseFloat(style.strokeWidth);
        const strokePadding = strokeIsVisible(element) && Number.isFinite(parsedStrokeWidth) ?
          Math.max(0, parsedStrokeWidth) / 2 : 0;
        if (style.vectorEffect === "non-scaling-stroke" && strokePadding > 0) {
          throw new Error("non-scaling stroke requires screen bbox fallback");
        }
        return [
          new DOMPoint(box.x - strokePadding, box.y - strokePadding),
          new DOMPoint(box.x + box.width + strokePadding, box.y - strokePadding),
          new DOMPoint(
            box.x + box.width + strokePadding,
            box.y + box.height + strokePadding,
          ),
          new DOMPoint(box.x - strokePadding, box.y + box.height + strokePadding),
        ].map((point) => point.matrixTransform(matrix));
      } catch {
        return [
          { x: fallbackRect.left, y: fallbackRect.top },
          { x: fallbackRect.right, y: fallbackRect.top },
          { x: fallbackRect.right, y: fallbackRect.bottom },
          { x: fallbackRect.left, y: fallbackRect.bottom },
        ];
      }
    };
    const polygonScreenPoints = (element) => {
      try {
        const matrix = element.getScreenCTM();
        if (!matrix || !element.points) return [];
        return Array.from(
          { length: element.points.numberOfItems },
          (_, index) => element.points.getItem(index),
        ).map((point) => new DOMPoint(point.x, point.y).matrixTransform(matrix));
      } catch {
        return [];
      }
    };
    const pointInPolygon = (point, polygon) => {
      let inside = false;
      for (let index = 0, previous = polygon.length - 1;
        index < polygon.length;
        previous = index, index += 1) {
        const start = polygon[previous];
        const end = polygon[index];
        if (pointSegmentDistance(point, start, end) <= 1e-7) return true;
        const crosses = (end.y > point.y) !== (start.y > point.y) &&
          point.x < (start.x - end.x) * (point.y - end.y) /
            Math.max(Math.abs(start.y - end.y), 1e-12) * Math.sign(start.y - end.y) + end.x;
        if (crosses) inside = !inside;
      }
      return inside;
    };
    const pointSegmentDistance = (point, start, end) => {
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      const lengthSquared = dx * dx + dy * dy;
      if (lengthSquared <= 1e-9) return Math.hypot(point.x - start.x, point.y - start.y);
      const ratio = Math.max(0, Math.min(1,
        ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared));
      return Math.hypot(
        point.x - (start.x + ratio * dx),
        point.y - (start.y + ratio * dy),
      );
    };
    const pointInConvexQuad = (point, quad) => {
      if (!quad || quad.length !== 4) return false;
      let sign = 0;
      for (let index = 0; index < quad.length; index += 1) {
        const start = quad[index];
        const end = quad[(index + 1) % quad.length];
        const cross = (end.x - start.x) * (point.y - start.y) -
          (end.y - start.y) * (point.x - start.x);
        if (Math.abs(cross) <= 1e-7) continue;
        const currentSign = Math.sign(cross);
        if (sign && currentSign !== sign) return false;
        sign = currentSign;
      }
      return true;
    };
    const pointInExpandedQuad = (point, quad, reach) => {
      if (pointInConvexQuad(point, quad)) return true;
      if (!(reach > 0)) return false;
      return quad.some((start, index) =>
        pointSegmentDistance(point, start, quad[(index + 1) % quad.length]) <= reach);
    };
    const overlap = (a, b, tolerance) => {
      const width = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const height = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      return {
        collides: width > tolerance && height > tolerance,
        overlapWidthPx: round(Math.max(0, width)),
        overlapHeightPx: round(Math.max(0, height)),
      };
    };
    const nearestContainer = (svg) => {
      let candidate = svg.parentElement;
      while (candidate && candidate !== root) {
        const display = getComputedStyle(candidate).display;
        const rect = candidate.getBoundingClientRect();
        if (candidate !== body && display !== "contents" && !display.startsWith("inline") && rect.width > 0) {
          return candidate;
        }
        candidate = candidate.parentElement;
      }
      return body;
    };
    const paintValueVisible = (value) => {
      const normalized = String(value || "").trim().toLowerCase();
      if (!normalized || normalized === "none" || normalized === "transparent") return false;
      if (/^rgba\([^)]*,\s*0(?:\.0+)?\s*\)$/.test(normalized)) return false;
      if (/\/[\s]*0(?:\.0+)?%?\s*\)$/.test(normalized)) return false;
      return true;
    };
    const strokeIsVisible = (element) => {
      const style = getComputedStyle(element);
      return paintValueVisible(style.stroke) && Number(style.strokeOpacity || 1) > 0 &&
        Number(style.opacity || 1) > 0;
    };
    const fillIsVisible = (element) => {
      const style = getComputedStyle(element);
      return paintValueVisible(style.fill) && Number(style.fillOpacity || 1) > 0 &&
        Number(style.opacity || 1) > 0;
    };
    const textPaintIsVisible = (element) => fillIsVisible(element) || strokeIsVisible(element);
    const paintElementIsVisible = (element) => {
      const tag = element.tagName.toLowerCase();
      if (["use", "image", "foreignobject"].includes(tag)) {
        if (!visibleBox(element)) return false;
        if (tag === "image") {
          const href = element.getAttribute("href") ||
            element.getAttributeNS("http://www.w3.org/1999/xlink", "href") || "";
          if (!href.trim()) return false;
        }
        return true;
      }
      return strokeIsVisible(element) || fillIsVisible(element);
    };
    const markerStyleProperties = [
      "color", "opacity", "display", "visibility", "fill", "fill-opacity", "fill-rule",
      "stroke", "stroke-opacity", "stroke-width", "stroke-linecap", "stroke-linejoin",
      "stroke-miterlimit", "stroke-dasharray", "stroke-dashoffset", "vector-effect",
      "paint-order", "shape-rendering", "image-rendering", "font-family", "font-size",
      "font-style", "font-weight", "letter-spacing", "text-anchor", "dominant-baseline",
      "transform", "transform-origin", "clip-path", "mask", "filter",
      "x", "y", "cx", "cy", "r", "rx", "ry", "width", "height",
    ];
    const cloneMarkerNodeWithComputedStyles = (original, host) => {
      const clone = original.cloneNode(true);
      const originals = [original, ...original.querySelectorAll("*")];
      const clones = [clone, ...clone.querySelectorAll("*")];
      const hostStyle = getComputedStyle(host);
      const contextPaint = (value) => {
        const normalized = String(value || "").trim().toLowerCase();
        if (normalized === "context-stroke") return hostStyle.stroke || "none";
        if (normalized === "context-fill") return hostStyle.fill || "none";
        return value;
      };
      for (let index = 0; index < Math.min(originals.length, clones.length); index += 1) {
        const computed = getComputedStyle(originals[index]);
        for (const property of markerStyleProperties) {
          const value = contextPaint(computed.getPropertyValue(property));
          if (value) clones[index].style.setProperty(property, value, "important");
        }
      }
      return clone;
    };
    const geometryRect = (element) => {
      try {
        const box = element.getBBox();
        const matrix = element.getScreenCTM();
        if (!matrix) return null;
        const points = [
          new DOMPoint(box.x, box.y),
          new DOMPoint(box.x + box.width, box.y),
          new DOMPoint(box.x + box.width, box.y + box.height),
          new DOMPoint(box.x, box.y + box.height),
        ].map((point) => point.matrixTransform(matrix));
        const xs = points.map((point) => point.x);
        const ys = points.map((point) => point.y);
        const style = getComputedStyle(element);
        const parsedStrokeWidth = Number.parseFloat(style.strokeWidth);
        const strokeWidth = strokeIsVisible(element) && Number.isFinite(parsedStrokeWidth) ?
          Math.max(0, parsedStrokeWidth) : 0;
        const scale = Math.max(
          Math.hypot(matrix.a, matrix.b),
          Math.hypot(matrix.c, matrix.d),
          0.0001,
        );
        const strokeScale = style.vectorEffect === "non-scaling-stroke" ? 1 : scale;
        const padding = strokeWidth * strokeScale / 2;
        const left = Math.min(...xs) - padding;
        const right = Math.max(...xs) + padding;
        const top = Math.min(...ys) - padding;
        const bottom = Math.max(...ys) + padding;
        return { left, right, top, bottom, width: right - left, height: bottom - top };
      } catch {
        const rect = element.getBoundingClientRect();
        return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
          width: rect.width, height: rect.height };
      }
    };
    const intersectRects = (leftRect, rightRect) => {
      if (!leftRect || !rightRect) return null;
      const left = Math.max(leftRect.left, rightRect.left);
      const right = Math.min(leftRect.right, rightRect.right);
      const top = Math.max(leftRect.top, rightRect.top);
      const bottom = Math.min(leftRect.bottom, rightRect.bottom);
      if (!(right > left && bottom > top)) return null;
      return { left, right, top, bottom, width: right - left, height: bottom - top };
    };
    const rectContainsPoint = (rect, point, inset = 0) => Boolean(rect) &&
      point.x >= rect.left + inset && point.x <= rect.right - inset &&
      point.y >= rect.top + inset && point.y <= rect.bottom - inset;
    const localPaintServerReference = (value, expectedTag) => {
      if (!value || value === "none") return null;
      const match = String(value).match(/^url\(\s*['"]?([^'")]+)['"]?\s*\)$/i);
      if (!match) return null;
      let id = "";
      try {
        const resolved = new URL(match[1], document.baseURI);
        const referencedDocument = new URL(resolved.href);
        const currentDocument = new URL(document.location.href);
        referencedDocument.hash = "";
        currentDocument.hash = "";
        if (referencedDocument.href !== currentDocument.href) return null;
        id = decodeURIComponent(resolved.hash.slice(1));
      } catch {
        id = match[1].startsWith("#") ? match[1].slice(1) : "";
      }
      const referenced = id ? document.getElementById(id) : null;
      if (!referenced || referenced.tagName?.toLowerCase() !== expectedTag) return null;
      return { id, referenced };
    };
    const clipGeometryTags = new Set([
      "path", "rect", "circle", "ellipse", "polygon", "polyline", "text", "use",
    ]);
    const clipPathPaintBounds = (clipTarget, outerSvg, cache) => {
      if (cache.has(clipTarget)) return cache.get(clipTarget);
      const clipValue = getComputedStyle(clipTarget).clipPath ||
        clipTarget.getAttribute("clip-path") || "";
      const reference = localPaintServerReference(clipValue, "clippath");
      if (!reference) {
        cache.set(clipTarget, null);
        return null;
      }
      const clipPath = reference.referenced;
      const outerMatrix = outerSvg.getScreenCTM();
      const targetMatrix = clipTarget.getScreenCTM();
      if (!outerMatrix || !targetMatrix) {
        cache.set(clipTarget, null);
        return null;
      }
      const namespace = "http://www.w3.org/2000/svg";
      const layer = document.createElementNS(namespace, "g");
      layer.setAttribute("aria-hidden", "true");
      layer.style.setProperty("pointer-events", "none", "important");
      layer.style.setProperty("opacity", "0", "important");
      try {
        let targetToOuter = new DOMMatrix([
          outerMatrix.a,
          outerMatrix.b,
          outerMatrix.c,
          outerMatrix.d,
          outerMatrix.e,
          outerMatrix.f,
        ]).inverse().multiply(new DOMMatrix([
          targetMatrix.a,
          targetMatrix.b,
          targetMatrix.c,
          targetMatrix.d,
          targetMatrix.e,
          targetMatrix.f,
        ]));
        const units = (clipPath.getAttribute("clipPathUnits") ||
          "userSpaceOnUse").toLowerCase();
        if (units === "objectboundingbox") {
          const box = clipTarget.getBBox();
          if (!(box.width > 0 && box.height > 0)) {
            const result = { id: reference.id, rect: null, empty: true };
            cache.set(clipTarget, result);
            return result;
          }
          targetToOuter = targetToOuter.translate(box.x, box.y).scale(box.width, box.height);
        }
        layer.setAttribute(
          "transform",
          "matrix(" + [
            targetToOuter.a,
            targetToOuter.b,
            targetToOuter.c,
            targetToOuter.d,
            targetToOuter.e,
            targetToOuter.f,
          ].join(" ") + ")",
        );
        const clipContents = document.createElementNS(namespace, "g");
        const clipTransform = clipPath.getAttribute("transform");
        if (clipTransform) clipContents.setAttribute("transform", clipTransform);
        for (const child of clipPath.children) {
          clipContents.appendChild(cloneMarkerNodeWithComputedStyles(child, clipTarget));
        }
        layer.appendChild(clipContents);
        outerSvg.appendChild(layer);
        const candidates = [...clipContents.querySelectorAll(
          "path, rect, circle, ellipse, polygon, polyline, text, use",
        )].filter((element) => clipGeometryTags.has(element.tagName.toLowerCase()))
          .filter((element) => !element.closest("defs, mask, pattern, symbol"));
        let rect = null;
        for (const candidate of candidates) {
          const style = getComputedStyle(candidate);
          if (style.display === "none" || style.visibility === "hidden") continue;
          let candidateRect = null;
          try {
            const box = candidate.getBBox();
            const matrix = candidate.getScreenCTM();
            if (!matrix || !(box.width > 0 && box.height > 0)) continue;
            candidateRect = rectForPoints([
              new DOMPoint(box.x, box.y),
              new DOMPoint(box.x + box.width, box.y),
              new DOMPoint(box.x + box.width, box.y + box.height),
              new DOMPoint(box.x, box.y + box.height),
            ].map((point) => point.matrixTransform(matrix)));
          } catch {
            candidateRect = null;
          }
          if (!candidateRect) continue;
          if (!rect) rect = candidateRect;
          else {
            const left = Math.min(rect.left, candidateRect.left);
            const right = Math.max(rect.right, candidateRect.right);
            const top = Math.min(rect.top, candidateRect.top);
            const bottom = Math.max(rect.bottom, candidateRect.bottom);
            rect = { left, right, top, bottom, width: right - left, height: bottom - top };
          }
        }
        const result = { id: reference.id, rect, empty: !rect };
        cache.set(clipTarget, result);
        return result;
      } catch {
        cache.set(clipTarget, null);
        return null;
      } finally {
        layer.remove();
      }
    };
    const ancestorClipPaintBounds = (element, outerSvg, cache) => {
      const clips = [];
      let current = element;
      while (current) {
        const clipValue = getComputedStyle(current).clipPath ||
          current.getAttribute?.("clip-path") || "";
        if (clipValue && clipValue !== "none") {
          const clip = clipPathPaintBounds(current, outerSvg, cache);
          if (clip) clips.push(clip);
        }
        if (current === outerSvg) break;
        current = current.parentElement;
      }
      return clips;
    };
    const applyAncestorClipBounds = (rect, clips) => {
      let clipped = rect;
      for (const clip of clips) {
        if (clip.empty) return null;
        if (clip.rect) clipped = intersectRects(clipped, clip.rect);
        if (!clipped) return null;
      }
      return clipped;
    };
    const applyClipBoundsToStrokeSample = (sample, clips) => {
      if (!sample?.points || !clips.length) return sample;
      return {
        ...sample,
        points: sample.points.map((point) => ({
          ...point,
          painted: point.painted && clips.every((clip) =>
            !clip.empty && (!clip.rect || rectContainsPoint(clip.rect, point))),
        })),
      };
    };
    const pointInsideClipBounds = (point, clips = []) => clips.every((clip) =>
      !clip.empty && (!clip.rect || rectContainsPoint(clip.rect, point)));
    const applyClipBoundsToPolygon = (polygon, clips = []) => {
      let clipped = polygon;
      for (const clip of clips) {
        if (clip.empty) return [];
        if (!clip.rect) continue;
        clipped = clipConvexPolygon(clipped, [
          { x: clip.rect.left, y: clip.rect.top },
          { x: clip.rect.right, y: clip.rect.top },
          { x: clip.rect.right, y: clip.rect.bottom },
          { x: clip.rect.left, y: clip.rect.bottom },
        ], true, true);
        if (!clipped.length) return [];
      }
      return clipped;
    };
    const elementAndAncestorsAreOpaque = (element, outerSvg) => {
      let current = element;
      while (current && current !== outerSvg.parentElement) {
        const style = getComputedStyle(current);
        if (Number(style.opacity || 1) < 0.999) return false;
        const filter = style.filter || style.getPropertyValue("filter") || "none";
        const mask = style.maskImage || style.getPropertyValue("mask-image") ||
          style.getPropertyValue("mask") || "none";
        if (filter !== "none" || mask !== "none") return false;
        if ((style.mixBlendMode || "normal") !== "normal") return false;
        if (current === outerSvg) break;
        current = current.parentElement;
      }
      return true;
    };
    const opaqueFillElement = (geometry, outerSvg) => {
      const element = geometry._element;
      if (!element || element.tagName.toLowerCase() !== "rect") return false;
      // Clip paths are represented by conservative bounds for overflow
      // auditing. They are not exact enough to prove that every point in a
      // disjoint or concave clip is painted, so never use a clipped shape as
      // an occlusion suppressor.
      if (geometry._clipBounds?.length) return false;
      // Only an axis-aligned, square-cornered rect lets the four cardinal
      // radius probes prove that the complete circular stroke cross-section
      // is covered. Other filled shapes remain collision candidates.
      const matrix = element.getScreenCTM();
      const rx = Number(element.rx?.baseVal?.value || 0);
      const ry = Number(element.ry?.baseVal?.value || 0);
      if (!matrix || Math.abs(matrix.b) > 1e-7 || Math.abs(matrix.c) > 1e-7 ||
          rx > 1e-7 || ry > 1e-7) return false;
      const style = getComputedStyle(element);
      if (!fillIsVisible(element) || Number(style.fillOpacity || 1) < 0.999) return false;
      const fill = String(style.fill || "").trim().toLowerCase();
      if (!fill || fill === "none" || fill === "transparent" || fill.startsWith("url(")) {
        return false;
      }
      const rgb = fill.match(/^rgba?\((.*)\)$/);
      // Chrome normally serializes opaque CSS colors as rgb(...). Unknown
      // color syntaxes are kept conservative rather than hiding collisions.
      if (!rgb) return false;
      const body = rgb[1].trim();
      const slashParts = body.split("/");
      const commaParts = body.split(",");
      const alphaToken = slashParts.length === 2 ? slashParts[1].trim() :
        (commaParts.length === 4 ? commaParts[3].trim() : "1");
      const alpha = alphaToken.endsWith("%") ?
        Number.parseFloat(alphaToken) / 100 : Number.parseFloat(alphaToken);
      if (!Number.isFinite(alpha) || alpha < 0.999) return false;
      return elementAndAncestorsAreOpaque(element, outerSvg);
    };
    const screenPointInElementFill = (element, point) => {
      try {
        if (typeof element.isPointInFill !== "function") return false;
        const matrix = element.getScreenCTM();
        if (!matrix) return false;
        const inverse = new DOMMatrix([
          matrix.a,
          matrix.b,
          matrix.c,
          matrix.d,
          matrix.e,
          matrix.f,
        ]).inverse();
        const local = new DOMPoint(point.x, point.y).matrixTransform(inverse);
        return element.isPointInFill(local);
      } catch {
        return false;
      }
    };
    const opaqueGeometryCoversStrokePoint = (geometry, point, strokeRadius) => {
      const radius = Math.max(0, strokeRadius || 0) + 0.25;
      const offsets = radius > 0 ? [
        [0, 0], [radius, 0], [-radius, 0], [0, radius], [0, -radius],
      ] : [[0, 0]];
      return offsets.every(([dx, dy]) => {
        const candidatePoint = { x: point.x + dx, y: point.y + dy };
        if (!rectContainsPoint(geometry.rect, candidatePoint)) return false;
        if (geometry._clipBounds?.some((clip) =>
          clip.empty || (clip.rect && !rectContainsPoint(clip.rect, candidatePoint)))) {
          return false;
        }
        return screenPointInElementFill(geometry._element, candidatePoint);
      });
    };
    const renderedTextHeight = (element) => {
      try {
        const box = element.getBBox();
        const matrix = element.getScreenCTM();
        if (!matrix || !Number.isFinite(box.height)) throw new Error("text transform unavailable");
        return box.height * Math.hypot(matrix.c, matrix.d);
      } catch {
        return element.getBoundingClientRect().height;
      }
    };
    const isAuxiliaryText = (element, fontSizePx) => {
      const explicit = (element.getAttribute("data-text-role") || "").toLowerCase();
      if (["aux", "auxiliary", "caption", "tick", "legend", "note"].includes(explicit)) return true;
      if (["core", "primary", "heading"].includes(explicit)) return false;
      const ancestors = [element, element.parentElement, element.parentElement?.parentElement]
        .filter(Boolean);
      const hint = ancestors.map((node) => [
        node.id || "",
        typeof node.className === "string" ? node.className : (node.className?.baseVal ?? ""),
        node.getAttribute?.("aria-label") || "",
      ].join(" ")).join(" ").toLowerCase();
      if (/(?:^|[\s_-])(aux|axis|tick|legend|caption|note|annotation|minor|small)(?:$|[\s_-])/.test(hint)) {
        return true;
      }
      return fontSizePx <= config.auxiliaryTextMinPx + 0.5;
    };
    const sampleGeometryStroke = (element) => {
      try {
        if (typeof element.getTotalLength !== "function" ||
            typeof element.getPointAtLength !== "function") {
          throw new Error("SVG geometry length API is unavailable");
        }
        const matrix = element.getScreenCTM();
        if (!matrix) throw new Error("getScreenCTM returned null");
        const localLength = element.getTotalLength();
        if (!Number.isFinite(localLength) || localLength <= 0) {
          return {
            skipped: true,
            skipReason: "zero-length stroke",
            sampleCount: 0,
            points: [],
          };
        }
        const scale = Math.max(
          Math.hypot(matrix.a, matrix.b),
          Math.hypot(matrix.c, matrix.d),
          0.0001,
        );
        const style = getComputedStyle(element);
        const strokeScale = style.vectorEffect === "non-scaling-stroke" ? 1 : scale;
        const strokeWidthLocalPx = strokeIsVisible(element) ?
          (Number.parseFloat(style.strokeWidth) || 1) : 0;
        const strokeWidthScreenPx = strokeWidthLocalPx * strokeScale;
        let dashArray = style.strokeDasharray === "none" ? [] :
          style.strokeDasharray.split(/[\s,]+/).map((value) => Number.parseFloat(value))
            .filter((value) => Number.isFinite(value) && value >= 0);
        if (dashArray.length % 2 === 1) dashArray = [...dashArray, ...dashArray];
        if (!dashArray.some((value) => value > 0)) dashArray = [];
        const dashPatternLength = dashArray.reduce((sum, value) => sum + value, 0);
        const dashOffset = Number.parseFloat(style.strokeDashoffset) || 0;
        const paintedAt = (pathDistance) => {
          if (!dashArray.length || dashPatternLength <= 0) return true;
          let phase = (pathDistance + dashOffset) % dashPatternLength;
          if (phase < 0) phase += dashPatternLength;
          for (let dashIndex = 0; dashIndex < dashArray.length; dashIndex += 1) {
            if (phase < dashArray[dashIndex]) return dashIndex % 2 === 0;
            phase -= dashArray[dashIndex];
          }
          return true;
        };
        const estimatedScreenLengthPx = localLength * scale;
        const requiredSampleCount = Math.max(
          2,
          Math.ceil(estimatedScreenLengthPx / config.strokeSampleTargetSpacingPx) + 1,
        );
        if (requiredSampleCount > config.strokeMaxSamplePoints) {
          throw samplingLimitError(
            "stroke-sample-point-limit",
            "stroke sampling",
            requiredSampleCount,
            config.strokeMaxSamplePoints,
          );
        }
        const sampleCount = requiredSampleCount;
        reserveSamplePoints(sampleCount, "stroke sampling");
        const points = [];
        for (let sampleIndex = 0; sampleIndex < sampleCount; sampleIndex += 1) {
          const pathDistance = localLength * sampleIndex / (sampleCount - 1);
          const localPoint = element.getPointAtLength(pathDistance);
          const screenPoint = new DOMPoint(localPoint.x, localPoint.y).matrixTransform(matrix);
          points.push({
            sampleIndex,
            pathDistance,
            x: screenPoint.x,
            y: screenPoint.y,
            painted: paintedAt(pathDistance),
          });
        }
        return {
          skipped: false,
          localLength,
          estimatedScreenLengthPx,
          sampleCount,
          approximateSampleSpacingPx: estimatedScreenLengthPx / (sampleCount - 1),
          strokeWidthScreenPx,
          strokeHalfWidthScreenPx: strokeWidthScreenPx / 2,
          dashArray,
          dashOffset,
          collisionReachPx: Math.max(
            0,
            strokeWidthScreenPx / 2 - config.collisionTolerancePx,
          ),
          points,
        };
      } catch (error) {
        return {
          error: String(error?.message || error),
          samplingLimit: error?.auditLimit || null,
          sampleCount: 0,
          points: [],
        };
      }
    };
    const sampleFilledPaint = (element, effectivePolygon, usePaintHitTestFallback = false) => {
      try {
        if (!fillIsVisible(element) && !usePaintHitTestFallback) {
          return { skipped: true, skipReason: "fill is not visible", sampleCount: 0, points: [] };
        }
        const rect = rectForPoints(effectivePolygon);
        if (!rect || !(rect.width > 0) || !(rect.height > 0)) {
          return { skipped: true, skipReason: "empty fill bounds", sampleCount: 0, points: [] };
        }
        const columns = Math.max(1, Math.ceil(rect.width / config.fillSampleTargetSpacingPx));
        const rows = Math.max(1, Math.ceil(rect.height / config.fillSampleTargetSpacingPx));
        const requiredSampleCount = columns * rows;
        if (requiredSampleCount > config.fillMaxSamplePoints) {
          throw samplingLimitError(
            "fill-sample-point-limit",
            "fill sampling",
            requiredSampleCount,
            config.fillMaxSamplePoints,
          );
        }
        reserveSamplePoints(requiredSampleCount, "fill sampling");
        const matrix = element.getScreenCTM();
        if (!matrix) throw new Error("fill screen transform unavailable");
        const inverse = new DOMMatrix([
          matrix.a,
          matrix.b,
          matrix.c,
          matrix.d,
          matrix.e,
          matrix.f,
        ]).inverse();
        const supportsFillTest = typeof element.isPointInFill === "function";
        const points = [];
        const savedPointerEvents = element.style.getPropertyValue("pointer-events");
        const savedPointerEventsPriority = element.style.getPropertyPriority("pointer-events");
        if (!supportsFillTest && usePaintHitTestFallback) {
          element.style.setProperty("pointer-events", "visiblePainted", "important");
        }
        try {
          for (let row = 0; row < rows; row += 1) {
            for (let column = 0; column < columns; column += 1) {
              const point = {
                x: rect.left + (column + 0.5) * rect.width / columns,
                y: rect.top + (row + 0.5) * rect.height / rows,
              };
              if (!pointInPolygon(point, effectivePolygon)) continue;
              let painted = false;
              if (supportsFillTest) {
                const local = new DOMPoint(point.x, point.y).matrixTransform(inverse);
                painted = element.isPointInFill(local);
              } else if (usePaintHitTestFallback) {
                painted = document.elementsFromPoint(point.x, point.y).some((hit) =>
                  hit === element || element.contains(hit));
              }
              if (painted) points.push({ x: point.x, y: point.y });
            }
          }
        } finally {
          element.style.removeProperty("pointer-events");
          if (savedPointerEvents) {
            element.style.setProperty(
              "pointer-events",
              savedPointerEvents,
              savedPointerEventsPriority,
            );
          }
        }
        return {
          skipped: false,
          sampleCount: requiredSampleCount,
          filledSampleCount: points.length,
          approximateSampleWidthPx: rect.width / columns,
          approximateSampleHeightPx: rect.height / rows,
          approximateSampleAreaPx:
            rect.width / columns * (rect.height / rows),
          paintHitTestFallbackUsed: usePaintHitTestFallback && !supportsFillTest,
          points,
        };
      } catch (error) {
        return {
          error: String(error?.message || error),
          samplingLimit: error?.auditLimit || null,
          sampleCount: 0,
          points: [],
        };
      }
    };
    const markerReference = (element, position) => {
      const property = position === "start" ? "markerStart" :
        (position === "mid" ? "markerMid" : "markerEnd");
      const value = getComputedStyle(element)[property] ||
        element.getAttribute("marker-" + position) || "";
      if (!value || value === "none") return null;
      const match = String(value).match(/^url\(\s*['"]?([^'")]+)['"]?\s*\)$/i);
      if (!match) return { error: "unsupported marker reference: " + value };
      let id = "";
      try {
        const resolved = new URL(match[1], document.baseURI);
        const markerDocument = new URL(resolved.href);
        const currentDocument = new URL(document.location.href);
        markerDocument.hash = "";
        currentDocument.hash = "";
        if (markerDocument.href !== currentDocument.href) {
          return { error: "external marker reference is not auditable: " + value };
        }
        id = decodeURIComponent(resolved.hash.slice(1));
      } catch {
        id = match[1].startsWith("#") ? match[1].slice(1) : "";
      }
      const marker = id ? document.getElementById(id) : null;
      if (!marker || marker.tagName?.toLowerCase() !== "marker") {
        return { error: "marker target not found: " + value };
      }
      return { id, marker, value };
    };
    const pathMidDistances = (element) => {
      const data = element.getAttribute("d") || "";
      if (data.length > config.markerMaxPathDataCharacters) {
        throw samplingLimitError(
          "marker-path-character-limit",
          "marker path data characters",
          data.length,
          config.markerMaxPathDataCharacters,
        );
      }
      const tokens = data.match(/[AaCcHhLlMmQqSsTtVvZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?/g) || [];
      if (tokens.length > config.markerMaxPathTokens) {
        throw samplingLimitError(
          "marker-path-token-limit",
          "marker path tokens",
          tokens.length,
          config.markerMaxPathTokens,
        );
      }
      const arity = { M: 2, L: 2, H: 1, V: 1, C: 6, S: 4, Q: 4, T: 2, A: 7 };
      const subpaths = [];
      let active = null;
      let command = null;
      let index = 0;
      let current = { x: 0, y: 0 };
      let start = null;
      let vertexCount = 0;
      const checkVertexLimit = () => {
        vertexCount += 1;
        if (vertexCount > config.markerMaxPlacementsPerPosition + 2) {
          throw samplingLimitError(
            "marker-placement-limit",
            "marker path vertices",
            vertexCount,
            config.markerMaxPlacementsPerPosition + 2,
          );
        }
      };
      const measurementPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const measuredLength = () => {
        measurementPath.setAttribute("d", tokens.slice(0, index).join(" "));
        return measurementPath.getTotalLength();
      };
      const isCommand = (value) => /^[A-Za-z]$/.test(value);
      while (index < tokens.length) {
        if (isCommand(tokens[index])) {
          command = tokens[index];
          index += 1;
          if (command.toUpperCase() === "Z") {
            if (!active || !start) throw new Error("path close command has no active subpath");
            checkVertexLimit();
            active.push({ ...start, distance: measuredLength() });
            current = { ...start };
            command = null;
            continue;
          }
        }
        if (!command) throw new Error("path data is missing a command");
        const upper = command.toUpperCase();
        const count = arity[upper];
        if (!count || index + count > tokens.length || isCommand(tokens[index])) {
          throw new Error("unsupported or incomplete path command: " + command);
        }
        const values = tokens.slice(index, index + count).map(Number);
        if (!values.every(Number.isFinite)) throw new Error("path command contains a non-number");
        index += count;
        const relative = command === command.toLowerCase();
        let endpoint;
        if (["M", "L", "T"].includes(upper)) {
          endpoint = {
            x: values[0] + (relative ? current.x : 0),
            y: values[1] + (relative ? current.y : 0),
          };
        } else if (upper === "H") {
          endpoint = { x: values[0] + (relative ? current.x : 0), y: current.y };
        } else if (upper === "V") {
          endpoint = { x: current.x, y: values[0] + (relative ? current.y : 0) };
        } else if (upper === "C") {
          endpoint = {
            x: values[4] + (relative ? current.x : 0),
            y: values[5] + (relative ? current.y : 0),
          };
        } else if (["S", "Q"].includes(upper)) {
          endpoint = {
            x: values[2] + (relative ? current.x : 0),
            y: values[3] + (relative ? current.y : 0),
          };
        } else if (upper === "A") {
          endpoint = {
            x: values[5] + (relative ? current.x : 0),
            y: values[6] + (relative ? current.y : 0),
          };
        }
        if (upper === "M") {
          current = endpoint;
          start = { ...endpoint };
          checkVertexLimit();
          active = [{ ...endpoint, distance: measuredLength() }];
          subpaths.push(active);
          command = relative ? "l" : "L";
        } else {
          if (!active) throw new Error("path segment appears before moveto");
          current = endpoint;
          checkVertexLimit();
          active.push({ ...endpoint, distance: measuredLength() });
        }
      }
      const vertices = subpaths.flatMap((points) => points.map((vertex, vertexIndex) => {
        let boundaryDirection = null;
        if (vertexIndex === 0 && points.length > 1) {
          boundaryDirection = {
            x: points[1].x - vertex.x,
            y: points[1].y - vertex.y,
          };
        } else if (vertexIndex === points.length - 1 && points.length > 1) {
          boundaryDirection = {
            x: vertex.x - points[vertexIndex - 1].x,
            y: vertex.y - points[vertexIndex - 1].y,
          };
        }
        return { ...vertex, boundaryDirection };
      }));
      return vertices.slice(1, -1);
    };
    const markerPointPlacements = (element, position) => {
      try {
        if (typeof element.getTotalLength !== "function" ||
            typeof element.getPointAtLength !== "function") {
          throw new Error("marker host geometry length API is unavailable");
        }
        const totalLength = element.getTotalLength();
        if (!Number.isFinite(totalLength) || totalLength < 0) {
          throw new Error("marker host geometry has invalid length");
        }
        let distances = [];
        if (position === "start") distances = [0];
        else if (position === "end") distances = [totalLength];
        else {
          const tag = element.tagName.toLowerCase();
          if (tag === "path") distances = pathMidDistances(element);
          else {
            if (!["polyline", "polygon"].includes(tag)) return [];
            if (element.points.numberOfItems > config.markerMaxPlacementsPerPosition + 2) {
              throw samplingLimitError(
                "marker-placement-limit",
                "marker host vertices",
                element.points.numberOfItems,
                config.markerMaxPlacementsPerPosition + 2,
              );
            }
            const points = Array.from(
              { length: element.points.numberOfItems },
              (_, index) => element.points.getItem(index),
            ).map((point) => ({ x: point.x, y: point.y }));
            if (points.length < 3) return [];
            let travelled = 0;
            const lastMidIndex = tag === "polygon" ? points.length - 1 : points.length - 2;
            for (let index = 1; index <= lastMidIndex; index += 1) {
              travelled += Math.hypot(
                points[index].x - points[index - 1].x,
                points[index].y - points[index - 1].y,
              );
              distances.push(Math.min(totalLength, travelled));
            }
          }
        }
        if (distances.length > config.markerMaxPlacementsPerPosition) {
          throw samplingLimitError(
            "marker-placement-limit",
            "marker-" + position + " placements",
            distances.length,
            config.markerMaxPlacementsPerPosition,
          );
        }
        const epsilon = Math.min(0.5, Math.max(0.01, totalLength / 10_000));
        return distances.map((distanceValue, placementIndex) => {
          const placement = typeof distanceValue === "number" ?
            { distance: distanceValue } : distanceValue;
          const distance = placement.distance;
          const point = Number.isFinite(placement.x) && Number.isFinite(placement.y) ?
            placement : element.getPointAtLength(distance);
          const before = element.getPointAtLength(Math.max(0, distance - epsilon));
          const after = element.getPointAtLength(Math.min(totalLength, distance + epsilon));
          const incoming = { x: point.x - before.x, y: point.y - before.y };
          const outgoing = { x: after.x - point.x, y: after.y - point.y };
          const normalize = (vector) => {
            const length = Math.hypot(vector.x, vector.y);
            return length > 1e-7 ? { x: vector.x / length, y: vector.y / length } : null;
          };
          const incomingUnit = normalize(incoming);
          const outgoingUnit = normalize(outgoing);
          let direction;
          if (placement.boundaryDirection) direction = normalize(placement.boundaryDirection);
          else if (position === "start") direction = outgoingUnit || incomingUnit;
          else if (position === "end") direction = incomingUnit || outgoingUnit;
          else if (incomingUnit && outgoingUnit) {
            direction = normalize({
              x: incomingUnit.x + outgoingUnit.x,
              y: incomingUnit.y + outgoingUnit.y,
            }) || outgoingUnit;
          } else direction = outgoingUnit || incomingUnit;
          return {
            placementIndex,
            distance,
            x: point.x,
            y: point.y,
            autoAngleDeg: direction ? Math.atan2(direction.y, direction.x) * 180 / Math.PI : 0,
          };
        });
      } catch (error) {
        return {
          error: String(error?.message || error),
          samplingLimit: error?.auditLimit || null,
        };
      }
    };
    const markerAngle = (marker, placement, position) => {
      const orient = (marker.getAttribute("orient") || "0").trim().toLowerCase();
      if (orient === "auto" || orient === "auto-start-reverse") {
        return placement.autoAngleDeg +
          (orient === "auto-start-reverse" && position === "start" ? 180 : 0);
      }
      const match = orient.match(/^([-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?)\s*(deg|grad|rad|turn)?$/i);
      if (!match) return { error: "unsupported marker orient: " + orient };
      const value = Number(match[1]);
      const unit = match[2] || "deg";
      if (unit === "rad") return value * 180 / Math.PI;
      if (unit === "grad") return value * 0.9;
      if (unit === "turn") return value * 360;
      return value;
    };
    const markerViewport = (marker) => {
      const numericLength = (property, attribute, fallback) => {
        const animated = marker[property]?.baseVal?.value;
        if (Number.isFinite(animated)) return animated;
        const parsed = Number.parseFloat(marker.getAttribute(attribute) || "");
        return Number.isFinite(parsed) ? parsed : fallback;
      };
      const width = numericLength("markerWidth", "markerWidth", 3);
      const height = numericLength("markerHeight", "markerHeight", 3);
      const refX = numericLength("refX", "refX", 0);
      const refY = numericLength("refY", "refY", 0);
      const rawViewBox = marker.getAttribute("viewBox") || "";
      const parsedViewBox = rawViewBox.trim().split(/[\s,]+/)
        .map((value) => Number.parseFloat(value));
      const hasViewBox = parsedViewBox.length === 4 && parsedViewBox.every(Number.isFinite) &&
        parsedViewBox[2] > 0 && parsedViewBox[3] > 0;
      let mappedRefX = refX;
      let mappedRefY = refY;
      if (hasViewBox) {
        const [minX, minY, boxWidth, boxHeight] = parsedViewBox;
        const preserve = (marker.getAttribute("preserveAspectRatio") || "xMidYMid meet")
          .trim().split(/\s+/);
        const align = preserve[0] === "defer" ? preserve[1] : preserve[0];
        const mode = preserve.includes("slice") ? "slice" : "meet";
        let scaleX = width / boxWidth;
        let scaleY = height / boxHeight;
        let offsetX = 0;
        let offsetY = 0;
        if (align !== "none") {
          const scale = mode === "slice" ? Math.max(scaleX, scaleY) : Math.min(scaleX, scaleY);
          scaleX = scale;
          scaleY = scale;
          const spareX = width - boxWidth * scale;
          const spareY = height - boxHeight * scale;
          offsetX = /xMid/i.test(align) ? spareX / 2 : (/xMax/i.test(align) ? spareX : 0);
          offsetY = /YMid/i.test(align) ? spareY / 2 : (/YMax/i.test(align) ? spareY : 0);
        }
        mappedRefX = (refX - minX) * scaleX + offsetX;
        mappedRefY = (refY - minY) * scaleY + offsetY;
      }
      return {
        width,
        height,
        refX,
        refY,
        mappedRefX,
        mappedRefY,
        rawViewBox,
        preserveAspectRatio: marker.getAttribute("preserveAspectRatio") || "",
      };
    };
    const markerPaintInstances = (host, outerSvg) => {
      const records = [];
      const errors = [];
      const hostClipBounds = ancestorClipPaintBounds(host, outerSvg, new WeakMap());
      if (activeSampleBudget?.exhausted) {
        return {
          records,
          errors: [{
            hostSelector: selector(host),
            error: "SVG sample budget was already exhausted; marker audit skipped",
            samplingLimit: {
              code: "svg-sample-point-limit",
              scope: "marker audit after SVG sample budget exhaustion",
              observed: activeSampleBudget.used + 1,
              limit: activeSampleBudget.limit,
              action: "skipped",
            },
          }],
        };
      }
      const namespace = "http://www.w3.org/2000/svg";
      for (const position of ["start", "mid", "end"]) {
        const reference = markerReference(host, position);
        if (!reference) continue;
        if (reference.error) {
          errors.push({ position, error: reference.error });
          continue;
        }
        const placements = markerPointPlacements(host, position);
        if (placements.error) {
          errors.push({
            position,
            markerId: reference.id,
            error: placements.error,
            samplingLimit: placements.samplingLimit || null,
          });
          continue;
        }
        const viewport = markerViewport(reference.marker);
        const markerUnits = (reference.marker.getAttribute("markerUnits") || "strokeWidth")
          .trim().toLowerCase();
        const markerStyle = getComputedStyle(reference.marker);
        const markerOverflowX = markerStyle.overflowX || markerStyle.overflow || "hidden";
        const markerOverflowY = markerStyle.overflowY || markerStyle.overflow || "hidden";
        const markerClipsHorizontal = markerOverflowX !== "visible";
        const markerClipsVertical = markerOverflowY !== "visible";
        const unitScale = markerUnits === "userspaceonuse" ? 1 :
          Math.max(0, Number.parseFloat(getComputedStyle(host).strokeWidth) || 1);
        const outerMatrix = outerSvg.getScreenCTM();
        const hostMatrix = host.getScreenCTM();
        if (!outerMatrix || !hostMatrix) {
          errors.push({ position, markerId: reference.id, error: "marker screen transform unavailable" });
          continue;
        }
        for (const placement of placements) {
          const angle = markerAngle(reference.marker, placement, position);
          if (typeof angle === "object" && angle.error) {
            errors.push({ position, markerId: reference.id, error: angle.error });
            continue;
          }
          const layer = document.createElementNS(namespace, "g");
          layer.setAttribute("data-audit-marker-root", "");
          layer.setAttribute("pointer-events", "none");
          const localMarkerMatrix = new DOMMatrix()
            .translate(placement.x, placement.y)
            .rotate(angle)
            .scale(unitScale);
          const domMatrix = (matrix) => new DOMMatrix([
            matrix.a,
            matrix.b,
            matrix.c,
            matrix.d,
            matrix.e,
            matrix.f,
          ]);
          const markerToOuter = domMatrix(outerMatrix).inverse()
            .multiply(domMatrix(hostMatrix))
            .multiply(localMarkerMatrix);
          layer.setAttribute("transform", "matrix(" + [
            markerToOuter.a,
            markerToOuter.b,
            markerToOuter.c,
            markerToOuter.d,
            markerToOuter.e,
            markerToOuter.f,
          ].join(" ") + ")");
          const viewportSvg = document.createElementNS(namespace, "svg");
          viewportSvg.setAttribute("x", String(-viewport.mappedRefX));
          viewportSvg.setAttribute("y", String(-viewport.mappedRefY));
          viewportSvg.setAttribute("width", String(viewport.width));
          viewportSvg.setAttribute("height", String(viewport.height));
          if (viewport.rawViewBox) viewportSvg.setAttribute("viewBox", viewport.rawViewBox);
          if (viewport.preserveAspectRatio) {
            viewportSvg.setAttribute("preserveAspectRatio", viewport.preserveAspectRatio);
          }
          viewportSvg.setAttribute("overflow", "visible");
          for (const attribute of reference.marker.attributes) {
            if (["id", "markerwidth", "markerheight", "markerunits", "refx", "refy",
              "orient", "viewbox", "preserveaspectratio", "overflow"].includes(
              attribute.name.toLowerCase(),
            )) continue;
            viewportSvg.setAttribute(attribute.name, attribute.value);
          }
          viewportSvg.style.setProperty("width", String(viewport.width) + "px", "important");
          viewportSvg.style.setProperty("height", String(viewport.height) + "px", "important");
          viewportSvg.style.setProperty("overflow", "visible", "important");
          viewportSvg.style.setProperty("display", "block", "important");
          for (const child of reference.marker.childNodes) {
            viewportSvg.appendChild(
              child.nodeType === Node.ELEMENT_NODE ?
                cloneMarkerNodeWithComputedStyles(child, host) : child.cloneNode(true),
            );
          }
          layer.appendChild(viewportSvg);
          outerSvg.appendChild(layer);
          try {
            const layerMatrix = layer.getScreenCTM();
            if (!layerMatrix) throw new Error("marker viewport screen transform unavailable");
            const markerViewportPoints = [
              new DOMPoint(-viewport.mappedRefX, -viewport.mappedRefY),
              new DOMPoint(-viewport.mappedRefX + viewport.width, -viewport.mappedRefY),
              new DOMPoint(
                -viewport.mappedRefX + viewport.width,
                -viewport.mappedRefY + viewport.height,
              ),
              new DOMPoint(-viewport.mappedRefX, -viewport.mappedRefY + viewport.height),
            ].map((point) => point.matrixTransform(layerMatrix));
            const markerViewportRect = rectForPoints(markerViewportPoints);
            if (!markerViewportRect) throw new Error("marker viewport bounds unavailable");
            const candidates = [...viewportSvg.querySelectorAll(
              "line, polyline, polygon, path, rect, circle, ellipse, text, tspan, use, image, foreignObject",
            )]
              .filter((element) => element.tagName.toLowerCase() === "tspan" ||
                !element.querySelector("tspan"))
              .filter(displayed)
              .filter((element) => !element.closest("defs, clipPath, mask, symbol, pattern"))
              .filter((element) => {
                const tag = element.tagName.toLowerCase();
                if (["text", "tspan"].includes(tag)) return textPaintIsVisible(element);
                return paintElementIsVisible(element);
              });
            const markerClipBoundsCache = new WeakMap();
            if (candidates.length > config.markerMaxPaintItemsPerPlacement) {
              errors.push({
                position,
                markerId: reference.id,
                error: "marker placement has " + candidates.length +
                  " paint items; limit is " + config.markerMaxPaintItemsPerPlacement,
                samplingLimit: {
                  code: "marker-paint-item-limit",
                  scope: "marker paint items per placement",
                  observed: candidates.length,
                  limit: config.markerMaxPaintItemsPerPlacement,
                  action: "skipped",
                },
              });
              return {
                records,
                errors: errors.map((error) => ({
                  ...error,
                  hostSelector: selector(host),
                })),
              };
            }
            if (records.length + candidates.length > config.markerMaxPaintRecordsPerHost) {
              errors.push({
                position,
                markerId: reference.id,
                error: "marker paint record limit exceeded: " +
                  config.markerMaxPaintRecordsPerHost,
                samplingLimit: {
                  code: "marker-paint-record-limit",
                  scope: "marker paint records per host",
                  observed: records.length + candidates.length,
                  limit: config.markerMaxPaintRecordsPerHost,
                  action: "skipped",
                },
              });
              return {
                records,
                errors: errors.map((error) => ({ ...error, hostSelector: selector(host) })),
              };
            }
            for (const [paintIndex, element] of candidates.entries()) {
              const tag = element.tagName.toLowerCase();
              const rawRect = ["text", "tspan"].includes(tag) ?
                element.getBoundingClientRect() : geometryRect(element);
              if (!rawRect || !(rawRect.width > 0) || !(rawRect.height > 0)) continue;
              const rawPaintQuad = paintQuadForElement(element, rawRect);
              const clipBounds = [
                ...hostClipBounds,
                ...ancestorClipPaintBounds(element, outerSvg, markerClipBoundsCache),
              ];
              const clippedPaintQuad = applyClipBoundsToPolygon(rawPaintQuad, clipBounds);
              if (!clippedPaintQuad.length) continue;
              const markerViewportOutside = polygonOutside(
                clippedPaintQuad,
                markerViewportPoints,
                config.layoutTolerancePx,
              );
              const markerInternalClipped =
                (markerViewportOutside.sides.left && markerClipsHorizontal) ||
                (markerViewportOutside.sides.right && markerClipsHorizontal) ||
                (markerViewportOutside.sides.top && markerClipsVertical) ||
                (markerViewportOutside.sides.bottom && markerClipsVertical);
              const effectivePaintPolygon = clipConvexPolygon(
                clippedPaintQuad,
                markerViewportPoints,
                markerClipsHorizontal,
                markerClipsVertical,
              );
              const rect = rectForPoints(effectivePaintPolygon);
              if (!rect) {
                errors.push({
                  position,
                  markerId: reference.id,
                  error: "marker paint is fully clipped by its marker viewport",
                });
                continue;
              }
              const canSample = typeof element.getTotalLength === "function" &&
                typeof element.getPointAtLength === "function";
              let sample = canSample ? sampleGeometryStroke(element) : null;
              sample = applyClipBoundsToStrokeSample(sample, clipBounds);
              const strokeVisible = canSample && strokeIsVisible(element);
              if (sample?.points && (markerClipsHorizontal || markerClipsVertical)) {
                sample.points = sample.points.map((point) => ({
                  ...point,
                  painted: point.painted && pointInsideClipEdges(
                    point,
                    markerViewportPoints,
                    markerClipsHorizontal,
                    markerClipsVertical,
                  ),
                }));
              }
              const fillSample = sampleFilledPaint(
                element,
                effectivePaintPolygon,
                ["use", "image", "foreignobject"].includes(tag),
              );
              records.push({
                tag: "marker-" + tag,
                selector: selector(host) + "::marker-" + position + "(#" + reference.id + ")" +
                  "[" + placement.placementIndex + "] > " + tag + ":nth-paint(" +
                  (paintIndex + 1) + ")",
                rect,
                rawPaintRect: rectValue(rawRect),
                markerViewportRect: rectValue(markerViewportRect),
                markerViewportQuad: markerViewportPoints.map((point) => ({
                  x: round(point.x),
                  y: round(point.y),
                })),
                effectivePaintPolygon: effectivePaintPolygon.map((point) => ({
                  x: round(point.x),
                  y: round(point.y),
                })),
                markerInternalClipped,
                markerViewportOutside,
                sample,
                fillSample,
                fillVisible: !fillSample.error && !fillSample.skipped,
                fillPaintVisible: fillIsVisible(element),
                strokeVisible,
                _clipBounds: clipBounds,
                _hostElement: host,
                marker: {
                  id: reference.id,
                  position,
                  placementIndex: placement.placementIndex,
                  hostSelector: selector(host),
                  markerUnits,
                  overflowX: markerOverflowX,
                  overflowY: markerOverflowY,
                  angleDeg: round(angle),
                  point: { x: round(placement.x), y: round(placement.y) },
                  viewport,
                },
              });
              if (activeSampleBudget?.exhausted) {
                return {
                  records,
                  errors: errors.map((error) => ({
                    ...error,
                    hostSelector: selector(host),
                  })),
                };
              }
            }
          } finally {
            layer.remove();
          }
        }
      }
      return {
        records,
        errors: errors.map((error) => ({ ...error, hostSelector: selector(host) })),
      };
    };
    const strokeTextIntersection = (
      sample,
      textRect,
      textQuad = null,
      pointOccluded = null,
      textClipBounds = [],
    ) => {
      const reach = sample.collisionReachPx || 0;
      const collisionZone = {
        left: textRect.left - reach,
        right: textRect.right + reach,
        top: textRect.top - reach,
        bottom: textRect.bottom + reach,
      };
      let insideSampleCount = 0;
      let rawInsideSampleCount = 0;
      let occludedInsideSampleCount = 0;
      let consecutive = 0;
      let maximumConsecutive = 0;
      let totalInsideLengthPx = 0;
      let currentInsideLengthPx = 0;
      let longestContinuousInsideLengthPx = 0;
      let previous = null;
      let previousInside = false;
      const intersectionPoints = [];
      const intersectionBounds = {
        left: Infinity,
        top: Infinity,
        right: -Infinity,
        bottom: -Infinity,
      };

      for (const point of sample.points) {
        if (!point.painted || !pointInsideClipBounds(point, textClipBounds)) {
          consecutive = 0;
          currentInsideLengthPx = 0;
          previous = point;
          previousInside = false;
          continue;
        }
        const insideCoarse = point.x >= collisionZone.left && point.x <= collisionZone.right &&
          point.y >= collisionZone.top && point.y <= collisionZone.bottom;
        const rawInsideCoarse = point.x >= textRect.left && point.x <= textRect.right &&
          point.y >= textRect.top && point.y <= textRect.bottom;
        const inside = insideCoarse && (!textQuad ||
          pointInExpandedQuad(point, textQuad, reach));
        const rawInside = rawInsideCoarse && (!textQuad || pointInConvexQuad(point, textQuad));
        if (inside && pointOccluded?.(point)) {
          occludedInsideSampleCount += 1;
          consecutive = 0;
          currentInsideLengthPx = 0;
          previous = point;
          previousInside = false;
          continue;
        }
        if (inside) {
          insideSampleCount += 1;
          if (rawInside) rawInsideSampleCount += 1;
          consecutive += 1;
          maximumConsecutive = Math.max(maximumConsecutive, consecutive);
          intersectionBounds.left = Math.min(intersectionBounds.left, point.x);
          intersectionBounds.top = Math.min(intersectionBounds.top, point.y);
          intersectionBounds.right = Math.max(intersectionBounds.right, point.x);
          intersectionBounds.bottom = Math.max(intersectionBounds.bottom, point.y);
          if (intersectionPoints.length < 24) {
            intersectionPoints.push({
              sampleIndex: point.sampleIndex,
              pathDistance: round(point.pathDistance),
              x: round(point.x),
              y: round(point.y),
              centerInsideTextBBox: rawInside,
            });
          }
          if (previousInside && previous) {
            const segmentLength = Math.hypot(point.x - previous.x, point.y - previous.y);
            totalInsideLengthPx += segmentLength;
            currentInsideLengthPx += segmentLength;
            longestContinuousInsideLengthPx = Math.max(
              longestContinuousInsideLengthPx,
              currentInsideLengthPx,
            );
          } else {
            currentInsideLengthPx = 0;
          }
        } else {
          consecutive = 0;
          currentInsideLengthPx = 0;
        }
        previous = point;
        previousInside = inside;
      }

      const hardCollision = maximumConsecutive >= config.strokeMinConsecutivePoints &&
        longestContinuousInsideLengthPx >= config.strokeMinIntersectionLengthPx;
      return {
        hardCollision,
        insideSampleCount,
        rawInsideSampleCount,
        occludedInsideSampleCount,
        maximumConsecutiveInsideSamples: maximumConsecutive,
        totalInsideLengthPx: round(totalInsideLengthPx),
        longestContinuousInsideLengthPx: round(longestContinuousInsideLengthPx),
        intersectionPointCount: insideSampleCount,
        intersectionPointsTruncated: insideSampleCount > intersectionPoints.length,
        intersectionPoints,
        intersectionBounds: insideSampleCount ? {
          left: round(intersectionBounds.left),
          top: round(intersectionBounds.top),
          right: round(intersectionBounds.right),
          bottom: round(intersectionBounds.bottom),
          width: round(intersectionBounds.right - intersectionBounds.left),
          height: round(intersectionBounds.bottom - intersectionBounds.top),
        } : null,
      };
    };
    const filledSampleTextIntersection = (
      fillSample,
      textQuad,
      geometryClipBounds = [],
      textClipBounds = [],
    ) => {
      const intersectionPoints = fillSample.points.filter((point) =>
        pointInConvexQuad(point, textQuad) &&
        pointInsideClipBounds(point, geometryClipBounds) &&
        pointInsideClipBounds(point, textClipBounds));
      const approximateIntersectionAreaPx = intersectionPoints.length *
        (fillSample.approximateSampleAreaPx || 0);
      return {
        hardCollision:
          intersectionPoints.length >= config.fillMinIntersectionPoints &&
          approximateIntersectionAreaPx >= config.fillMinIntersectionAreaPx,
        intersectionPointCount: intersectionPoints.length,
        approximateIntersectionAreaPx: round(approximateIntersectionAreaPx),
        minimumIntersectionPointCount: config.fillMinIntersectionPoints,
        minimumIntersectionAreaPx: config.fillMinIntersectionAreaPx,
        paintHitTestFallbackUsed: Boolean(fillSample.paintHitTestFallbackUsed),
        intersectionPointsTruncated: intersectionPoints.length > 24,
        intersectionPoints: intersectionPoints.slice(0, 24).map((point) => ({
          x: round(point.x),
          y: round(point.y),
        })),
      };
    };
    const polygonFillTextIntersection = (geometry, text) => {
      if (!geometry.fillPolygon?.length || !geometry.fillVisible) {
        return { hardCollision: false, skipped: true, skipReason: "fill is not visible" };
      }
      try {
        if (typeof geometry._element.isPointInFill !== "function") {
          throw new Error("polygon fill hit-test API is unavailable");
        }
        const columns = 8;
        const rows = 8;
        reserveSamplePoints(columns * rows, "polygon fill-text sampling");
        const matrix = geometry._element.getScreenCTM();
        if (!matrix) throw new Error("polygon fill screen transform unavailable");
        const inverse = new DOMMatrix([
          matrix.a,
          matrix.b,
          matrix.c,
          matrix.d,
          matrix.e,
          matrix.f,
        ]).inverse();
        const intersectionPoints = [];
        for (let row = 0; row < rows; row += 1) {
          for (let column = 0; column < columns; column += 1) {
            const point = {
              x: text._paintRect.left + (column + 0.5) * text._paintRect.width / columns,
              y: text._paintRect.top + (row + 0.5) * text._paintRect.height / rows,
            };
            if (!pointInConvexQuad(point, text._paintQuad)) continue;
            if (!pointInsideClipBounds(point, geometry._clipBounds)) continue;
            if (!pointInsideClipBounds(point, text._clipBounds)) continue;
            const local = new DOMPoint(point.x, point.y).matrixTransform(inverse);
            if (geometry._element.isPointInFill(local)) intersectionPoints.push(point);
          }
        }
        const textQuadAreaPx = text._paintRect.width * text._paintRect.height;
        const approximateIntersectionAreaPx = intersectionPoints.length *
          textQuadAreaPx / (columns * rows);
        const containsTextQuad = text._paintQuad.every((point) => {
          if (!pointInsideClipBounds(point, geometry._clipBounds)) return false;
          if (!pointInsideClipBounds(point, text._clipBounds)) return false;
          const local = new DOMPoint(point.x, point.y).matrixTransform(inverse);
          return geometry._element.isPointInFill(local);
        });
        const relation = text._element.compareDocumentPosition(geometry._element);
        const geometryPaintsAfterText = Boolean(relation & Node.DOCUMENT_POSITION_FOLLOWING);
        const hasPaintOverlap =
          intersectionPoints.length >= config.fillMinIntersectionPoints &&
          approximateIntersectionAreaPx >= config.fillMinIntersectionAreaPx;
        return {
          hardCollision: hasPaintOverlap && geometryPaintsAfterText,
          skipped: false,
          intersectionPointCount: intersectionPoints.length,
          approximateIntersectionAreaPx: round(approximateIntersectionAreaPx),
          minimumIntersectionPointCount: config.fillMinIntersectionPoints,
          minimumIntersectionAreaPx: config.fillMinIntersectionAreaPx,
          containsTextQuad,
          geometryPaintsAfterText,
          behindTextSuppressed: hasPaintOverlap && !geometryPaintsAfterText,
          intersectionPoints: intersectionPoints.slice(0, 24).map((point) => ({
            x: round(point.x),
            y: round(point.y),
          })),
          intersectionPointsTruncated: intersectionPoints.length > 24,
        };
      } catch (error) {
        return {
          hardCollision: false,
          error: String(error?.message || error),
          samplingLimit: error?.auditLimit || null,
        };
      }
    };
    const tableTags = new Set(["table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "colgroup", "col"]);
    const wrapperOverflow = new Map();
    const wrapperPaintEscapes = new Map();
    const viewportRect = { left: 0, right: root.clientWidth };
    const svgResults = [];

    const visibleSvgs = [...document.querySelectorAll("svg")].filter(visibleBox);
    for (const [svgIndex, svg] of visibleSvgs.entries()) {
      activeSampleBudget = {
        used: 0,
        limit: config.totalMaxSamplePointsPerSvg,
        exhausted: false,
      };
      const svgRect = svg.getBoundingClientRect();
      const container = nearestContainer(svg);
      const containerRect = container.getBoundingClientRect();
      const outsideViewport = horizontalOutside(svgRect, viewportRect, config.layoutTolerancePx);
      const outsideContainer = horizontalOutside(svgRect, containerRect, config.layoutTolerancePx);

      let wrapper = svg.parentElement;
      while (wrapper && wrapper !== root) {
        const tag = wrapper.tagName.toLowerCase();
        const clientWidth = Number(wrapper.clientWidth) || 0;
        const scrollWidth = Number(wrapper.scrollWidth) || 0;
        const wrapperRect = wrapper.getBoundingClientRect();
        const layoutWidth = Number(wrapper.offsetWidth) || clientWidth;
        const scaleX = layoutWidth > 0 ? wrapperRect.width / layoutWidth : 1;
        const innerClientLeft = wrapperRect.left + (Number(wrapper.clientLeft) || 0) * scaleX;
        const innerClientWidth = clientWidth * scaleX;
        const innerClientRect = {
          left: innerClientLeft,
          right: innerClientLeft + innerClientWidth,
        };
        const svgOutsideInnerClientBox = horizontalOutside(
          svgRect,
          innerClientRect,
          config.layoutTolerancePx,
        );
        const svgWidthExceedsClient =
          svgRect.width > innerClientWidth + config.layoutTolerancePx;
        const linkedToSvg = svgOutsideInnerClientBox.outside || svgWidthExceedsClient;
        if (!tableTags.has(tag) && clientWidth > 0 &&
            scrollWidth > clientWidth + config.layoutTolerancePx / Math.max(scaleX, 0.0001) &&
            linkedToSvg) {
          const key = selector(wrapper);
          if (!wrapperOverflow.has(key)) {
            wrapperOverflow.set(key, {
              ...describe(wrapper),
              overflowPx: round(scrollWidth - clientWidth),
              innerClientBox: {
                left: round(innerClientRect.left),
                right: round(innerClientRect.right),
                width: round(innerClientWidth),
              },
              svgOutsideInnerClientBox,
              svgWidthExceedsClient,
              svgIndexes: [svgIndex],
            });
          } else {
            wrapperOverflow.get(key).svgIndexes.push(svgIndex);
          }
        }
        wrapper = wrapper.parentElement;
      }

      const svgStyle = getComputedStyle(svg);
      const svgOverflowX = svgStyle.overflowX || svgStyle.overflow || "hidden";
      const svgOverflowY = svgStyle.overflowY || svgStyle.overflow || "hidden";
      const svgClipsHorizontal = svgOverflowX !== "visible";
      const svgClipsVertical = svgOverflowY !== "visible";
      const clippingStatus = (outside) => {
        const clippedSides = {
          left: outside.sides.left && svgClipsHorizontal,
          right: outside.sides.right && svgClipsHorizontal,
          top: outside.sides.top && svgClipsVertical,
          bottom: outside.sides.bottom && svgClipsVertical,
        };
        return {
          ...outside,
          clipped: Object.values(clippedSides).some(Boolean),
          clippedSides,
        };
      };
      const clipPathBoundsCache = new WeakMap();

      // A multi-line <text> bbox hides the real height of each line, and a
      // rotated bbox swaps visual width/height. Audit leaf text fragments and
      // derive rendered glyph height from the SVG screen transform instead.
      const textElements = [...svg.querySelectorAll("text, tspan")]
        .filter((element) => element.closest("svg") === svg)
        .filter((element) => element.tagName.toLowerCase() === "tspan" ||
          !element.querySelector("tspan"))
        .filter(visibleBox)
        .filter(textPaintIsVisible);
      const texts = textElements.map((element, textIndex) => {
        const rawRect = element.getBoundingClientRect();
        const clipBounds = ancestorClipPaintBounds(element, svg, clipPathBoundsCache);
        const paintRect = applyAncestorClipBounds(rawRect, clipBounds);
        if (!paintRect) return null;
        const style = getComputedStyle(element);
        const fontSizePx = Number.parseFloat(style.fontSize) || 0;
        const actualRenderedHeightPx = renderedTextHeight(element);
        const role = isAuxiliaryText(element, fontSizePx) ? "auxiliary" : "core";
        const thresholdPx = role === "auxiliary" ?
          config.auxiliaryTextMinPx : config.coreTextMinPx;
        const paintBoundsOutsideSvg = clippingStatus(
          boundsOutside(paintRect, svgRect, config.layoutTolerancePx),
        );
        return {
          textIndex,
          tag: element.tagName.toLowerCase(),
          selector: selector(element),
          text: (element.textContent || "").replace(/\s+/g, " ").trim().slice(0, 120),
          role,
          fontSizePx: round(fontSizePx),
          renderedHeightPx: round(actualRenderedHeightPx),
          thresholdPx,
          tooSmall: actualRenderedHeightPx + 0.25 < thresholdPx,
          rect: rectValue(paintRect),
          paintBoundsOutsideSvg,
          _rect: rawRect,
          _paintRect: paintRect,
          _paintQuad: quadForElement(element, rawRect),
          _clipBounds: clipBounds,
          _textOwner: element.closest("text"),
          _element: element,
        };
      }).filter(Boolean);

      const collisionPairInspectionBudget = {
        used: 0,
        limit: config.collisionMaxPairInspectionsPerSvg,
        exhausted: false,
      };
      const collisionAuditErrors = [];
      const reserveCollisionPairInspection = () => {
        const observed = collisionPairInspectionBudget.used + 1;
        if (observed > collisionPairInspectionBudget.limit) {
          collisionPairInspectionBudget.exhausted = true;
          if (!collisionAuditErrors.length) {
            collisionAuditErrors.push({
              error: "collision pair inspection limit exceeded: " +
                collisionPairInspectionBudget.limit,
              samplingLimit: {
                code: "collision-pair-inspection-limit",
                scope: "collision pair inspections per SVG",
                observed,
                limit: collisionPairInspectionBudget.limit,
                action: "skipped",
              },
            });
          }
          return false;
        }
        collisionPairInspectionBudget.used = observed;
        return true;
      };
      const textTextCollisions = [];
      const textTextRejectedCoarseCandidates = [];
      let textTextCoarseCandidateCount = 0;
      textCollisionAudit:
      for (let leftIndex = 0; leftIndex < texts.length; leftIndex += 1) {
        for (let rightIndex = leftIndex + 1; rightIndex < texts.length; rightIndex += 1) {
          if (texts[leftIndex]._textOwner === texts[rightIndex]._textOwner) continue;
          if (!reserveCollisionPairInspection()) break textCollisionAudit;
          const collision = overlap(
            texts[leftIndex]._paintRect,
            texts[rightIndex]._paintRect,
            config.collisionTolerancePx,
          );
          if (!collision.collides) continue;
          textTextCoarseCandidateCount += 1;
          const minimumWidth = Math.min(
            texts[leftIndex]._paintRect.width,
            texts[rightIndex]._paintRect.width,
          );
          const minimumHeight = Math.min(
            texts[leftIndex]._paintRect.height,
            texts[rightIndex]._paintRect.height,
          );
          const widthOverlapRatio = minimumWidth > 0 ?
            collision.overlapWidthPx / minimumWidth : 0;
          const heightOverlapRatio = minimumHeight > 0 ?
            collision.overlapHeightPx / minimumHeight : 0;
          const hardCollision =
            widthOverlapRatio > config.textTextMinimumOverlapRatio &&
            heightOverlapRatio > config.textTextMinimumOverlapRatio;
          const candidate = {
            firstTextIndex: leftIndex,
            secondTextIndex: rightIndex,
            firstTextExcerpt: texts[leftIndex].text,
            secondTextExcerpt: texts[rightIndex].text,
            widthOverlapRatio: round(widthOverlapRatio),
            heightOverlapRatio: round(heightOverlapRatio),
            minimumRequiredOverlapRatio: config.textTextMinimumOverlapRatio,
            ...collision,
          };
          if (hardCollision) textTextCollisions.push(candidate);
          else textTextRejectedCoarseCandidates.push(candidate);
        }
      }

      const directPaintGeometryElements = [...svg.querySelectorAll(
        "line, polyline, polygon, path, rect, circle, ellipse, use, image, foreignObject",
      )]
        .filter((element) => {
          if (element.closest("svg") !== svg) return false;
          if (element.closest("defs, marker, clipPath, mask, symbol, pattern")) return false;
          if (!displayed(element)) return false;
          if (!paintElementIsVisible(element)) return false;
          const rect = geometryRect(element);
          return rect && rect.width > 0 && rect.height > 0;
        })
        .map((element, paintGeometryIndex) => {
          const rawRect = geometryRect(element);
          const clipBounds = ancestorClipPaintBounds(element, svg, clipPathBoundsCache);
          const rect = applyAncestorClipBounds(rawRect, clipBounds);
          if (!rect) return null;
          return {
            paintGeometryIndex,
            tag: element.tagName.toLowerCase(),
            selector: selector(element),
            rect,
            paintBoundsOutsideSvg: clippingStatus(
              boundsOutside(rect, svgRect, config.layoutTolerancePx),
            ),
            _fillPolygon: element.tagName.toLowerCase() === "polygon" ?
              polygonScreenPoints(element) : [],
            _rawRect: rawRect,
            _clipBounds: clipBounds,
            _element: element,
          };
        })
        .filter(Boolean);
      const markerAudits = [...svg.querySelectorAll("line, polyline, polygon, path")]
        .filter((element) => element.closest("svg") === svg)
        .filter(displayed)
        .filter((element) => {
          const style = getComputedStyle(element);
          return [style.markerStart, style.markerMid, style.markerEnd]
            .some((value) => value && value !== "none");
        })
        .map((element) => markerPaintInstances(element, svg));
      const markerAuditErrors = markerAudits.flatMap((audit) => audit.errors)
        .map((error) => ({
          geometryTag: "marker",
          geometrySelector: error.hostSelector || selector(svg),
          error: [error.position, error.markerId, error.error].filter(Boolean).join(": "),
          samplingLimit: error.samplingLimit || null,
        }));
      const markerPaintGeometryElements = markerAudits.flatMap((audit) => audit.records)
        .map((geometry, markerPaintItemIndex) => ({
          ...geometry,
          markerPaintItemIndex,
          paintBoundsOutsideSvg: clippingStatus(
            boundsOutside(geometry.rect, svgRect, config.layoutTolerancePx),
          ),
        }));
      const paintGeometryElements = [
        ...directPaintGeometryElements,
        ...markerPaintGeometryElements,
      ].map((geometry, paintGeometryIndex) => ({ ...geometry, paintGeometryIndex }));
      const collisionGeometry = (geometry, collisionKind) => {
        const rawSample = geometry.sample || (geometry._element ?
          sampleGeometryStroke(geometry._element) : null);
        return {
          paintGeometryIndex: geometry.paintGeometryIndex,
          tag: geometry.tag,
          selector: geometry.selector,
          rect: geometry.rect,
          marker: geometry.marker || null,
          collisionKind,
          sample: applyClipBoundsToStrokeSample(rawSample, geometry._clipBounds || []),
          fillSample: geometry.fillSample || null,
          fillPolygon: geometry._fillPolygon || [],
          fillVisible: geometry.fillVisible ??
            (geometry._element ? fillIsVisible(geometry._element) : false),
          fillPaintVisible: geometry.fillPaintVisible ??
            (geometry._element ? fillIsVisible(geometry._element) : false),
          strokeVisible: geometry.strokeVisible ??
            (geometry._element ? strokeIsVisible(geometry._element) : false),
          _clipBounds: geometry._clipBounds || [],
          _element: geometry._element || null,
          _paintElement: geometry._hostElement || geometry._element || null,
        };
      };
      const directStrokeGeometryElements = paintGeometryElements
        .filter((geometry) => ["line", "polyline", "path"].includes(geometry.tag) &&
          strokeIsVisible(geometry._element))
        .map((geometry) => collisionGeometry(geometry, "stroke-text"));
      const polygonGeometryElements = paintGeometryElements
        .filter((geometry) => geometry.tag === "polygon" &&
          (strokeIsVisible(geometry._element) || fillIsVisible(geometry._element)))
        .map((geometry) => collisionGeometry(geometry, "polygon-paint-text"));
      const markerGeometryElements = paintGeometryElements
        .filter((geometry) => geometry.tag.startsWith("marker-") &&
          (geometry.sample || geometry.fillSample))
        .map((geometry) => collisionGeometry(geometry, "marker-paint-text"));
      const geometryElements = [
        ...directStrokeGeometryElements,
        ...polygonGeometryElements,
        ...markerGeometryElements,
      ].map((geometry, geometryIndex) => ({ ...geometry, geometryIndex }));
      const opaqueFillOccluders = directPaintGeometryElements.filter(
        (geometry) => opaqueFillElement(geometry, svg),
      );
      const linePathTextCollisions = [];
      const markerTextCollisions = [];
      const polygonTextCollisions = [];
      const directGeometrySamplingErrors = geometryElements
        .filter((geometry) => geometry.collisionKind === "stroke-text")
        .filter((geometry) => geometry.sample?.error)
        .map((geometry) => ({
          geometryIndex: geometry.geometryIndex,
          geometryTag: geometry.tag,
          geometrySelector: geometry.selector,
          error: geometry.sample.error,
          samplingLimit: geometry.sample.samplingLimit || null,
        }));
      const markerGeometrySamplingErrors = geometryElements
        .filter((geometry) => geometry.collisionKind === "marker-paint-text")
        .flatMap((geometry) => [
          geometry.sample?.error ? {
            geometryIndex: geometry.geometryIndex,
            geometryTag: geometry.tag,
            geometrySelector: geometry.selector,
            samplingKind: "stroke-boundary",
            error: geometry.sample.error,
            samplingLimit: geometry.sample.samplingLimit || null,
          } : null,
          geometry.fillSample?.error ? {
            geometryIndex: geometry.geometryIndex,
            geometryTag: geometry.tag,
            geometrySelector: geometry.selector,
            samplingKind: "filled-paint",
            error: geometry.fillSample.error,
            samplingLimit: geometry.fillSample.samplingLimit || null,
          } : null,
        ].filter(Boolean)).concat(markerAuditErrors);
      const polygonGeometrySamplingErrors = geometryElements
        .filter((geometry) => geometry.collisionKind === "polygon-paint-text")
        .filter((geometry) => geometry.sample?.error)
        .map((geometry) => ({
          geometryIndex: geometry.geometryIndex,
          geometryTag: geometry.tag,
          geometrySelector: geometry.selector,
          error: geometry.sample.error,
          samplingLimit: geometry.sample.samplingLimit || null,
        }));
      let linePathTextCoarseCandidateCount = 0;
      let markerTextCoarseCandidateCount = 0;
      let polygonTextCoarseCandidateCount = 0;
      let paintTextCoarseCandidateCount = 0;
      const samplingErrorBucket = (geometry) => {
        if (geometry.collisionKind === "marker-paint-text") return markerGeometrySamplingErrors;
        if (geometry.collisionKind === "polygon-paint-text") return polygonGeometrySamplingErrors;
        return directGeometrySamplingErrors;
      };
      const recordCollisionAuditError = (
        geometry,
        error,
        samplingLimit = null,
        samplingKind = "collision-audit",
      ) => {
        const bucket = samplingErrorBucket(geometry);
        if (bucket.some((item) => item.error === error)) return;
        bucket.push({
          geometryIndex: geometry.geometryIndex,
          geometryTag: geometry.tag,
          geometrySelector: geometry.selector,
          samplingKind,
          error,
          samplingLimit,
        });
      };
      collisionAudit:
      for (const geometry of geometryElements) {
        if (collisionPairInspectionBudget.exhausted) break;
        const canAuditStroke = geometry.sample &&
          !geometry.sample.error && !geometry.sample.skipped;
        const canAuditMarkerFill = geometry.collisionKind === "marker-paint-text" &&
          geometry.fillSample && !geometry.fillSample.error && !geometry.fillSample.skipped;
        const canAuditPolygonFill = geometry.collisionKind === "polygon-paint-text" &&
          geometry.fillVisible && geometry.fillPolygon.length >= 3;
        if (!canAuditStroke && !canAuditMarkerFill && !canAuditPolygonFill) continue;
        for (const text of texts) {
          if (!reserveCollisionPairInspection()) break collisionAudit;
          const coarseCollision = overlap(
            geometry.rect,
            text._paintRect,
            0,
          );
          if (!coarseCollision.collides) continue;
          paintTextCoarseCandidateCount += 1;
          if (paintTextCoarseCandidateCount > config.collisionMaxCoarseCandidatesPerSvg) {
            recordCollisionAuditError(
              geometry,
              "paint-text coarse candidate limit exceeded: " +
                config.collisionMaxCoarseCandidatesPerSvg,
              {
                code: "collision-coarse-candidate-limit",
                scope: "paint-text coarse candidates per SVG",
                observed: paintTextCoarseCandidateCount,
                limit: config.collisionMaxCoarseCandidatesPerSvg,
                action: "skipped",
              },
              "collision-coarse-candidate-limit",
            );
            break collisionAudit;
          }
          if (geometry.collisionKind === "marker-paint-text") {
            markerTextCoarseCandidateCount += 1;
          } else if (geometry.collisionKind === "polygon-paint-text") {
            polygonTextCoarseCandidateCount += 1;
          } else linePathTextCoarseCandidateCount += 1;
          const occluders = geometry.collisionKind === "stroke-text" && geometry._element ?
            opaqueFillOccluders.filter((occluder) => {
              if (occluder._element === geometry._element) return false;
              if (!overlap(occluder.rect, text._paintRect, 0).collides) return false;
              const geometryToOccluder = geometry._element.compareDocumentPosition(
                occluder._element,
              );
              const occluderToText = occluder._element.compareDocumentPosition(
                text._element,
              );
              return Boolean(geometryToOccluder & Node.DOCUMENT_POSITION_FOLLOWING) &&
                Boolean(occluderToText & Node.DOCUMENT_POSITION_FOLLOWING);
            }) : [];
          const sampledIntersection = canAuditStroke ? strokeTextIntersection(
            geometry.sample,
            text._paintRect,
            text._paintQuad,
            occluders.length ? (point) => occluders.some((occluder) =>
              opaqueGeometryCoversStrokePoint(
                occluder,
                point,
                geometry.sample.strokeHalfWidthScreenPx,
              )) : null,
            text._clipBounds,
          ) : null;
          const fillIntersection = canAuditMarkerFill ?
            filledSampleTextIntersection(
              geometry.fillSample,
              text._paintQuad,
              geometry._clipBounds,
              text._clipBounds,
            ) :
            (canAuditPolygonFill ? polygonFillTextIntersection(geometry, text) : null);
          if (fillIntersection?.error) {
            recordCollisionAuditError(
              geometry,
              "filled-paint sampling failed: " + fillIntersection.error,
              fillIntersection.samplingLimit || null,
              "filled-paint",
            );
            if (activeSampleBudget?.exhausted) break collisionAudit;
          }
          const paintRelation = geometry._paintElement ?
            text._element.compareDocumentPosition(geometry._paintElement) : 0;
          const geometryPaintsAfterText = Boolean(
            paintRelation & Node.DOCUMENT_POSITION_FOLLOWING,
          );
          // A fill-only shape's sampled outline is part of that fill, not an
          // independently visible stroke. Suppress it when the text paints on
          // top, just as the filled-face test does for label backgrounds.
          if (sampledIntersection?.hardCollision && !geometry.strokeVisible &&
              geometry.fillPaintVisible) {
            sampledIntersection.fillOnlyBoundary = true;
            sampledIntersection.geometryPaintsAfterText = geometryPaintsAfterText;
            sampledIntersection.behindTextSuppressed = !geometryPaintsAfterText;
            sampledIntersection.hardCollision = geometryPaintsAfterText;
          }
          if (canAuditMarkerFill && fillIntersection) {
            fillIntersection.markerHostPaintsAfterText = geometryPaintsAfterText;
            fillIntersection.behindTextSuppressed =
              fillIntersection.hardCollision && !geometryPaintsAfterText;
            fillIntersection.hardCollision =
              fillIntersection.hardCollision && geometryPaintsAfterText;
          }
          if (sampledIntersection?.hardCollision || fillIntersection?.hardCollision) {
            const target = geometry.collisionKind === "marker-paint-text" ?
              markerTextCollisions : (geometry.collisionKind === "polygon-paint-text" ?
                polygonTextCollisions : linePathTextCollisions);
            if (target.length >= config.collisionMaxResultsPerKindPerSvg) {
              recordCollisionAuditError(
                geometry,
                geometry.collisionKind + " result limit exceeded: " +
                  config.collisionMaxResultsPerKindPerSvg,
                {
                  code: "collision-result-limit",
                  scope: geometry.collisionKind + " results per SVG",
                  observed: target.length + 1,
                  limit: config.collisionMaxResultsPerKindPerSvg,
                  action: "skipped",
                },
                "collision-result-limit",
              );
              break collisionAudit;
            }
            const collision = {
              geometryIndex: geometry.geometryIndex,
              geometryTag: geometry.tag,
              geometrySelector: geometry.selector,
              collisionKind: geometry.collisionKind,
              marker: geometry.marker,
              textIndex: text.textIndex,
              textExcerpt: text.text,
              coarseBBoxOverlap: coarseCollision,
              collisionModes: [
                sampledIntersection?.hardCollision ? "boundary" : null,
                fillIntersection?.hardCollision ? "filled-paint" : null,
              ].filter(Boolean),
              strokeSampling: sampledIntersection ? {
                sampledPointCount: geometry.sample.sampleCount,
                localLength: round(geometry.sample.localLength),
                estimatedScreenLengthPx: round(geometry.sample.estimatedScreenLengthPx),
                approximateSampleSpacingPx: round(geometry.sample.approximateSampleSpacingPx),
                strokeWidthScreenPx: round(geometry.sample.strokeWidthScreenPx),
                strokeHalfWidthScreenPx: round(geometry.sample.strokeHalfWidthScreenPx),
                dashArray: geometry.sample.dashArray.map(round),
                dashOffset: round(geometry.sample.dashOffset),
                tolerancePx: config.collisionTolerancePx,
                collisionReachPx: round(geometry.sample.collisionReachPx),
                ...sampledIntersection,
              } : null,
              fillSampling: fillIntersection ? {
                sampledPointCount: geometry.fillSample?.sampleCount ?? null,
                filledSamplePointCount: geometry.fillSample?.filledSampleCount ?? null,
                approximateSampleWidthPx:
                  round(geometry.fillSample?.approximateSampleWidthPx),
                approximateSampleHeightPx:
                  round(geometry.fillSample?.approximateSampleHeightPx),
                ...fillIntersection,
              } : null,
            };
            if (geometry.collisionKind === "marker-paint-text") {
              markerTextCollisions.push(collision);
            } else if (geometry.collisionKind === "polygon-paint-text") {
              polygonTextCollisions.push(collision);
            } else linePathTextCollisions.push(collision);
          }
        }
      }

      const cleanTexts = texts.map(
        ({ _rect, _paintRect, _paintQuad, _clipBounds, _textOwner, _element, ...text }) => text,
      );
      const clippedTextPaintItems = cleanTexts
        .filter((text) => text.paintBoundsOutsideSvg.clipped)
        .map((text) => ({
          kind: "text",
          textIndex: text.textIndex,
          tag: text.tag,
          selector: text.selector,
          text: text.text,
          rect: text.rect,
          paintBoundsOutsideSvg: text.paintBoundsOutsideSvg,
        }));
      const svgChildPaintRects = [
        ...texts.map((text) => ({
          kind: "text",
          selector: text.selector,
          rect: text._paintRect,
        })),
        ...paintGeometryElements.map((geometry) => ({
          kind: geometry.tag.startsWith("marker-") ? "marker" : "geometry",
          selector: geometry.selector,
          rect: geometry.rect,
        })),
      ].filter((paint) => svgOverflowX === "visible" &&
        horizontalOutside(paint.rect, svgRect, config.layoutTolerancePx).outside);
      let paintWrapper = svg.parentElement;
      while (paintWrapper && paintWrapper !== root) {
        const tag = paintWrapper.tagName.toLowerCase();
        const clientWidth = Number(paintWrapper.clientWidth) || 0;
        const wrapperStyle = getComputedStyle(paintWrapper);
        const clipsOrScrolls = wrapperStyle.overflowX !== "visible";
        const wrapperRect = paintWrapper.getBoundingClientRect();
        const layoutWidth = Number(paintWrapper.offsetWidth) || clientWidth;
        const scaleX = layoutWidth > 0 ? wrapperRect.width / layoutWidth : 1;
        const innerClientLeft = wrapperRect.left + (Number(paintWrapper.clientLeft) || 0) * scaleX;
        const innerClientWidth = clientWidth * scaleX;
        const innerClientRect = {
          left: innerClientLeft,
          right: innerClientLeft + innerClientWidth,
        };
        const outsidePaint = svgChildPaintRects
          .map((paint, paintIndex) => ({
            paintIndex,
            kind: paint.kind,
            selector: paint.selector,
            rect: rectValue(paint.rect),
            outside: horizontalOutside(
              paint.rect,
              innerClientRect,
              config.layoutTolerancePx,
            ),
          }))
          .filter((paint) => paint.outside.outside);
        if (!tableTags.has(tag) && clientWidth > 0 && clipsOrScrolls && outsidePaint.length) {
          const key = selector(paintWrapper);
          let record = wrapperPaintEscapes.get(key);
          if (!record) {
            record = {
              ...describe(paintWrapper),
              innerClientBox: {
                left: round(innerClientRect.left),
                right: round(innerClientRect.right),
                width: round(innerClientWidth),
              },
              wrapperOverflowX: wrapperStyle.overflowX,
              clipsOrScrolls,
              svgIndexes: [],
            };
            wrapperPaintEscapes.set(key, record);
          }
          if (!record.svgIndexes.includes(svgIndex)) record.svgIndexes.push(svgIndex);
          record.paintOutsideInnerClientBoxCount =
            (record.paintOutsideInnerClientBoxCount || 0) + outsidePaint.length;
          record.paintOutsideInnerClientBoxItems = [
            ...(record.paintOutsideInnerClientBoxItems || []),
            ...outsidePaint.slice(0, 20),
          ].slice(0, 40);
          break;
        }
        paintWrapper = paintWrapper.parentElement;
      }
      const cleanDirectPaintGeometry = directPaintGeometryElements.map(
        ({
          _element,
          _hostElement,
          _fillPolygon,
          _rawRect,
          _clipBounds,
          sample,
          fillSample,
          rect,
          ...geometry
        }) => ({
          ...geometry,
          rect: rectValue(rect),
        }),
      );
      const embeddedPaintTags = new Set(["use", "image", "foreignobject"]);
      const embeddedPaintItems = cleanDirectPaintGeometry.filter(
        (geometry) => embeddedPaintTags.has(geometry.tag),
      );
      const cleanMarkerPaintGeometry = markerPaintGeometryElements.map(
        ({
          _element,
          _hostElement,
          _fillPolygon,
          _clipBounds,
          sample,
          fillSample,
          rect,
          ...geometry
        }) => ({
          ...geometry,
          rect: rectValue(rect),
          fillSampling: fillSample ? {
            error: fillSample.error || null,
            skipped: Boolean(fillSample.skipped),
            skipReason: fillSample.skipReason || "",
            sampleCount: fillSample.sampleCount || 0,
            filledSampleCount: fillSample.filledSampleCount || 0,
            paintHitTestFallbackUsed: Boolean(fillSample.paintHitTestFallbackUsed),
          } : null,
        }),
      );
      const markerInstanceCount = new Set(cleanMarkerPaintGeometry.map((geometry) => [
        geometry.marker?.hostSelector,
        geometry.marker?.id,
        geometry.marker?.position,
        geometry.marker?.placementIndex,
      ].join("\u0000"))).size;
      const clippedGeometryPaintItems = cleanDirectPaintGeometry
        .filter((geometry) => geometry.paintBoundsOutsideSvg.clipped)
        .map((geometry) => ({ kind: "geometry", ...geometry }));
      const clippedMarkerPaintItems = cleanMarkerPaintGeometry
        .filter((geometry) => geometry.paintBoundsOutsideSvg.clipped)
        .map((geometry) => ({ kind: "marker", ...geometry }));
      const internallyClippedMarkerPaintItems = cleanMarkerPaintGeometry
        .filter((geometry) => geometry.markerInternalClipped)
        .map((geometry) => ({ kind: "marker", ...geometry }));
      const clippedPaintItems = [...clippedTextPaintItems, ...clippedGeometryPaintItems];
      const renderedHeights = cleanTexts.map((text) => text.renderedHeightPx)
        .filter((height) => Number.isFinite(height));
      svgResults.push({
        svgIndex,
        collisionPairInspectionBudget: {
          ...collisionPairInspectionBudget,
          remaining: collisionPairInspectionBudget.limit -
            collisionPairInspectionBudget.used,
        },
        collisionAuditErrorCount: collisionAuditErrors.length,
        collisionAuditErrors,
        samplePointBudget: {
          used: activeSampleBudget.used,
          limit: activeSampleBudget.limit,
          remaining: activeSampleBudget.limit - activeSampleBudget.used,
          exhausted: activeSampleBudget.exhausted,
        },
        selector: selector(svg),
        rect: rectValue(svgRect),
        viewBox: svg.getAttribute("viewBox") || "",
        preserveAspectRatio: svg.getAttribute("preserveAspectRatio") || "",
        container: describe(container),
        outsideViewport,
        outsideContainer,
        paintClipping: {
          overflowX: svgOverflowX,
          overflowY: svgOverflowY,
          clipsHorizontal: svgClipsHorizontal,
          clipsVertical: svgClipsVertical,
          paintItemCount: cleanTexts.length + cleanDirectPaintGeometry.length,
          textPaintItemCount: cleanTexts.length,
          geometryPaintItemCount: cleanDirectPaintGeometry.length,
          paintOutsideSvgCount: cleanTexts.filter(
            (text) => text.paintBoundsOutsideSvg.outside,
          ).length + cleanDirectPaintGeometry.filter(
            (geometry) => geometry.paintBoundsOutsideSvg.outside,
          ).length,
          clippedPaintCount: clippedPaintItems.length,
          clippedTextPaintCount: clippedTextPaintItems.length,
          clippedGeometryPaintCount: clippedGeometryPaintItems.length,
          clippedPaintItemsTruncated: clippedPaintItems.length > 80,
          clippedPaintItems: clippedPaintItems.slice(0, 80),
        },
        textMetrics: {
          count: cleanTexts.length,
          auxiliaryCount: cleanTexts.filter((text) => text.role === "auxiliary").length,
          coreCount: cleanTexts.filter((text) => text.role === "core").length,
          minimumRenderedHeightPx: renderedHeights.length ? round(Math.min(...renderedHeights)) : null,
          undersizedCount: cleanTexts.filter((text) => text.tooSmall).length,
          texts: cleanTexts,
        },
        paintGeometryCount: cleanDirectPaintGeometry.length,
        embeddedPaintItemCount: embeddedPaintItems.length,
        clippedEmbeddedPaintItemCount: embeddedPaintItems.filter(
          (geometry) => geometry.paintBoundsOutsideSvg.clipped,
        ).length,
        markerPaintItemCount: cleanMarkerPaintGeometry.length,
        markerInstanceCount,
        clippedMarkerPaintCount: clippedMarkerPaintItems.length,
        clippedMarkerPaintItemsTruncated: clippedMarkerPaintItems.length > 80,
        clippedMarkerPaintItems: clippedMarkerPaintItems.slice(0, 80),
        internallyClippedMarkerPaintCount: internallyClippedMarkerPaintItems.length,
        internallyClippedMarkerPaintItemsTruncated:
          internallyClippedMarkerPaintItems.length > 80,
        internallyClippedMarkerPaintItems: internallyClippedMarkerPaintItems.slice(0, 80),
        geometryCount: directStrokeGeometryElements.length,
        sampledGeometryCount: directStrokeGeometryElements.filter(
          (geometry) => !geometry.sample.error && !geometry.sample.skipped,
        ).length,
        geometrySamplingErrorCount: directGeometrySamplingErrors.length,
        geometrySamplingErrors: directGeometrySamplingErrors,
        markerGeometryCount: markerGeometryElements.length,
        sampledMarkerGeometryCount: markerGeometryElements.filter(
          (geometry) => {
            const sampledStroke = geometry.sample &&
              !geometry.sample.error && !geometry.sample.skipped;
            const sampledFill = geometry.fillSample &&
              !geometry.fillSample.error && !geometry.fillSample.skipped;
            return sampledStroke || sampledFill;
          },
        ).length,
        markerGeometrySamplingErrorCount: markerGeometrySamplingErrors.length,
        markerGeometrySamplingErrors,
        polygonGeometryCount: polygonGeometryElements.length,
        sampledPolygonGeometryCount: polygonGeometryElements.filter(
          (geometry) => !geometry.sample.error && !geometry.sample.skipped,
        ).length,
        polygonGeometrySamplingErrorCount: polygonGeometrySamplingErrors.length,
        polygonGeometrySamplingErrors,
        paintGeometrySamplingErrorCount:
          directGeometrySamplingErrors.length + markerGeometrySamplingErrors.length +
          polygonGeometrySamplingErrors.length,
        textTextCoarseCandidateCount,
        textTextRejectedCoarseCandidateCount:
          textTextCoarseCandidateCount - textTextCollisions.length,
        textTextRejectedCoarseCandidates,
        textTextCollisionCount: textTextCollisions.length,
        textTextCollisions,
        linePathTextCoarseCandidateCount,
        linePathTextRejectedCoarseCandidateCount:
          linePathTextCoarseCandidateCount - linePathTextCollisions.length,
        linePathTextCollisionCount: linePathTextCollisions.length,
        linePathTextCollisions,
        markerTextCoarseCandidateCount,
        markerTextRejectedCoarseCandidateCount:
          markerTextCoarseCandidateCount - markerTextCollisions.length,
        markerTextCollisionCount: markerTextCollisions.length,
        markerTextCollisions,
        polygonTextCoarseCandidateCount,
        polygonTextRejectedCoarseCandidateCount:
          polygonTextCoarseCandidateCount - polygonTextCollisions.length,
        polygonTextCollisionCount: polygonTextCollisions.length,
        polygonTextCollisions,
        paintTextCollisionCount:
          linePathTextCollisions.length + markerTextCollisions.length +
          polygonTextCollisions.length,
      });
    }

    const pageOverflowElements = [...document.body.querySelectorAll("*")]
      .filter((element) => {
        if (!visibleBox(element)) return false;
        const rect = element.getBoundingClientRect();
        return rect.left < -config.layoutTolerancePx ||
          rect.right > root.clientWidth + config.layoutTolerancePx;
      })
      .slice(0, 40)
      .map(describe);
    const documentScrollWidth = Math.max(root.scrollWidth, body?.scrollWidth ?? 0);
    const internalHorizontalScrolls = [...wrapperOverflow.values()];
    const svgPaintEscapingWrappers = [...wrapperPaintEscapes.values()];
    const undersizedSvgTexts = svgResults.flatMap((svg) =>
      svg.textMetrics.texts.filter((text) => text.tooSmall)
        .map((text) => ({ svgIndex: svg.svgIndex, ...text })),
    );

    return {
      url: location.href,
      documentTitle: document.title,
      documentReadyState: document.readyState,
      viewport: {
        width: root.clientWidth,
        height: root.clientHeight,
        devicePixelRatio,
      },
      pageHorizontalOverflow: {
        failed: documentScrollWidth > root.clientWidth + config.layoutTolerancePx,
        documentScrollWidth,
        documentClientWidth: root.clientWidth,
        overflowPx: round(Math.max(0, documentScrollWidth - root.clientWidth)),
        elements: pageOverflowElements,
      },
      svgCount: svgResults.length,
      svgs: svgResults,
      svgOutsideViewportCount: svgResults.filter((svg) => svg.outsideViewport.outside).length,
      svgOutsideContainerCount: svgResults.filter((svg) => svg.outsideContainer.outside).length,
      svgWithClippedPaintCount: svgResults.filter(
        (svg) => svg.paintClipping.clippedPaintCount > 0,
      ).length,
      clippedSvgPaintItemCount: svgResults.reduce(
        (sum, svg) => sum + svg.paintClipping.clippedPaintCount, 0),
      clippedSvgTextPaintCount: svgResults.reduce(
        (sum, svg) => sum + svg.paintClipping.clippedTextPaintCount, 0),
      clippedSvgGeometryPaintCount: svgResults.reduce(
        (sum, svg) => sum + svg.paintClipping.clippedGeometryPaintCount, 0),
      embeddedPaintItemCount: svgResults.reduce(
        (sum, svg) => sum + svg.embeddedPaintItemCount, 0),
      clippedEmbeddedPaintItemCount: svgResults.reduce(
        (sum, svg) => sum + svg.clippedEmbeddedPaintItemCount, 0),
      markerPaintItemCount: svgResults.reduce(
        (sum, svg) => sum + svg.markerPaintItemCount, 0),
      markerInstanceCount: svgResults.reduce(
        (sum, svg) => sum + svg.markerInstanceCount, 0),
      svgWithClippedMarkerPaintCount: svgResults.filter(
        (svg) => svg.clippedMarkerPaintCount > 0,
      ).length,
      clippedMarkerPaintCount: svgResults.reduce(
        (sum, svg) => sum + svg.clippedMarkerPaintCount, 0),
      internallyClippedMarkerPaintCount: svgResults.reduce(
        (sum, svg) => sum + svg.internallyClippedMarkerPaintCount, 0),
      internalHorizontalScrollCount: internalHorizontalScrolls.length,
      internalHorizontalScrolls,
      svgPaintObstructedWrapperCount: svgPaintEscapingWrappers.length,
      svgPaintObstructedWrappers: svgPaintEscapingWrappers,
      // Compatibility aliases retained for schema-v2 report consumers. In
      // schema v3 these count only paint blocked by a clip/scroll ancestor,
      // never harmless overflow-visible paint that remains inside the page.
      svgPaintEscapingWrapperCount: svgPaintEscapingWrappers.length,
      svgPaintEscapingWrappers,
      svgTextThresholdsPx: {
        auxiliary: config.auxiliaryTextMinPx,
        core: config.coreTextMinPx,
      },
      svgTextCount: svgResults.reduce((sum, svg) => sum + svg.textMetrics.count, 0),
      undersizedSvgTextCount: undersizedSvgTexts.length,
      undersizedSvgTexts,
      exhaustedSvgSampleBudgetCount: svgResults.filter(
        (svg) => svg.samplePointBudget.exhausted,
      ).length,
      usedSvgSamplePointCount: svgResults.reduce(
        (sum, svg) => sum + svg.samplePointBudget.used, 0),
      exhaustedSvgCollisionPairBudgetCount: svgResults.filter(
        (svg) => svg.collisionPairInspectionBudget.exhausted,
      ).length,
      collisionPairInspectionCount: svgResults.reduce(
        (sum, svg) => sum + svg.collisionPairInspectionBudget.used, 0),
      collisionAuditErrorCount: svgResults.reduce(
        (sum, svg) => sum + svg.collisionAuditErrorCount, 0),
      textTextCoarseCandidateCount: svgResults.reduce(
        (sum, svg) => sum + svg.textTextCoarseCandidateCount, 0),
      textTextRejectedCoarseCandidateCount: svgResults.reduce(
        (sum, svg) => sum + svg.textTextRejectedCoarseCandidateCount, 0),
      textTextCollisionCount: svgResults.reduce(
        (sum, svg) => sum + svg.textTextCollisionCount, 0),
      geometrySamplingErrorCount: svgResults.reduce(
        (sum, svg) => sum + svg.geometrySamplingErrorCount, 0),
      markerGeometryCount: svgResults.reduce(
        (sum, svg) => sum + svg.markerGeometryCount, 0),
      sampledMarkerGeometryCount: svgResults.reduce(
        (sum, svg) => sum + svg.sampledMarkerGeometryCount, 0),
      markerGeometrySamplingErrorCount: svgResults.reduce(
        (sum, svg) => sum + svg.markerGeometrySamplingErrorCount, 0),
      polygonGeometryCount: svgResults.reduce(
        (sum, svg) => sum + svg.polygonGeometryCount, 0),
      sampledPolygonGeometryCount: svgResults.reduce(
        (sum, svg) => sum + svg.sampledPolygonGeometryCount, 0),
      polygonGeometrySamplingErrorCount: svgResults.reduce(
        (sum, svg) => sum + svg.polygonGeometrySamplingErrorCount, 0),
      paintGeometrySamplingErrorCount: svgResults.reduce(
        (sum, svg) => sum + svg.paintGeometrySamplingErrorCount, 0),
      linePathTextCoarseCandidateCount: svgResults.reduce(
        (sum, svg) => sum + svg.linePathTextCoarseCandidateCount, 0),
      linePathTextRejectedCoarseCandidateCount: svgResults.reduce(
        (sum, svg) => sum + svg.linePathTextRejectedCoarseCandidateCount, 0),
      linePathTextCollisionCount: svgResults.reduce(
        (sum, svg) => sum + svg.linePathTextCollisionCount, 0),
      markerTextCoarseCandidateCount: svgResults.reduce(
        (sum, svg) => sum + svg.markerTextCoarseCandidateCount, 0),
      markerTextRejectedCoarseCandidateCount: svgResults.reduce(
        (sum, svg) => sum + svg.markerTextRejectedCoarseCandidateCount, 0),
      markerTextCollisionCount: svgResults.reduce(
        (sum, svg) => sum + svg.markerTextCollisionCount, 0),
      polygonTextCoarseCandidateCount: svgResults.reduce(
        (sum, svg) => sum + svg.polygonTextCoarseCandidateCount, 0),
      polygonTextRejectedCoarseCandidateCount: svgResults.reduce(
        (sum, svg) => sum + svg.polygonTextRejectedCoarseCandidateCount, 0),
      polygonTextCollisionCount: svgResults.reduce(
        (sum, svg) => sum + svg.polygonTextCollisionCount, 0),
      paintTextCollisionCount: svgResults.reduce(
        (sum, svg) => sum + svg.paintTextCollisionCount, 0),
    };
  })()`;
}


function runtimeErrorsFromEvents(events) {
  const errors = [];
  for (const event of events) {
    if (event.method === "Runtime.exceptionThrown") {
      const details = event.params?.exceptionDetails ?? {};
      errors.push({
        type: "uncaught-exception",
        text: details.exception?.description ?? details.text ?? "uncaught exception",
        url: details.url ?? "",
        lineNumber: details.lineNumber ?? null,
        columnNumber: details.columnNumber ?? null,
      });
    } else if (event.method === "Runtime.consoleAPICalled" &&
               ["error", "assert"].includes(event.params?.type)) {
      const text = (event.params.args ?? []).map((argument) =>
        argument.value !== undefined ? String(argument.value) :
          (argument.description ?? argument.type ?? ""),
      ).join(" ");
      errors.push({ type: `console-${event.params.type}`, text });
    } else if (event.method === "Log.entryAdded" && event.params?.entry?.level === "error") {
      const entry = event.params.entry;
      errors.push({
        type: "browser-log-error",
        source: entry.source ?? "",
        text: entry.text ?? "",
        url: entry.url ?? "",
        lineNumber: entry.lineNumber ?? null,
      });
    }
  }
  return errors;
}


function documentResponseFromEvents(events, expectedUrl) {
  const expected = new URL(expectedUrl);
  expected.hash = "";
  const responses = events.filter((event) => {
    if (event.method !== "Network.responseReceived" || event.params?.type !== "Document") return false;
    try {
      const actual = new URL(event.params.response.url);
      actual.hash = "";
      return actual.href === expected.href;
    } catch {
      return false;
    }
  });
  if (!responses.length) return null;
  const response = responses.at(-1).params.response;
  return {
    status: response.status,
    statusText: response.statusText ?? "",
    mimeType: response.mimeType ?? "",
    fromDiskCache: Boolean(response.fromDiskCache),
    fromServiceWorker: Boolean(response.fromServiceWorker),
  };
}


function failureReasons(metrics, runtimeErrors, documentResponse) {
  const reasons = [];
  if (!documentResponse) reasons.push("missing main-document HTTP response");
  else if (documentResponse.status < 200 || documentResponse.status >= 400) {
    reasons.push(`main document HTTP ${documentResponse.status}`);
  }
  if (metrics.pageHorizontalOverflow.failed) reasons.push("page horizontal overflow");
  if (metrics.svgCount === 0) reasons.push("no visible SVG");
  if (metrics.svgOutsideViewportCount > 0) {
    reasons.push(`${metrics.svgOutsideViewportCount} SVG(s) outside viewport horizontally`);
  }
  if (metrics.svgOutsideContainerCount > 0) {
    reasons.push(`${metrics.svgOutsideContainerCount} SVG(s) outside container horizontally`);
  }
  if (metrics.clippedSvgPaintItemCount > 0) {
    reasons.push(
      `${metrics.clippedSvgPaintItemCount} SVG text/geometry paint item(s) clipped by SVG viewport`,
    );
  }
  if (metrics.clippedMarkerPaintCount > 0) {
    reasons.push(
      `${metrics.clippedMarkerPaintCount} marker paint item(s) clipped by SVG viewport`,
    );
  }
  if (metrics.internalHorizontalScrollCount > 0) {
    reasons.push(`${metrics.internalHorizontalScrollCount} SVG wrapper(s) internally scroll horizontally`);
  }
  const obstructedWrapperCount = metrics.svgPaintObstructedWrapperCount ??
    metrics.svgPaintEscapingWrapperCount ?? 0;
  if (obstructedWrapperCount > 0) {
    reasons.push(
      `${obstructedWrapperCount} SVG paint obstruction(s) at clip/scroll wrapper(s)`,
    );
  }
  if (metrics.internallyClippedMarkerPaintCount > 0) {
    reasons.push(
      `${metrics.internallyClippedMarkerPaintCount} marker paint item(s) clipped by marker viewport`,
    );
  }
  if (metrics.undersizedSvgTextCount > 0) {
    reasons.push(`${metrics.undersizedSvgTextCount} undersized SVG text node(s)`);
  }
  if (metrics.collisionAuditErrorCount > 0) {
    reasons.push(`${metrics.collisionAuditErrorCount} collision audit limit error(s)`);
  }
  if (metrics.textTextCollisionCount > 0) {
    reasons.push(`${metrics.textTextCollisionCount} text-text bbox collision(s)`);
  }
  if (metrics.geometrySamplingErrorCount > 0) {
    reasons.push(`${metrics.geometrySamplingErrorCount} SVG stroke sampling error(s)`);
  }
  if (metrics.markerGeometrySamplingErrorCount > 0) {
    reasons.push(`${metrics.markerGeometrySamplingErrorCount} SVG marker sampling error(s)`);
  }
  if (metrics.polygonGeometrySamplingErrorCount > 0) {
    reasons.push(`${metrics.polygonGeometrySamplingErrorCount} SVG polygon sampling error(s)`);
  }
  if (metrics.linePathTextCollisionCount > 0) {
    reasons.push(`${metrics.linePathTextCollisionCount} sampled stroke-text collision(s)`);
  }
  if (metrics.markerTextCollisionCount > 0) {
    reasons.push(`${metrics.markerTextCollisionCount} sampled marker-text collision(s)`);
  }
  if (metrics.polygonTextCollisionCount > 0) {
    reasons.push(`${metrics.polygonTextCollisionCount} sampled polygon-text collision(s)`);
  }
  if (runtimeErrors.length > 0) reasons.push(`${runtimeErrors.length} runtime error(s)`);
  return reasons;
}


async function createWorker(port, timeoutMs) {
  const response = await fetch(
    `http://127.0.0.1:${port}/json/new?${encodeURIComponent("about:blank")}`,
    { method: "PUT" },
  );
  if (!response.ok) throw new Error(`could not create Chrome target: HTTP ${response.status}`);
  const target = await response.json();
  const cdp = new CDP(target.webSocketDebuggerUrl, timeoutMs);
  await cdp.open();
  await Promise.all([
    cdp.call("Page.enable"),
    cdp.call("Runtime.enable"),
    cdp.call("Log.enable"),
    cdp.call("Network.enable"),
    cdp.call("Emulation.setFocusEmulationEnabled", { enabled: true }),
  ]);
  return { target, cdp };
}


async function auditCase(worker, auditCaseValue, expression, options) {
  const { cdp } = worker;
  const { lesson, viewport } = auditCaseValue;
  const startedAt = new Date().toISOString();
  const started = performance.now();
  try {
    await cdp.call("Emulation.setDeviceMetricsOverride", {
      width: viewport.width,
      height: viewport.height,
      deviceScaleFactor: 1,
      mobile: viewport.mobile,
      screenWidth: viewport.width,
      screenHeight: viewport.height,
    });
    cdp.resetEvents();
    const loaded = cdp.waitEvent("Page.loadEventFired");
    try {
      const navigation = await cdp.call("Page.navigate", { url: lesson.url });
      if (navigation.errorText) throw new Error(`navigation failed: ${navigation.errorText}`);
      await loaded;
    } catch (error) {
      cdp.cancelWaiters("Page.loadEventFired", error);
      await loaded.catch(() => {});
      throw error;
    }
    const settleExpression = `Promise.race([
      document.fonts.ready.then(() => new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() =>
          setTimeout(resolve, ${options.settleMs})
        ))
      )),
      new Promise((_, reject) => setTimeout(() => reject(new Error("font settle timeout")),
        ${Math.max(1_000, options.timeoutMs - 500)}))
    ])`;
    const settled = await cdp.call("Runtime.evaluate", {
      expression: settleExpression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (settled.exceptionDetails) {
      throw new Error(settled.exceptionDetails.exception?.description ?? settled.exceptionDetails.text);
    }
    const evaluation = await cdp.call("Runtime.evaluate", {
      expression,
      returnByValue: true,
    });
    if (evaluation.exceptionDetails) {
      throw new Error(evaluation.exceptionDetails.exception?.description ?? evaluation.exceptionDetails.text);
    }
    const metrics = evaluation.result?.value;
    if (!metrics || typeof metrics !== "object") throw new Error("audit expression returned no value");
    const events = cdp.events.slice();
    const runtimeErrors = runtimeErrorsFromEvents(events);
    const documentResponse = documentResponseFromEvents(events, lesson.url);
    const reasons = failureReasons(metrics, runtimeErrors, documentResponse);
    return {
      courseId: lesson.courseId,
      courseTitle: lesson.courseTitle,
      lessonId: lesson.lessonId,
      lessonTitle: lesson.lessonTitle,
      slug: lesson.slug,
      url: lesson.url,
      viewport,
      startedAt,
      durationMs: Math.round(performance.now() - started),
      status: reasons.length ? "failed" : "passed",
      failureReasons: reasons,
      documentResponse,
      runtimeErrors,
      metrics,
    };
  } catch (error) {
    return {
      courseId: lesson.courseId,
      courseTitle: lesson.courseTitle,
      lessonId: lesson.lessonId,
      lessonTitle: lesson.lessonTitle,
      slug: lesson.slug,
      url: lesson.url,
      viewport,
      startedAt,
      durationMs: Math.round(performance.now() - started),
      status: "failed",
      failureReasons: [`auditor/navigation error: ${error.message}`],
      documentResponse: documentResponseFromEvents(cdp.events, lesson.url),
      runtimeErrors: runtimeErrorsFromEvents(cdp.events),
      metrics: null,
    };
  }
}


async function runPool(workers, cases, expression, options, port) {
  const results = new Array(cases.length);
  let nextIndex = 0;
  async function runWorker(initialWorker, workerIndex) {
    let worker = initialWorker;
    while (true) {
      const index = nextIndex;
      nextIndex += 1;
      if (index >= cases.length) return;
      const item = cases[index];
      const result = await auditCase(worker, item, expression, options);
      results[index] = result;
      const diagnostic = result.failureReasons.length ? result.failureReasons.join("; ") : "ok";
      process.stderr.write(
        `[${index + 1}/${cases.length}] ${result.courseId}:${result.lessonId} ` +
        `${result.viewport.name} ${result.status} (${diagnostic})\n`,
      );
      if (!result.metrics && nextIndex < cases.length) {
        // A timed-out navigation/evaluation can still emit a late load event.
        // Never let that stale page/event satisfy the next case's waiter.
        worker.cdp.close();
        worker = await createWorker(port, options.timeoutMs);
        workers[workerIndex] = worker;
        process.stderr.write(`Replaced Chrome tab ${workerIndex + 1} after auditor error.\n`);
      }
    }
  }
  await Promise.all(workers.map((worker, workerIndex) => runWorker(worker, workerIndex)));
  return results;
}


function numericSum(results, selector) {
  return results.reduce((sum, result) => sum + (selector(result) || 0), 0);
}


function buildReport(options, chromePath, courses, viewports, results, startedAt, durationMs) {
  const failedCases = results.filter((result) => result.status === "failed");
  const auditedLessons = new Set(results.map((result) => `${result.courseId}:${result.lessonId}`));
  return {
    // v3 adds rendered marker fill/embedded-paint auditing, bounded sampling,
    // and narrows wrapper failures to actual clip/scroll obstructions.
    schemaVersion: 3,
    generatedAt: new Date().toISOString(),
    startedAt,
    durationMs,
    baseUrl: options.baseUrl,
    chromePath,
    courseIds: options.courses,
    targets: options.targets.map((target) => target.key),
    concurrency: options.concurrency,
    viewports,
    thresholds: {
      layoutTolerancePx: options.layoutTolerancePx,
      collisionTolerancePx: options.collisionTolerancePx,
      auxiliarySvgTextMinimumRenderedHeightPx: options.auxiliaryTextMinPx,
      coreSvgTextMinimumRenderedHeightPx: options.coreTextMinPx,
      strokeSampleTargetSpacingPx: STROKE_SAMPLE_TARGET_SPACING_PX,
      strokeMaximumSamplePointsPerGeometry: STROKE_MAX_SAMPLE_POINTS,
      strokeMinimumConsecutiveIntersectionPoints: STROKE_MIN_CONSECUTIVE_POINTS,
      strokeMinimumContinuousIntersectionLengthPx: STROKE_MIN_INTERSECTION_LENGTH_PX,
      textTextMinimumOverlapRatioOnBothAxes: TEXT_TEXT_MINIMUM_OVERLAP_RATIO,
      markerMaximumPathDataCharacters: MARKER_MAX_PATH_DATA_CHARACTERS,
      markerMaximumPathTokens: MARKER_MAX_PATH_TOKENS,
      markerMaximumPlacementsPerPosition: MARKER_MAX_PLACEMENTS_PER_POSITION,
      markerMaximumPaintItemsPerPlacement: MARKER_MAX_PAINT_ITEMS_PER_PLACEMENT,
      markerMaximumPaintRecordsPerHost: MARKER_MAX_PAINT_RECORDS_PER_HOST,
      fillSampleTargetSpacingPx: FILL_SAMPLE_TARGET_SPACING_PX,
      fillMaximumSamplePointsPerPaintItem: FILL_MAX_SAMPLE_POINTS,
      fillMinimumIntersectionPoints: FILL_MIN_INTERSECTION_POINTS,
      fillMinimumIntersectionAreaPx: FILL_MIN_INTERSECTION_AREA_PX,
      totalMaximumSamplePointsPerSvg: TOTAL_MAX_SAMPLE_POINTS_PER_SVG,
      collisionMaximumCoarseCandidatesPerSvg:
        COLLISION_MAX_COARSE_CANDIDATES_PER_SVG,
      collisionMaximumPairInspectionsPerSvg:
        COLLISION_MAX_PAIR_INSPECTIONS_PER_SVG,
      collisionMaximumResultsPerKindPerSvg:
        COLLISION_MAX_RESULTS_PER_KIND_PER_SVG,
    },
    discovery: courses.map((course) => ({
      courseId: course.courseId,
      courseTitle: course.courseTitle,
      curriculumUrl: course.curriculumUrl,
      discoveredLessonCount: course.discoveredLessonCount,
      selectedLessonCount: course.selectedLessonCount,
    })),
    summary: {
      status: failedCases.length ? "failed" : "passed",
      courseCount: courses.length,
      auditedLessonCount: auditedLessons.size,
      renderedCaseCount: results.length,
      passedCaseCount: results.length - failedCases.length,
      failedCaseCount: failedCases.length,
      auditorOrNavigationErrorCaseCount: results.filter((result) => !result.metrics).length,
      pageHorizontalOverflowCaseCount: results.filter(
        (result) => result.metrics?.pageHorizontalOverflow?.failed,
      ).length,
      zeroVisibleSvgCaseCount: results.filter((result) => result.metrics?.svgCount === 0).length,
      visibleSvgCount: numericSum(results, (result) => result.metrics?.svgCount),
      svgOutsideViewportCount: numericSum(
        results, (result) => result.metrics?.svgOutsideViewportCount,
      ),
      svgOutsideContainerCount: numericSum(
        results, (result) => result.metrics?.svgOutsideContainerCount,
      ),
      svgWithClippedPaintCount: numericSum(
        results, (result) => result.metrics?.svgWithClippedPaintCount,
      ),
      clippedSvgPaintItemCount: numericSum(
        results, (result) => result.metrics?.clippedSvgPaintItemCount,
      ),
      clippedSvgTextPaintCount: numericSum(
        results, (result) => result.metrics?.clippedSvgTextPaintCount,
      ),
      clippedSvgGeometryPaintCount: numericSum(
        results, (result) => result.metrics?.clippedSvgGeometryPaintCount,
      ),
      embeddedPaintItemCount: numericSum(
        results, (result) => result.metrics?.embeddedPaintItemCount,
      ),
      clippedEmbeddedPaintItemCount: numericSum(
        results, (result) => result.metrics?.clippedEmbeddedPaintItemCount,
      ),
      markerPaintItemCount: numericSum(
        results, (result) => result.metrics?.markerPaintItemCount,
      ),
      markerInstanceCount: numericSum(
        results, (result) => result.metrics?.markerInstanceCount,
      ),
      svgWithClippedMarkerPaintCount: numericSum(
        results, (result) => result.metrics?.svgWithClippedMarkerPaintCount,
      ),
      clippedMarkerPaintCount: numericSum(
        results, (result) => result.metrics?.clippedMarkerPaintCount,
      ),
      internallyClippedMarkerPaintCount: numericSum(
        results, (result) => result.metrics?.internallyClippedMarkerPaintCount,
      ),
      internalHorizontalScrollCount: numericSum(
        results, (result) => result.metrics?.internalHorizontalScrollCount,
      ),
      svgPaintObstructedWrapperCount: numericSum(
        results, (result) => result.metrics?.svgPaintObstructedWrapperCount,
      ),
      svgPaintEscapingWrapperCount: numericSum(
        results, (result) => result.metrics?.svgPaintEscapingWrapperCount,
      ),
      svgTextCount: numericSum(results, (result) => result.metrics?.svgTextCount),
      undersizedSvgTextCount: numericSum(
        results, (result) => result.metrics?.undersizedSvgTextCount,
      ),
      exhaustedSvgSampleBudgetCount: numericSum(
        results, (result) => result.metrics?.exhaustedSvgSampleBudgetCount,
      ),
      usedSvgSamplePointCount: numericSum(
        results, (result) => result.metrics?.usedSvgSamplePointCount,
      ),
      exhaustedSvgCollisionPairBudgetCount: numericSum(
        results, (result) => result.metrics?.exhaustedSvgCollisionPairBudgetCount,
      ),
      collisionPairInspectionCount: numericSum(
        results, (result) => result.metrics?.collisionPairInspectionCount,
      ),
      collisionAuditErrorCount: numericSum(
        results, (result) => result.metrics?.collisionAuditErrorCount,
      ),
      textTextCoarseCandidateCount: numericSum(
        results, (result) => result.metrics?.textTextCoarseCandidateCount,
      ),
      textTextRejectedCoarseCandidateCount: numericSum(
        results, (result) => result.metrics?.textTextRejectedCoarseCandidateCount,
      ),
      textTextCollisionCount: numericSum(
        results, (result) => result.metrics?.textTextCollisionCount,
      ),
      geometrySamplingErrorCount: numericSum(
        results, (result) => result.metrics?.geometrySamplingErrorCount,
      ),
      markerGeometryCount: numericSum(
        results, (result) => result.metrics?.markerGeometryCount,
      ),
      sampledMarkerGeometryCount: numericSum(
        results, (result) => result.metrics?.sampledMarkerGeometryCount,
      ),
      markerGeometrySamplingErrorCount: numericSum(
        results, (result) => result.metrics?.markerGeometrySamplingErrorCount,
      ),
      polygonGeometryCount: numericSum(
        results, (result) => result.metrics?.polygonGeometryCount,
      ),
      sampledPolygonGeometryCount: numericSum(
        results, (result) => result.metrics?.sampledPolygonGeometryCount,
      ),
      polygonGeometrySamplingErrorCount: numericSum(
        results, (result) => result.metrics?.polygonGeometrySamplingErrorCount,
      ),
      paintGeometrySamplingErrorCount: numericSum(
        results, (result) => result.metrics?.paintGeometrySamplingErrorCount,
      ),
      linePathTextCoarseCandidateCount: numericSum(
        results, (result) => result.metrics?.linePathTextCoarseCandidateCount,
      ),
      linePathTextRejectedCoarseCandidateCount: numericSum(
        results, (result) => result.metrics?.linePathTextRejectedCoarseCandidateCount,
      ),
      linePathTextCollisionCount: numericSum(
        results, (result) => result.metrics?.linePathTextCollisionCount,
      ),
      markerTextCoarseCandidateCount: numericSum(
        results, (result) => result.metrics?.markerTextCoarseCandidateCount,
      ),
      markerTextRejectedCoarseCandidateCount: numericSum(
        results, (result) => result.metrics?.markerTextRejectedCoarseCandidateCount,
      ),
      markerTextCollisionCount: numericSum(
        results, (result) => result.metrics?.markerTextCollisionCount,
      ),
      polygonTextCoarseCandidateCount: numericSum(
        results, (result) => result.metrics?.polygonTextCoarseCandidateCount,
      ),
      polygonTextRejectedCoarseCandidateCount: numericSum(
        results, (result) => result.metrics?.polygonTextRejectedCoarseCandidateCount,
      ),
      polygonTextCollisionCount: numericSum(
        results, (result) => result.metrics?.polygonTextCollisionCount,
      ),
      paintTextCollisionCount: numericSum(
        results, (result) => result.metrics?.paintTextCollisionCount,
      ),
      runtimeErrorCount: numericSum(results, (result) => result.runtimeErrors?.length),
    },
    results,
  };
}


function writeReport(output, report) {
  const json = `${JSON.stringify(report, null, 2)}\n`;
  if (output === "-") {
    process.stdout.write(json);
    return;
  }
  const outputPath = path.resolve(output);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  const temporary = `${outputPath}.${process.pid}.tmp`;
  fs.writeFileSync(temporary, json, "utf8");
  fs.renameSync(temporary, outputPath);
  process.stderr.write(`JSON report: ${outputPath}\n`);
}


async function stopChrome(browserCdp, chrome, profileDir) {
  if (browserCdp) {
    try {
      await browserCdp.call("Browser.close");
    } catch {
      // Browser.close commonly closes the socket before returning its response.
    }
    browserCdp.close();
  }
  if (chrome && chrome.exitCode === null) {
    const exited = new Promise((resolve) => chrome.once("exit", resolve));
    const exitedGracefully = await Promise.race([
      exited.then(() => true),
      delay(3_000).then(() => false),
    ]);
    if (!exitedGracefully && chrome.exitCode === null) {
      try {
        chrome.kill();
      } catch (error) {
        process.stderr.write(`Warning: could not terminate Chrome: ${error.message}\n`);
      }
      await Promise.race([exited, delay(3_000)]);
    }
  }
  if (profileDir) {
    const resolvedProfile = path.resolve(profileDir);
    const resolvedTemp = path.resolve(os.tmpdir());
    const safe = path.dirname(resolvedProfile) === resolvedTemp &&
      path.basename(resolvedProfile).startsWith("visual-cc-chrome-");
    if (safe) {
      try {
        fs.rmSync(resolvedProfile, {
          recursive: true,
          force: true,
          maxRetries: 3,
          retryDelay: 100,
        });
      } catch (error) {
        process.stderr.write(
          `Warning: could not remove temporary Chrome profile ${resolvedProfile}: ${error.message}\n`,
        );
      }
    }
  }
}


async function main(argv) {
  let options;
  try {
    options = parseArgs(argv);
  } catch (error) {
    process.stderr.write(`Error: ${error.message}\n\n${HELP}`);
    return 2;
  }
  if (options.help) {
    process.stdout.write(HELP);
    return 0;
  }

  const startedAt = new Date().toISOString();
  const started = performance.now();
  let chrome = null;
  let browserCdp = null;
  let profileDir = null;
  const workers = [];
  try {
    const courses = await discoverCourses(options);
    const lessons = courses.flatMap((course) => course.lessons);
    const viewports = options.desktop ? [...MOBILE_VIEWPORTS, DESKTOP_VIEWPORT] : MOBILE_VIEWPORTS;
    const cases = lessons.flatMap((lesson) => viewports.map((viewport) => ({ lesson, viewport })));
    const chromePath = resolveChromePath(options.chromePath);
    const port = await reservePort();
    profileDir = fs.mkdtempSync(path.join(os.tmpdir(), "visual-cc-chrome-"));
    const chromeArgs = [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profileDir}`,
      "--disable-background-networking",
      "--disable-component-update",
      "--disable-default-apps",
      "--disable-extensions",
      "--disable-sync",
      "--metrics-recording-only",
      "--no-default-browser-check",
      "--no-first-run",
      "--mute-audio",
      "about:blank",
    ];
    if (process.platform !== "win32" && typeof process.getuid === "function" && process.getuid() === 0) {
      chromeArgs.unshift("--no-sandbox");
    }
    chrome = spawn(chromePath, chromeArgs, {
      stdio: ["ignore", "ignore", "pipe"],
      windowsHide: true,
    });
    chrome.spawnError = null;
    chrome.once("error", (error) => {
      chrome.spawnError = error;
    });
    let chromeStderr = "";
    chrome.stderr.setEncoding("utf8");
    chrome.stderr.on("data", (chunk) => {
      chromeStderr = (chromeStderr + chunk).slice(-8_000);
    });
    const version = await waitForDevTools(port, chrome, options.timeoutMs);
    browserCdp = new CDP(version.webSocketDebuggerUrl, options.timeoutMs);
    await browserCdp.open();
    const workerCount = Math.min(options.concurrency, cases.length);
    for (let index = 0; index < workerCount; index += 1) {
      workers.push(await createWorker(port, options.timeoutMs));
    }
    process.stderr.write(
      `Auditing ${lessons.length} lesson(s), ${cases.length} render case(s), ` +
      `${workerCount} Chrome tab(s).\n`,
    );
    const expression = buildAuditExpression(options);
    const results = await runPool(workers, cases, expression, options, port);
    const report = buildReport(
      options,
      chromePath,
      courses,
      viewports,
      results,
      startedAt,
      Math.round(performance.now() - started),
    );
    writeReport(options.output, report);
    process.stderr.write(
      `Audit ${report.summary.status}: ${report.summary.passedCaseCount} passed, ` +
      `${report.summary.failedCaseCount} failed.\n`,
    );
    if (chrome.exitCode !== null && chrome.exitCode !== 0) {
      process.stderr.write(`Chrome stderr tail:\n${chromeStderr}\n`);
    }
    if (report.summary.auditorOrNavigationErrorCaseCount > 0) return 2;
    return report.summary.failedCaseCount ? 1 : 0;
  } catch (error) {
    process.stderr.write(`Fatal audit error: ${error.stack ?? error.message}\n`);
    return 2;
  } finally {
    for (const worker of workers) worker.cdp.close();
    await stopChrome(browserCdp, chrome, profileDir);
  }
}


const isEntrypoint = process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
if (isEntrypoint) {
  process.exitCode = await main(process.argv.slice(2));
}

export {
  MAX_CONCURRENCY,
  buildAuditExpression,
  lessonsFromCurriculum,
  parseArgs,
};
