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
const STROKE_MAX_SAMPLE_POINTS = 2_000;
const STROKE_MIN_CONSECUTIVE_POINTS = 3;
const STROKE_MIN_INTERSECTION_LENGTH_PX = 4;
const TEXT_TEXT_MINIMUM_OVERLAP_RATIO = 0.15;
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
  });
  return String.raw`(() => {
    const config = ${config};
    const root = document.documentElement;
    const body = document.body;
    const round = (value) => Number.isFinite(value) ? Math.round(value * 100) / 100 : null;
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
        const strokeWidthLocalPx = Number.parseFloat(style.strokeWidth) || 1;
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
        const sampleCount = Math.min(
          config.strokeMaxSamplePoints,
          Math.max(
            2,
            Math.ceil(estimatedScreenLengthPx / config.strokeSampleTargetSpacingPx) + 1,
          ),
        );
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
          sampleCount: 0,
          points: [],
        };
      }
    };
    const strokeTextIntersection = (sample, textRect) => {
      const reach = sample.collisionReachPx || 0;
      const collisionZone = {
        left: textRect.left - reach,
        right: textRect.right + reach,
        top: textRect.top - reach,
        bottom: textRect.bottom + reach,
      };
      let insideSampleCount = 0;
      let rawInsideSampleCount = 0;
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
        if (!point.painted) {
          consecutive = 0;
          currentInsideLengthPx = 0;
          previous = point;
          previousInside = false;
          continue;
        }
        const inside = point.x >= collisionZone.left && point.x <= collisionZone.right &&
          point.y >= collisionZone.top && point.y <= collisionZone.bottom;
        const rawInside = point.x >= textRect.left && point.x <= textRect.right &&
          point.y >= textRect.top && point.y <= textRect.bottom;
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
    const tableTags = new Set(["table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "colgroup", "col"]);
    const wrapperOverflow = new Map();
    const viewportRect = { left: 0, right: root.clientWidth };
    const svgResults = [];

    const visibleSvgs = [...document.querySelectorAll("svg")].filter(visibleBox);
    for (const [svgIndex, svg] of visibleSvgs.entries()) {
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
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        const fontSizePx = Number.parseFloat(style.fontSize) || 0;
        const actualRenderedHeightPx = renderedTextHeight(element);
        const role = isAuxiliaryText(element, fontSizePx) ? "auxiliary" : "core";
        const thresholdPx = role === "auxiliary" ?
          config.auxiliaryTextMinPx : config.coreTextMinPx;
        const paintBoundsOutsideSvg = clippingStatus(
          boundsOutside(rect, svgRect, config.layoutTolerancePx),
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
          rect: rectValue(rect),
          paintBoundsOutsideSvg,
          _rect: rect,
          _textOwner: element.closest("text"),
        };
      });

      const textTextCollisions = [];
      const textTextRejectedCoarseCandidates = [];
      let textTextCoarseCandidateCount = 0;
      for (let leftIndex = 0; leftIndex < texts.length; leftIndex += 1) {
        for (let rightIndex = leftIndex + 1; rightIndex < texts.length; rightIndex += 1) {
          if (texts[leftIndex]._textOwner === texts[rightIndex]._textOwner) continue;
          const collision = overlap(
            texts[leftIndex]._rect,
            texts[rightIndex]._rect,
            config.collisionTolerancePx,
          );
          if (!collision.collides) continue;
          textTextCoarseCandidateCount += 1;
          const minimumWidth = Math.min(
            texts[leftIndex]._rect.width,
            texts[rightIndex]._rect.width,
          );
          const minimumHeight = Math.min(
            texts[leftIndex]._rect.height,
            texts[rightIndex]._rect.height,
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

      const paintGeometryElements = [...svg.querySelectorAll(
        "line, polyline, polygon, path, rect, circle, ellipse",
      )]
        .filter((element) => {
          if (element.closest("svg") !== svg) return false;
          if (element.closest("defs, marker, clipPath, mask, symbol, pattern")) return false;
          if (!displayed(element)) return false;
          if (!strokeIsVisible(element) && !fillIsVisible(element)) return false;
          const rect = geometryRect(element);
          return rect && rect.width > 0 && rect.height > 0;
        })
        .map((element, paintGeometryIndex) => {
          const rect = geometryRect(element);
          return {
            paintGeometryIndex,
            tag: element.tagName.toLowerCase(),
            selector: selector(element),
            rect,
            paintBoundsOutsideSvg: clippingStatus(
              boundsOutside(rect, svgRect, config.layoutTolerancePx),
            ),
            _element: element,
          };
        });
      const geometryElements = paintGeometryElements
        .filter((geometry) => ["line", "polyline", "path"].includes(geometry.tag) &&
          strokeIsVisible(geometry._element))
        .map((geometry, geometryIndex) => ({
          geometryIndex,
          paintGeometryIndex: geometry.paintGeometryIndex,
          tag: geometry.tag,
          selector: geometry.selector,
          rect: geometry.rect,
          sample: sampleGeometryStroke(geometry._element),
        }));
      const linePathTextCollisions = [];
      const geometrySamplingErrors = geometryElements
        .filter((geometry) => geometry.sample.error)
        .map((geometry) => ({
          geometryIndex: geometry.geometryIndex,
          geometryTag: geometry.tag,
          geometrySelector: geometry.selector,
          error: geometry.sample.error,
        }));
      let linePathTextCoarseCandidateCount = 0;
      for (const geometry of geometryElements) {
        if (geometry.sample.error || geometry.sample.skipped) continue;
        for (const text of texts) {
          const coarseCollision = overlap(
            geometry.rect,
            text._rect,
            0,
          );
          if (!coarseCollision.collides) continue;
          linePathTextCoarseCandidateCount += 1;
          const sampledIntersection = strokeTextIntersection(geometry.sample, text._rect);
          if (sampledIntersection.hardCollision) {
            linePathTextCollisions.push({
              geometryIndex: geometry.geometryIndex,
              geometryTag: geometry.tag,
              geometrySelector: geometry.selector,
              textIndex: text.textIndex,
              textExcerpt: text.text,
              coarseBBoxOverlap: coarseCollision,
              strokeSampling: {
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
              },
            });
          }
        }
      }

      const cleanTexts = texts.map(({ _rect, _textOwner, ...text }) => text);
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
      const cleanPaintGeometry = paintGeometryElements.map(({ _element, rect, ...geometry }) => ({
        ...geometry,
        rect: rectValue(rect),
      }));
      const clippedGeometryPaintItems = cleanPaintGeometry
        .filter((geometry) => geometry.paintBoundsOutsideSvg.clipped)
        .map((geometry) => ({ kind: "geometry", ...geometry }));
      const clippedPaintItems = [...clippedTextPaintItems, ...clippedGeometryPaintItems];
      const renderedHeights = cleanTexts.map((text) => text.renderedHeightPx)
        .filter((height) => Number.isFinite(height));
      svgResults.push({
        svgIndex,
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
          paintItemCount: cleanTexts.length + cleanPaintGeometry.length,
          textPaintItemCount: cleanTexts.length,
          geometryPaintItemCount: cleanPaintGeometry.length,
          paintOutsideSvgCount: cleanTexts.filter(
            (text) => text.paintBoundsOutsideSvg.outside,
          ).length + cleanPaintGeometry.filter(
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
        paintGeometryCount: cleanPaintGeometry.length,
        geometryCount: geometryElements.length,
        sampledGeometryCount: geometryElements.filter(
          (geometry) => !geometry.sample.error && !geometry.sample.skipped,
        ).length,
        geometrySamplingErrorCount: geometrySamplingErrors.length,
        geometrySamplingErrors,
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
      internalHorizontalScrollCount: internalHorizontalScrolls.length,
      internalHorizontalScrolls,
      svgTextThresholdsPx: {
        auxiliary: config.auxiliaryTextMinPx,
        core: config.coreTextMinPx,
      },
      svgTextCount: svgResults.reduce((sum, svg) => sum + svg.textMetrics.count, 0),
      undersizedSvgTextCount: undersizedSvgTexts.length,
      undersizedSvgTexts,
      textTextCoarseCandidateCount: svgResults.reduce(
        (sum, svg) => sum + svg.textTextCoarseCandidateCount, 0),
      textTextRejectedCoarseCandidateCount: svgResults.reduce(
        (sum, svg) => sum + svg.textTextRejectedCoarseCandidateCount, 0),
      textTextCollisionCount: svgResults.reduce(
        (sum, svg) => sum + svg.textTextCollisionCount, 0),
      geometrySamplingErrorCount: svgResults.reduce(
        (sum, svg) => sum + svg.geometrySamplingErrorCount, 0),
      linePathTextCoarseCandidateCount: svgResults.reduce(
        (sum, svg) => sum + svg.linePathTextCoarseCandidateCount, 0),
      linePathTextRejectedCoarseCandidateCount: svgResults.reduce(
        (sum, svg) => sum + svg.linePathTextRejectedCoarseCandidateCount, 0),
      linePathTextCollisionCount: svgResults.reduce(
        (sum, svg) => sum + svg.linePathTextCollisionCount, 0),
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
  if (metrics.internalHorizontalScrollCount > 0) {
    reasons.push(`${metrics.internalHorizontalScrollCount} SVG wrapper(s) internally scroll horizontally`);
  }
  if (metrics.undersizedSvgTextCount > 0) {
    reasons.push(`${metrics.undersizedSvgTextCount} undersized SVG text node(s)`);
  }
  if (metrics.textTextCollisionCount > 0) {
    reasons.push(`${metrics.textTextCollisionCount} text-text bbox collision(s)`);
  }
  if (metrics.geometrySamplingErrorCount > 0) {
    reasons.push(`${metrics.geometrySamplingErrorCount} SVG stroke sampling error(s)`);
  }
  if (metrics.linePathTextCollisionCount > 0) {
    reasons.push(`${metrics.linePathTextCollisionCount} sampled stroke-text collision(s)`);
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
    schemaVersion: 2,
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
      internalHorizontalScrollCount: numericSum(
        results, (result) => result.metrics?.internalHorizontalScrollCount,
      ),
      svgTextCount: numericSum(results, (result) => result.metrics?.svgTextCount),
      undersizedSvgTextCount: numericSum(
        results, (result) => result.metrics?.undersizedSvgTextCount,
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
      linePathTextCoarseCandidateCount: numericSum(
        results, (result) => result.metrics?.linePathTextCoarseCandidateCount,
      ),
      linePathTextRejectedCoarseCandidateCount: numericSum(
        results, (result) => result.metrics?.linePathTextRejectedCoarseCandidateCount,
      ),
      linePathTextCollisionCount: numericSum(
        results, (result) => result.metrics?.linePathTextCollisionCount,
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
