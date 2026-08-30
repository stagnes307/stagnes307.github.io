(function () {
  "use strict";

  var ANSWER_LABELS = {
    official_verified: "공식 확인",
    expert_reviewed: "전문가 검토",
    multi_source_corroborated: "복수 출처 일치",
    conflicting: "정답 충돌",
    unverified: "미확인"
  };
  var CONTENT_LABELS = {
    full: "원문 수록",
    public_fulltext: "원문 공개",
    private_only: "로컬 전용",
    link_only: "출처 링크",
    blocked: "수집 제외"
  };
  var EVIDENCE_LABELS = {
    sufficient: "근거 충분",
    provisional: "잠정",
    insufficient: "근거 부족",
    conflicting: "검토 필요"
  };
  var TAB_NAMES = ["analysis", "search", "practice", "weak", "generated"];
  var STORAGE_PREFIX = "study.question-bank.progress.v1:";
  var MAX_STORED_ATTEMPTS = 2500;
  var FETCH_TIMEOUT_MS = 10000;
  var SEARCH_DEBOUNCE_MS = 180;
  var PUBLIC_DATA_PATH = "./data/questions.public.json";
  var GENERATED_DATA_PATH = "./data/questions.generated.public.json";

  var state = {
    data: null,
    topics: [],
    questions: [],
    topicByCode: new Map(),
    questionByStorageId: new Map(),
    questionHashes: new Map(),
    datasetHash: "",
    loadedScope: "public",
    requestedLocal: false,
    searchLimit: 50,
    practiceQueue: [],
    practiceIndex: 0,
    progress: null,
    storageKey: "",
    storageAvailable: true,
    searchIndex: new Map(),
    lessonByTopic: new Map(),
    showAllTopics: false,
    importanceAvailable: false,
    practiceAvailable: false,
    generatedData: null,
    generatedQuestions: [],
    generatedState: "loading",
    activeTab: "analysis",
    focusPracticeAfterRender: false,
    applyingUrlState: false,
    searchTimer: null,
    integrityVerified: false,
    integrityAvailable: false,
    retryRequested: false,
    analysisEvidenceOnly: false
  };

  var elementIds = [
    "qb-main", "appStatus", "datasetScope", "datasetVersion", "datasetGenerated",
    "analysisSummary", "analysisNotice", "analysisSection", "analysisSort",
    "coverageHeadline", "coverageRows", "methodologyBody", "toggleAllTopics",
    "topicAnalysis", "searchForm", "searchQuery", "roundFilter", "sectionFilter",
    "topicFilter", "sourceFilter", "answerFilter", "contentFilter", "searchResultCount", "questionResults",
    "practiceTopic", "shufflePractice", "practiceProgress", "practiceCard", "practiceControls",
    "weakSummary", "progressDatasetNote", "resetProgress", "weakTopics", "weakActions",
    "analysis-tab", "search-tab", "practice-tab", "weak-tab", "generated-tab",
    "generatedStatus", "generatedResults", "copyViewLink", "shareStatus"
  ];
  var dom = {};
  elementIds.forEach(function (id) {
    dom[id] = document.getElementById(id);
  });

  function make(tag, className, textValue) {
    var element = document.createElement(tag);
    if (className) {
      element.className = className;
    }
    if (textValue !== undefined && textValue !== null) {
      element.textContent = String(textValue);
    }
    return element;
  }

  function setEmpty(container, message) {
    container.replaceChildren(make("p", "qb-empty", message));
  }

  function courseUrl() {
    var courseId = courseIdFromPath();
    return courseId ? "/study/courses/" + encodeURIComponent(courseId) + "/" : "/study/";
  }

  function setActionEmpty(container, title, message, href, actionLabel) {
    var stateCard = make("div", "qb-empty-state");
    stateCard.append(make("h3", "", title));
    stateCard.append(make("p", "", message));
    if (href && actionLabel) {
      var action = make("a", "qb-button", actionLabel);
      action.href = href;
      stateCard.append(action);
    }
    container.replaceChildren(stateCard);
  }

  function safeId(value) {
    return asText(value, "item").replace(/[^a-zA-Z0-9_-]/g, "-");
  }

  function prefersReducedMotion() {
    return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function asText(value, fallback) {
    if (typeof value === "string" || typeof value === "number") {
      var text = String(value).trim();
      return text || (fallback || "");
    }
    return fallback || "";
  }

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function numberOrNull(value) {
    if (value === "" || value === null || value === undefined) {
      return null;
    }
    var number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function numberOr(value, fallback) {
    var number = numberOrNull(value);
    return number === null ? fallback : number;
  }

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function formatNumber(value) {
    var number = numberOrNull(value);
    return number === null ? "0" : new Intl.NumberFormat("ko-KR").format(number);
  }

  function formatPercent(value) {
    var number = numberOrNull(value);
    return number === null ? "-" : Math.round(number) + "%";
  }

  function formatDate(value) {
    var text = asText(value, "");
    if (!text) {
      return "-";
    }
    var match = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
    return match ? match[1] + "." + match[2] + "." + match[3] : text;
  }

  function compareCodes(left, right) {
    return String(left).localeCompare(String(right), "ko", {
      numeric: true,
      sensitivity: "base"
    });
  }

  function hashString(input) {
    var hash = 2166136261;
    var text = String(input);
    for (var index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return ("00000000" + (hash >>> 0).toString(16)).slice(-8);
  }

  function choiceText(choice) {
    if (typeof choice === "string" || typeof choice === "number") {
      return String(choice);
    }
    if (!choice || typeof choice !== "object") {
      return "";
    }
    return asText(
      choice.text !== undefined ? choice.text :
        choice.content !== undefined ? choice.content :
          choice.label !== undefined ? choice.label : choice.value,
      ""
    );
  }

  function choiceToken(choice, index) {
    if (choice && typeof choice === "object") {
      var candidate = choice.key !== undefined ? choice.key :
        choice.id !== undefined ? choice.id :
          choice.number !== undefined ? choice.number :
            choice.value !== undefined ? choice.value : choice.label;
      if (typeof candidate === "string" || typeof candidate === "number") {
        return String(candidate).trim();
      }
    }
    return String(index + 1);
  }

  function storageQuestionId(question) {
    return asText(question.appearance_id, "") || asText(question.question_id, "");
  }

  function questionHash(question) {
    var content = {
      question_id: asText(question.question_id, ""),
      appearance_id: asText(question.appearance_id, ""),
      question_text: asText(question.question_text, ""),
      choices: asArray(question.choices).map(choiceText),
      accepted_answer: question.accepted_answer,
      answer_status: asText(question.answer_status, ""),
      primary_topic_code: asText(question.primary_topic_code, "")
    };
    return hashString(JSON.stringify(content));
  }

  function normalEvidence(value) {
    var key = asText(value, "").toLowerCase();
    if (key === "sufficient" || key === "enough" || key === "high") {
      return "sufficient";
    }
    if (key === "provisional" || key === "tentative" || key === "medium") {
      return "provisional";
    }
    if (key === "conflicting" || key === "conflict") {
      return "conflicting";
    }
    return "insufficient";
  }

  function filterMetadataLabel(type, value) {
    var filters = state.data && state.data.filters;
    if (!filters || typeof filters !== "object") {
      return "";
    }
    var aliases = {
      round: ["rounds", "exam_rounds"],
      answer: ["answer_statuses", "answers"],
      content: ["content_modes", "contents"]
    };
    var names = aliases[type] || [];
    for (var index = 0; index < names.length; index += 1) {
      var source = filters[names[index]];
      if (Array.isArray(source)) {
        var item = source.find(function (entry) {
          if (entry && typeof entry === "object") {
            var entryValue = entry.value !== undefined ? entry.value :
              entry.id !== undefined ? entry.id : entry.exam_round;
            return String(entryValue) === String(value);
          }
          return String(entry) === String(value);
        });
        if (item && typeof item === "object") {
          return asText(item.label !== undefined ? item.label : item.title, "");
        }
      } else if (source && typeof source === "object" && source[value] !== undefined) {
        return asText(source[value], "");
      }
    }
    return "";
  }

  function answerLabel(value) {
    var key = asText(value, "unverified");
    return filterMetadataLabel("answer", key) || ANSWER_LABELS[key] || key;
  }

  function contentLabel(value) {
    var key = asText(value, "link_only");
    return filterMetadataLabel("content", key) || CONTENT_LABELS[key] || key;
  }

  function questionContentLabel(question) {
    var mode = asText(question.content_mode, "link_only");
    var rights = asText(question.rights_status, "");
    if (mode === "full" && rights === "public_fulltext") {
      return "원문 공개";
    }
    if (mode === "full" && rights === "private_only") {
      return "로컬 원문";
    }
    return contentLabel(mode);
  }

  function answerBadgeKind(value) {
    if (value === "official_verified" || value === "expert_reviewed" || value === "multi_source_corroborated") {
      return "verified";
    }
    if (value === "conflicting") {
      return "conflict";
    }
    return "review";
  }

  function topicFor(code) {
    return state.topicByCode.get(String(code)) || null;
  }

  function topicTitle(code) {
    var topic = topicFor(code);
    return topic ? asText(topic.title, String(code)) : asText(code, "미분류");
  }

  function questionTopicCodes(question) {
    var codes = asArray(question.topic_codes).map(function (code) {
      return asText(code, "");
    }).filter(Boolean);
    var primary = asText(question.primary_topic_code, "");
    if (primary && codes.indexOf(primary) === -1) {
      codes.unshift(primary);
    }
    return codes;
  }

  function roundValue(question) {
    return asText(question.exam_round, "") || asText(question.exam_year, "");
  }

  function roundLabel(question) {
    var round = asText(question.exam_round, "");
    var year = asText(question.exam_year, "");
    if (/^\d+$/.test(round)) {
      return (year ? year + "년 " : "") + "제" + round + "회";
    }
    if (round && year && round.indexOf(year) === -1) {
      return year + "년 · " + round;
    }
    return round || year || "회차 미상";
  }

  function option(select, value, label) {
    var item = document.createElement("option");
    item.value = String(value);
    item.textContent = String(label);
    return item;
  }

  function setOptions(select, firstLabel, entries) {
    var currentValue = select.value;
    var nodes = [option(select, "", firstLabel)];
    entries.forEach(function (entry) {
      nodes.push(option(select, entry.value, entry.label));
    });
    select.replaceChildren.apply(select, nodes);
    if (entries.some(function (entry) { return String(entry.value) === currentValue; })) {
      select.value = currentValue;
    }
  }

  function setStatus(type, message, withRetry) {
    dom["qb-main"].setAttribute("aria-busy", type === "loading" ? "true" : "false");
    dom.appStatus.hidden = false;
    dom.appStatus.setAttribute("role", type === "error" ? "alert" : "status");
    dom.appStatus.className = "qb-status" +
      (type === "warning" ? " qb-status-warning" : "") +
      (type === "error" ? " qb-status-error" : "");
    var nodes = [];
    if (type === "loading") {
      var spinner = make("span", "qb-spinner");
      spinner.setAttribute("aria-hidden", "true");
      nodes.push(spinner);
    }
    nodes.push(make("span", "", message));
    if (withRetry) {
      var retry = make("button", "qb-button qb-button-secondary qb-retry", "다시 시도");
      retry.type = "button";
      retry.addEventListener("click", function () {
        state.retryRequested = true;
        loadDataset();
      });
      nodes.push(retry);
    }
    dom.appStatus.replaceChildren.apply(dom.appStatus, nodes);
    if (type === "error" && state.retryRequested) {
      window.requestAnimationFrame(function () {
        var retry = dom.appStatus.querySelector(".qb-retry");
        if (retry) {
          retry.focus();
        }
      });
    }
  }

  function hideStatus() {
    dom["qb-main"].setAttribute("aria-busy", "false");
    dom.appStatus.hidden = true;
    dom.appStatus.replaceChildren();
  }

  function courseIdFromPath() {
    var match = window.location.pathname.match(/\/study\/courses\/([^/]+)\/questions\/?/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function stableStringify(value) {
    if (value === null || typeof value !== "object") {
      return JSON.stringify(value);
    }
    if (Array.isArray(value)) {
      return "[" + value.map(stableStringify).join(",") + "]";
    }
    return "{" + Object.keys(value).sort().map(function (key) {
      return JSON.stringify(key) + ":" + stableStringify(value[key]);
    }).join(",") + "}";
  }

  function byteHex(buffer) {
    return Array.from(new Uint8Array(buffer)).map(function (value) {
      return value.toString(16).padStart(2, "0");
    }).join("");
  }

  async function verifyDatasetIntegrity(data) {
    if (!window.crypto || !window.crypto.subtle || typeof window.TextEncoder !== "function") {
      return { available: false, verified: false };
    }
    if (data.dataset_hash_version !== "sha256-sorted-json-v1") {
      throw new Error("지원하지 않는 데이터 무결성 규칙입니다.");
    }
    var expected = asText(data.dataset_version, "").toLowerCase();
    var payload = {};
    Object.keys(data).forEach(function (key) {
      if (key !== "dataset_version" && key !== "generated_at") {
        payload[key] = data[key];
      }
    });
    var encoded = new TextEncoder().encode(stableStringify(payload));
    var actual = byteHex(await window.crypto.subtle.digest("SHA-256", encoded));
    if (actual !== expected) {
      throw new Error("데이터 무결성 검증에 실패했습니다.");
    }
    return { available: true, verified: true };
  }

  function validateDataset(data, options) {
    options = options || {};
    if (!data || typeof data !== "object") {
      throw new Error("데이터셋이 JSON 객체가 아닙니다.");
    }
    if (!Number.isInteger(data.schema_version) || data.schema_version < 1) {
      throw new Error("지원하지 않는 schema_version입니다.");
    }
    if (!Array.isArray(data.questions) || (!options.generated && !Array.isArray(data.topics))) {
      throw new Error("필수 데이터 배열이 없습니다.");
    }
    if (options.generated && (!data.summary || typeof data.summary !== "object" || data.target_curriculum === undefined)) {
      throw new Error("생성문제 공개 스키마가 올바르지 않습니다.");
    }
    if (!options.generated && (!data.summary || typeof data.summary !== "object" || !Array.isArray(data.coverage) ||
        !data.filters || typeof data.filters !== "object")) {
      throw new Error("공개 기출 근거 스키마가 올바르지 않습니다.");
    }
    if (!/^[0-9a-f]{64}$/.test(asText(data.dataset_version, ""))) {
      throw new Error("dataset_version이 올바른 SHA-256 값이 아닙니다.");
    }
    if (data.dataset_hash_version !== "sha256-sorted-json-v1") {
      throw new Error("dataset_hash_version이 없거나 지원되지 않습니다.");
    }
    if (!data.privacy || data.privacy.scope !== "public" || data.privacy.contains_private_content !== false) {
      throw new Error("공개 범위가 아닌 데이터는 브라우저에서 열 수 없습니다.");
    }
    if (!asText(data.generated_at, "") || Number.isNaN(Date.parse(data.generated_at))) {
      throw new Error("데이터 생성 시각이 올바르지 않습니다.");
    }
    var expectedCourse = courseIdFromPath();
    if (expectedCourse && asText(data.course_id, "") !== expectedCourse) {
      throw new Error("과정과 데이터셋 식별자가 일치하지 않습니다.");
    }
    var recordIds = new Set();
    var topicCodes = new Set();
    if (!options.generated) {
      data.topics.forEach(function (topic) {
        var code = topic && typeof topic === "object" ? asText(topic.code, "") : "";
        if (!code || topicCodes.has(code) || !asText(topic.title, "")) {
          throw new Error("중복되거나 올바르지 않은 토픽이 포함되어 있습니다.");
        }
        topicCodes.add(code);
      });
    }
    data.questions.forEach(function (question) {
      if (!question || typeof question !== "object") {
        throw new Error("올바르지 않은 관측 기록이 포함되어 있습니다.");
      }
      if (options.generated) {
        var generatedId = asText(question.question_id, "");
        if (asText(question.origin_type, "") !== "generated" || asText(question.review_status, "") !== "approved") {
          throw new Error("생성문제 파일에는 검토 승인된 생성 레코드만 포함할 수 있습니다.");
        }
        if (!generatedId || recordIds.has(generatedId) || !asText(question.question_text, "") ||
            !Array.isArray(question.choices) || question.choices.length < 2 || !Number.isInteger(question.answer) ||
            !Array.isArray(question.topic_codes) || !question.topic_codes.length || !asText(question.content_hash, "") ||
            !asText(question.content_hash_version, "")) {
          throw new Error("생성문제 필수 필드가 올바르지 않습니다.");
        }
        recordIds.add(generatedId);
        return;
      }
      var recordId = storageQuestionId(question);
      var contentMode = asText(question.content_mode, "");
      var rights = asText(question.rights_status, "");
      if (!recordId || recordIds.has(recordId) || !topicCodes.has(asText(question.primary_topic_code, "")) ||
          !Array.isArray(question.topic_codes) || !question.topic_codes.length ||
          (contentMode !== "link_only" && contentMode !== "full" && contentMode !== "public_fulltext")) {
        throw new Error("관측 기록 식별자 또는 토픽 연결이 올바르지 않습니다.");
      }
      recordIds.add(recordId);
      if (rights !== "public_fulltext" && rights !== "link_only") {
        throw new Error("공개가 허용되지 않은 콘텐츠가 포함되어 있습니다.");
      }
      if (rights !== "public_fulltext" && asText(question.question_text, "")) {
        throw new Error("공개 권한이 없는 원문이 포함되어 있습니다.");
      }
      if (rights === "link_only" && (!asText(question.concept_summary, "") || !Array.isArray(question.source_links) || !question.source_links.length)) {
        throw new Error("링크 전용 관측 기록에 개념 요약 또는 출처가 없습니다.");
      }
      asArray(question.source_links).forEach(function (source) {
        if (source && typeof source === "object" && asText(source.rights_status, "link_only") === "private_only") {
          throw new Error("비공개 출처 메타데이터가 포함되어 있습니다.");
        }
      });
    });
    if (options.generated && numberOr(data.summary.published_questions, -1) !== data.questions.length) {
      throw new Error("생성문제 공개 건수와 실제 레코드 수가 일치하지 않습니다.");
    }
    return data;
  }

  async function fetchDataset(path, options) {
    options = options || {};
    var controller = typeof AbortController === "function" ? new AbortController() : null;
    var timer = controller ? window.setTimeout(function () { controller.abort(); }, FETCH_TIMEOUT_MS) : null;
    var response;
    try {
      response = await fetch(path, {
        cache: "no-cache",
        credentials: "same-origin",
        signal: controller ? controller.signal : undefined
      });
    } catch (error) {
      if (error && error.name === "AbortError") {
        throw new Error("데이터 요청 시간이 초과되었습니다.");
      }
      throw error;
    } finally {
      if (timer) {
        window.clearTimeout(timer);
      }
    }
    if (options.optional && response.status === 404) {
      return null;
    }
    if (!response.ok) {
      throw new Error(path + " (" + response.status + ")");
    }
    var data;
    try {
      data = JSON.parse(await response.text());
    } catch (error) {
      throw new Error("JSON 형식을 읽을 수 없습니다.");
    }
    validateDataset(data, options);
    var integrity = await verifyDatasetIntegrity(data);
    if (options.primary) {
      state.integrityAvailable = integrity.available;
      state.integrityVerified = integrity.verified;
    }
    return data;
  }

  async function loadDataset() {
    setStatus("loading", "기출 데이터를 불러오는 중입니다.", false);
    state.requestedLocal = new URLSearchParams(window.location.search).get("scope") === "local";
    try {
      var data = await fetchDataset(PUBLIC_DATA_PATH, { primary: true });
      var recoveredFromFailure = state.retryRequested;
      state.loadedScope = "public";
      prepareDataset(data);
      setSearchFormDisabled(false);
      populateFilters();
      loadProgress();
      applyStateFromUrl(false);
      renderAll();
      applyCapabilityNavigation();
      var notices = [];
      if (state.requestedLocal) {
        notices.push("보안을 위해 브라우저에서는 로컬 비공개 데이터를 열지 않고 공개 데이터만 표시합니다.");
      }
      if (!state.integrityAvailable) {
        notices.push("이 브라우저에서는 데이터 무결성 검증을 사용할 수 없어 구조와 공개 범위만 확인했습니다.");
      }
      if (notices.length) {
        setStatus("warning", notices.join(" "), false);
      } else {
        hideStatus();
      }
      state.retryRequested = false;
      if (recoveredFromFailure) {
        restoreFocusAfterRetry();
      }
      loadGeneratedDataset();
      loadLessonMap();
    } catch (error) {
      console.error(error);
      renderFatalState();
      setStatus("error", "공개 기출 근거를 안전하게 확인하지 못했습니다. 연결 상태를 확인한 뒤 다시 시도해 주세요.", true);
    }
  }

  function prepareDataset(data) {
    state.data = data;
    state.topics = data.topics.filter(function (topic) {
      return topic && typeof topic === "object" && asText(topic.code, "");
    });
    state.questions = data.questions.filter(function (question) {
      return question && typeof question === "object";
    });
    state.topicByCode = new Map();
    state.topics.forEach(function (topic) {
      state.topicByCode.set(String(topic.code), topic);
    });
    state.questionByStorageId = new Map();
    state.questionHashes = new Map();
    state.searchIndex = new Map();
    state.questions.forEach(function (question) {
      var id = storageQuestionId(question);
      if (id) {
        state.questionByStorageId.set(id, question);
        state.questionHashes.set(id, questionHash(question));
        state.searchIndex.set(id, searchableText(question));
      }
    });
    var hashParts = Array.from(state.questionHashes.entries()).sort(function (left, right) {
      return compareCodes(left[0], right[0]);
    }).map(function (entry) {
      return entry[0] + ":" + entry[1];
    });
    state.datasetHash = hashString([
      asText(data.course_id, "question-bank"),
      asText(data.dataset_version, ""),
      hashParts.join("|")
    ].join("::"));
    var version = asText(data.dataset_version, "-");
    dom.datasetScope.textContent = "공개 데이터";
    dom.datasetVersion.textContent = version === "-" ? version : version.slice(0, 12) + "… · " +
      (state.integrityVerified ? "무결성 확인" : "구조 확인");
    dom.datasetVersion.title = version;
    dom.datasetGenerated.textContent = formatDate(data.generated_at);
    var summary = data.summary && typeof data.summary === "object" ? data.summary : {};
    state.importanceAvailable = numberOr(summary.eligible_rounds, 0) > 0 && state.topics.some(function (topic) {
      return numberOrNull(topic.importance_score) !== null;
    });
    state.practiceAvailable = getEligibleQuestions().length > 0;
  }

  function setFilterAvailability(select, entries) {
    var wrapper = select.closest("label");
    var useful = entries.length >= 2;
    if (wrapper) {
      wrapper.hidden = !useful;
    }
    select.disabled = !useful;
    if (!useful) {
      select.value = "";
    }
  }

  function populateFilters() {
    var sections = new Map();
    state.topics.forEach(function (topic) {
      var id = asText(topic.section_id, "");
      if (id && !sections.has(id)) {
        sections.set(id, asText(topic.section_title, id));
      }
    });
    var sectionEntries = Array.from(sections.entries()).map(function (entry) {
      return { value: entry[0], label: entry[0] + ". " + entry[1] };
    }).sort(function (left, right) {
      return compareCodes(left.value, right.value);
    });
    setOptions(dom.analysisSection, "전체 과목", sectionEntries);
    setOptions(dom.sectionFilter, "전체 과목", sectionEntries);

    var topicEntries = state.topics.slice().sort(function (left, right) {
      return compareCodes(left.code, right.code);
    }).map(function (topic) {
      return { value: topic.code, label: topic.code + ". " + asText(topic.title, topic.code) };
    });
    setOptions(dom.topicFilter, "전체 토픽", topicEntries);

    var rounds = Array.from(new Set(state.questions.map(roundValue).filter(Boolean)));
    rounds.sort(function (left, right) {
      return compareCodes(right, left);
    });
    setOptions(dom.roundFilter, "전체 회차", rounds.map(function (round) {
      return { value: round, label: filterMetadataLabel("round", round) || round };
    }));

    var answerStatuses = Array.from(new Set(state.questions.map(function (question) {
      return asText(question.answer_status, "");
    }).filter(Boolean))).sort();
    setOptions(dom.answerFilter, "전체 상태", answerStatuses.map(function (status) {
      return { value: status, label: answerLabel(status) };
    }));
    setFilterAvailability(dom.answerFilter, answerStatuses);

    var contentModes = Array.from(new Set(state.questions.map(function (question) {
      return asText(question.content_mode, "");
    }).filter(Boolean))).sort();
    setOptions(dom.contentFilter, "전체 상태", contentModes.map(function (mode) {
      return { value: mode, label: contentLabel(mode) };
    }));
    setFilterAvailability(dom.contentFilter, contentModes);

    var sources = sourceFilterEntries();
    setOptions(dom.sourceFilter, "전체 출처", sources);
    setFilterAvailability(dom.sourceFilter, sources);

    var eligibleCodes = new Set();
    getEligibleQuestions().forEach(function (question) {
      questionTopicCodes(question).forEach(function (code) {
        eligibleCodes.add(code);
      });
    });
    setOptions(dom.practiceTopic, "전체 토픽", topicEntries.filter(function (entry) {
      return eligibleCodes.has(String(entry.value));
    }));
    dom.analysisSort.querySelector("option[value='importance']").disabled = !state.importanceAvailable;
    dom.analysisSort.querySelector("option[value='importance']").hidden = !state.importanceAvailable;
    if (!state.importanceAvailable && dom.analysisSort.value === "importance") {
      dom.analysisSort.value = "frequency";
    }
    resetPracticeQueue(false);
  }

  function createMetric(label, value, note) {
    var metric = make("dl", "qb-metric");
    metric.append(make("dt", "", label));
    var detail = make("dd", "", value);
    if (note) {
      detail.append(make("small", "", note));
    }
    metric.append(detail);
    return metric;
  }

  function summaryNumber(keys, fallback) {
    var summary = state.data.summary;
    if (summary && typeof summary === "object") {
      for (var index = 0; index < keys.length; index += 1) {
        var value = numberOrNull(summary[keys[index]]);
        if (value !== null) {
          return value;
        }
      }
    }
    return fallback;
  }

  function renderAnalysisSummary() {
    var observedTopics = state.topics.filter(function (topic) {
      return (numberOrNull(topic.observed_questions) || 0) > 0;
    }).length;
    var distinctRounds = new Set(state.questions.map(roundValue).filter(Boolean)).size;
    var publicQuestions = state.questions.filter(function (question) {
      var mode = asText(question.content_mode, "");
      return mode === "public_fulltext" ||
        (mode === "full" && asText(question.rights_status, "") === "public_fulltext");
    }).length;
    var eligibleQuestions = getEligibleQuestions().length;
    var analysisSummary = state.data.summary && typeof state.data.summary === "object" ? state.data.summary : {};
    var eligibleRounds = numberOrNull(analysisSummary.eligible_rounds);
    var heldRounds = numberOrNull(analysisSummary.held_round_count);
    var candidateAppearances = numberOrNull(analysisSummary.analysis_eligible_appearances);
    var roundNote = eligibleRounds === null ? "현재 데이터 기준" : "중요도 산정 가능 " + formatNumber(eligibleRounds) + "개";
    dom.analysisSummary.replaceChildren(
      createMetric("관측 근거", formatNumber(summaryNumber(["observed_appearances", "observed_questions", "total_questions", "question_count"], state.questions.length)) + "건", candidateAppearances === null ? "출처별 기록 포함" : "분석 후보 " + formatNumber(candidateAppearances) + "건"),
      createMetric("자료 있는 회차", formatNumber(distinctRounds) + "개", (heldRounds === null ? "시행 회차 기준" : "시행 " + formatNumber(heldRounds) + "회 중") + " · " + roundNote),
      createMetric("관측 토픽", formatNumber(observedTopics) + "개", "전체 " + formatNumber(state.topics.length) + "개 토픽"),
      createMetric("공개 원문", formatNumber(summaryNumber(["public_question_count", "public_questions", "public_fulltext_questions"], publicQuestions)), "연습 가능 " + formatNumber(eligibleQuestions) + "개")
    );

    var summary = state.data.summary;
    var note = "";
    if (!state.importanceAvailable) {
      note = "현재 확보된 회차별 자료가 기준에 미치지 않아 중요도 점수는 산정하지 않습니다. 아래 순서는 확인된 관측 건수이며 출제 확률 순위가 아닙니다.";
    } else if (summary && typeof summary === "object") {
      note = asText(summary.analysis_note, "") || asText(summary.note, "") || asText(summary.limitation, "");
      if (!note && asText(summary.evidence_level, "")) {
        var evidence = normalEvidence(summary.evidence_level);
        var medianCoverage = numberOrNull(summary.median_round_coverage);
        note = "전체 근거 수준은 ‘" + EVIDENCE_LABELS[evidence] + "’입니다." +
          (eligibleRounds === null ? "" : " 빈도 산정 적격 회차는 " + formatNumber(eligibleRounds) + "개입니다.") +
          (medianCoverage === null ? "" : " 적격 회차 중앙 coverage는 " + formatPercent(medianCoverage * 100) + "입니다.");
      }
    }
    if (!note && state.topics.some(function (topic) {
      return normalEvidence(topic.evidence_level) === "insufficient";
    })) {
      note = "표본이 적은 토픽은 중요도 숫자만으로 판단하지 말고, 관측 문항 수와 근거 수준을 함께 확인하세요.";
    }
    dom.analysisNotice.hidden = !note;
    dom.analysisNotice.textContent = note;
  }

  function coverageLabel(row) {
    var round = numberOrNull(row.exam_round);
    return round === null ? asText(row.round_id, "회차 미상") : "제" + round + "회";
  }

  function renderCoverage() {
    var rows = asArray(state.data.coverage).filter(function (row) {
      return row && typeof row === "object" && row.status === "held" && numberOr(row.observed_questions, 0) > 0;
    });
    var held = asArray(state.data.coverage).filter(function (row) {
      return row && row.status === "held";
    });
    var missing = Math.max(0, held.length - rows.length);
    var eligible = rows.filter(function (row) { return row.eligible_for_frequency === true; }).length;
    dom.coverageHeadline.textContent = rows.length ?
      "자료가 있는 " + rows.length + "개 회차 중 중요도 산정 기준을 충족한 회차는 " + eligible + "개입니다." :
      "관측 자료가 있는 시행 회차가 아직 없습니다.";
    if (!rows.length) {
      setEmpty(dom.coverageRows, "회차별 자료가 확보되면 관측 범위를 표시합니다.");
    } else {
      var cards = rows.map(function (row) {
        var observed = numberOr(row.observed_questions, 0);
        var expected = numberOr(row.expected_questions, 0);
        var percent = numberOr(row.coverage, 0) * 100;
        var card = make("article", "qb-coverage-row");
        card.setAttribute("aria-label", coverageLabel(row) + " 자료 범위");
        var heading = make("strong", "", coverageLabel(row));
        var progress = make("progress");
        progress.max = 100;
        progress.value = clamp(percent, 0, 100);
        progress.setAttribute("aria-label", coverageLabel(row) + " 자료 범위 " + formatPercent(percent));
        card.append(heading, progress, make("small", "", observed + " / " + expected + " · " + formatPercent(percent)));
        return card;
      });
      dom.coverageRows.replaceChildren.apply(dom.coverageRows, cards);
    }
    var summary = state.data.summary || {};
    var threshold = numberOr(summary.coverage_threshold, 0.5) * 100;
    var lines = [
      "한 회차에서 확인된 분석 후보가 예상 문항의 " + formatPercent(threshold) + " 이상일 때만 빈도 분모에 포함합니다.",
      "현재 시행 " + held.length + "회 중 자료가 없는 회차는 " + missing + "개이며, 부분 자료를 전체 시험의 출제 확률로 확대 해석하지 않습니다.",
      state.importanceAvailable ? "기준을 충족한 회차만 중요도 산식에 사용합니다." : "기준을 충족한 회차가 없어 중요도와 별점은 표시하지 않습니다."
    ];
    dom.methodologyBody.replaceChildren.apply(dom.methodologyBody, lines.map(function (line) {
      return make("p", "", line);
    }));
  }

  function starText(topic) {
    var stars = topic.stars;
    var number = numberOrNull(stars);
    if (number !== null) {
      var rounded = clamp(Math.round(number), 0, 5);
      return "★".repeat(rounded) + "☆".repeat(5 - rounded);
    }
    var text = asText(stars, "");
    return text || "근거 부족";
  }

  function renderTopicAnalysis() {
    var section = dom.analysisSection.value;
    var sortMode = dom.analysisSort.value;
    var topics = state.topics.filter(function (topic) {
      var sectionMatches = !section || String(topic.section_id) === section;
      var hasObservation = numberOr(topic.observed_questions, 0) > 0;
      return sectionMatches && (state.showAllTopics || hasObservation);
    });
    topics.sort(function (left, right) {
      if (sortMode === "frequency") {
        return numberOr(right.observed_questions, 0) - numberOr(left.observed_questions, 0) ||
          compareCodes(left.code, right.code);
      }
      if (sortMode === "code") {
        return compareCodes(left.code, right.code);
      }
      return (state.importanceAvailable ? numberOr(right.importance_score, -1) - numberOr(left.importance_score, -1) : 0) ||
        numberOr(right.observed_questions, 0) - numberOr(left.observed_questions, 0) ||
        compareCodes(left.code, right.code);
    });
    var hiddenCount = state.topics.filter(function (topic) {
      return (!section || String(topic.section_id) === section) && numberOr(topic.observed_questions, 0) === 0;
    }).length;
    dom.toggleAllTopics.hidden = hiddenCount === 0;
    dom.toggleAllTopics.setAttribute("aria-expanded", state.showAllTopics ? "true" : "false");
    dom.toggleAllTopics.textContent = state.showAllTopics ? "관측 토픽만 보기" : "미관측 토픽 " + hiddenCount + "개도 보기";
    if (!topics.length) {
      setEmpty(dom.topicAnalysis, state.topics.length ? "선택한 과목에 해당하는 토픽이 없습니다." : "아직 분류된 기출 토픽이 없습니다.");
      return;
    }
    var cards = topics.map(function (topic) {
      var evidence = normalEvidence(topic.evidence_level);
      var score = numberOrNull(topic.importance_score);
      var card = make("article", "qb-topic-card");
      card.dataset.evidence = evidence;
      var headingId = "qb-topic-" + safeId(topic.code);
      card.setAttribute("aria-labelledby", headingId);
      var top = make("div", "qb-topic-top");
      top.append(make("span", "qb-code", asText(topic.code, "-")));
      var evidenceBadge = make("span", "qb-evidence", EVIDENCE_LABELS[evidence]);
      evidenceBadge.dataset.level = evidence;
      top.append(evidenceBadge);
      card.append(top);
      var heading = make("h3", "", asText(topic.title, topic.code));
      heading.id = headingId;
      card.append(heading);
      card.append(make("p", "qb-topic-section",
        asText(topic.section_id, "") + (topic.section_title ? ". " + asText(topic.section_title, "") : "")));

      if (state.importanceAvailable && score !== null) {
        var scoreRow = make("div", "qb-score-row");
        var scoreProgress = make("progress", "qb-score-progress");
        scoreProgress.max = 100;
        scoreProgress.value = clamp(score, 0, 100);
        scoreProgress.setAttribute("aria-label", "중요도 " + Math.round(score) + "점");
        scoreRow.append(scoreProgress);
        scoreRow.append(make("span", "qb-score", Math.round(score) + "점"));
        card.append(scoreRow);
        var stars = make("p", "qb-stars", starText(topic));
        stars.setAttribute("aria-label", "중요도 " + starText(topic));
        card.append(stars);
      } else {
        card.append(make("p", "qb-score-unavailable", "중요도 산정 전 · 관측 빈도만 표시"));
      }

      var stats = make("div", "qb-topic-stats");
      [
        [topic.observed_questions, "관측 근거"],
        [topic.distinct_rounds, "관측 회차"],
        [topic.public_question_count, "공개 원문"]
      ].forEach(function (item) {
        var stat = make("div");
        stat.append(make("strong", "", formatNumber(item[0])));
        stat.append(make("span", "", item[1]));
        stats.append(stat);
      });
      card.append(stats);
      var actions = make("div", "qb-topic-actions");
      if (numberOr(topic.observed_questions, 0) > 0) {
        var action = make("button", "qb-topic-action", "분석 포함 근거 " + formatNumber(topic.observed_questions) + "건 보기");
        action.type = "button";
        action.addEventListener("click", function () {
          window.clearTimeout(state.searchTimer);
          ["searchQuery", "roundFilter", "sectionFilter", "sourceFilter", "answerFilter", "contentFilter"].forEach(function (id) {
            dom[id].value = "";
          });
          dom.topicFilter.value = String(topic.code);
          state.analysisEvidenceOnly = true;
          state.searchLimit = 50;
          renderQuestions();
          switchTab("search", true, true);
        });
        actions.append(action);
      }
      var lessonUrl = state.lessonByTopic.get(String(topic.code));
      if (lessonUrl) {
        var lesson = make("a", "qb-lesson-link", "관련 강의 학습");
        lesson.href = lessonUrl;
        actions.append(lesson);
      }
      if (actions.childNodes.length) {
        card.append(actions);
      }
      return card;
    });
    dom.topicAnalysis.replaceChildren.apply(dom.topicAnalysis, cards);
  }

  function searchableText(question) {
    var topicNames = questionTopicCodes(question).map(function (code) {
      return code + " " + topicTitle(code);
    });
    return [
      question.question_text,
      question.concept_summary,
      asArray(question.keywords).join(" "),
      asArray(question.choices).map(choiceText).join(" "),
      asArray(question.source_links).map(function (source) {
        if (!source || typeof source !== "object") {
          return "";
        }
        return [source.source_id, source.provider, source.title, source.label].map(function (value) {
          return asText(value, "");
        }).join(" ");
      }).join(" "),
      topicNames.join(" "),
      question.exam_round,
      question.exam_year
    ].map(function (value) {
      return asText(value, "");
    }).join(" ").toLocaleLowerCase("ko");
  }

  function sourceFilterEntries() {
    var entries = new Map();
    state.questions.forEach(function (question) {
      asArray(question.source_links).forEach(function (source) {
        if (!source || typeof source !== "object") {
          return;
        }
        var sourceId = asText(source.source_id, "");
        var provider = asText(source.provider, "");
        var title = asText(source.title !== undefined ? source.title : source.label, "");
        if (sourceId) {
          entries.set("source:" + sourceId, {
            value: "source:" + sourceId,
            label: provider ? provider + " · " + sourceId : title ? title + " · " + sourceId : sourceId
          });
        }
        if (provider) {
          entries.set("provider:" + provider, {
            value: "provider:" + provider,
            label: "제공자 · " + provider
          });
        }
      });
    });
    return Array.from(entries.values()).sort(function (left, right) {
      return left.label.localeCompare(right.label, "ko", { numeric: true });
    });
  }

  function questionMatchesSection(question, section) {
    return !section || questionTopicCodes(question).some(function (code) {
      var topic = topicFor(code);
      return topic && asText(topic.section_id, "") === section;
    });
  }

  function questionMatchesSource(question, selectedSource) {
    if (!selectedSource) {
      return true;
    }
    var separator = selectedSource.indexOf(":");
    var kind = separator === -1 ? "" : selectedSource.slice(0, separator);
    var value = separator === -1 ? selectedSource : selectedSource.slice(separator + 1);
    return asArray(question.source_links).some(function (source) {
      if (!source || typeof source !== "object") {
        return false;
      }
      var sourceId = asText(source.source_id, "");
      var provider = asText(source.provider, "");
      if (kind === "source") {
        return sourceId === value;
      }
      if (kind === "provider") {
        return provider === value;
      }
      return sourceId === value || provider === value;
    });
  }

  function filteredQuestions() {
    var query = dom.searchQuery.value.trim().toLocaleLowerCase("ko");
    var round = dom.roundFilter.value;
    var section = dom.sectionFilter.value;
    var topic = dom.topicFilter.value;
    var source = dom.sourceFilter.value;
    var answer = dom.answerFilter.value;
    var content = dom.contentFilter.value;
    return state.questions.filter(function (question) {
      var indexed = state.searchIndex.get(storageQuestionId(question)) || "";
      var topicMatches = !topic || (state.analysisEvidenceOnly ?
        asText(question.primary_topic_code, "") === topic :
        questionTopicCodes(question).indexOf(topic) !== -1);
      return (!query || indexed.indexOf(query) !== -1) &&
        (!round || roundValue(question) === round) &&
        questionMatchesSection(question, section) &&
        topicMatches &&
        questionMatchesSource(question, source) &&
        (!answer || asText(question.answer_status, "") === answer) &&
        (!content || asText(question.content_mode, "") === content) &&
        (!state.analysisEvidenceOnly || question.analysis_eligible === true);
    }).sort(function (left, right) {
      return compareCodes(roundValue(right), roundValue(left)) ||
        compareCodes(storageQuestionId(left), storageQuestionId(right));
    });
  }

  function badge(text, kind) {
    var item = make("span", "qb-badge", text);
    if (kind) {
      item.dataset.kind = kind;
    }
    return item;
  }

  function renderChoices(question) {
    var choices = asArray(question.choices);
    if (!choices.length) {
      return null;
    }
    var list = make("ol", "qb-choice-list");
    choices.forEach(function (choice) {
      list.append(make("li", "", choiceText(choice)));
    });
    return list;
  }

  function answerTokens(value) {
    if (Array.isArray(value)) {
      return value.reduce(function (all, item) {
        return all.concat(answerTokens(item));
      }, []);
    }
    if (value && typeof value === "object") {
      var objectValue = value.answers !== undefined ? value.answers :
        value.accepted !== undefined ? value.accepted :
          value.choice !== undefined ? value.choice :
            value.choice_index !== undefined ? value.choice_index :
              value.index !== undefined ? value.index :
                value.value !== undefined ? value.value : value.label;
      return objectValue === undefined ? [] : answerTokens(objectValue);
    }
    if (typeof value === "string" || typeof value === "number") {
      return [value];
    }
    return [];
  }

  function normalizeAnswerString(value) {
    return String(value).trim().replace(/\s+/g, " ").toLocaleLowerCase("ko");
  }

  function answerIndices(question) {
    var choices = asArray(question.choices);
    var tokens = answerTokens(question.accepted_answer);
    if (tokens.length === 1 && typeof tokens[0] === "string") {
      var whole = normalizeAnswerString(tokens[0]);
      var exactChoice = choices.findIndex(function (choice, index) {
        return normalizeAnswerString(choiceToken(choice, index)) === whole ||
          normalizeAnswerString(choiceText(choice)) === whole;
      });
      if (exactChoice === -1 && /[,;/]/.test(whole)) {
        tokens = whole.split(/[,;/]/).map(function (token) { return token.trim(); }).filter(Boolean);
      }
    }
    var circled = {"①": 0, "②": 1, "③": 2, "④": 3, "⑤": 4, "⑥": 5, "⑦": 6, "⑧": 7, "⑨": 8};
    var result = [];
    tokens.forEach(function (token) {
      var index = -1;
      if (typeof token === "number" && Number.isInteger(token)) {
        index = token === 0 ? 0 : token - 1;
      } else {
        var normalized = normalizeAnswerString(token);
        if (circled[normalized] !== undefined) {
          index = circled[normalized];
        }
        if (index === -1) {
          index = choices.findIndex(function (choice, choiceIndex) {
            return normalizeAnswerString(choiceToken(choice, choiceIndex)) === normalized ||
              normalizeAnswerString(choiceText(choice)) === normalized;
          });
        }
        if (index === -1) {
          var numberMatch = normalized.match(/^(\d+)\s*(?:번)?$/);
          if (numberMatch) {
            index = Number(numberMatch[1]) - 1;
          }
        }
        if (index === -1 && /^[a-z]$/.test(normalized)) {
          index = normalized.charCodeAt(0) - 97;
        }
      }
      if (index >= 0 && index < choices.length && result.indexOf(index) === -1) {
        result.push(index);
      }
    });
    return result.sort(function (left, right) { return left - right; });
  }

  function acceptedAnswerText(question) {
    var indices = answerIndices(question);
    var choices = asArray(question.choices);
    if (indices.length) {
      return indices.map(function (index) {
        return (index + 1) + ". " + choiceText(choices[index]);
      }).join(" / ");
    }
    var tokens = answerTokens(question.accepted_answer);
    return tokens.map(function (token) { return asText(token, ""); }).filter(Boolean).join(" / ") || "확인된 답안 없음";
  }

  function explanationItems(value) {
    if (Array.isArray(value)) {
      return value.map(function (item, index) {
        if (item && typeof item === "object") {
          var label = asText(item.label !== undefined ? item.label : item.choice, String(index + 1));
          var text = asText(item.explanation !== undefined ? item.explanation : item.text, "");
          return text ? label + ". " + text : "";
        }
        return asText(item, "");
      }).filter(Boolean);
    }
    if (value && typeof value === "object") {
      return Object.keys(value).map(function (key) {
        var text = asText(value[key], "");
        return text ? key + ". " + text : "";
      }).filter(Boolean);
    }
    return [];
  }

  function appendAnswerDetails(card, question) {
    var explanation = asText(question.explanation, "");
    var itemExplanations = explanationItems(question.choice_explanations);
    var hasAnswer = answerTokens(question.accepted_answer).length > 0;
    if (!hasAnswer && !explanation && !itemExplanations.length) {
      return;
    }
    var details = make("details");
    details.append(make("summary", "", "답안과 해설 보기"));
    var body = make("div", "qb-answer-block");
    if (hasAnswer) {
      var answerLine = make("p");
      answerLine.append(make("span", "qb-answer-value", "제시 답안: "));
      answerLine.append(document.createTextNode(acceptedAnswerText(question)));
      body.append(answerLine);
    }
    if (explanation) {
      body.append(make("p", "", explanation));
    }
    if (itemExplanations.length) {
      var list = make("ul", "qb-explanation-list");
      itemExplanations.forEach(function (item) {
        list.append(make("li", "", item));
      });
      body.append(list);
    }
    details.append(body);
    card.append(details);
  }

  function safeLink(value) {
    try {
      var url = new URL(value, document.baseURI);
      return url.protocol === "http:" || url.protocol === "https:" ? url.href : "";
    } catch (error) {
      return "";
    }
  }

  function appendSourceLinks(card, links) {
    var validLinks = asArray(links).map(function (source, index) {
      var rawUrl;
      var label;
      if (typeof source === "string") {
        rawUrl = source;
        label = "출처 " + (index + 1);
      } else if (source && typeof source === "object") {
        rawUrl = source.url !== undefined ? source.url : source.href;
        label = asText(source.title !== undefined ? source.title :
          source.label !== undefined ? source.label : source.provider, "출처 " + (index + 1));
      }
      var href = safeLink(rawUrl);
      return href ? {
        href: href,
        label: label,
        reliability: source && typeof source === "object" ? asText(source.reliability, "unknown") : "unknown",
        locator: source && typeof source === "object" ? asText(source.locator, "") : "",
        provider: source && typeof source === "object" ? asText(source.provider, "") : ""
      } : null;
    }).filter(Boolean);
    if (!validLinks.length) {
      return;
    }
    var container = make("div", "qb-source-list");
    container.setAttribute("aria-label", "출처 근거");
    var reliabilityLabels = { high: "신뢰도 높음", medium: "신뢰도 보통", low: "신뢰도 낮음", unknown: "신뢰도 미표기" };
    validLinks.forEach(function (source) {
      var item = make("div", "qb-source-item");
      var link = make("a", "qb-source-link", source.provider ? source.provider + " · " + source.label : source.label);
      link.href = source.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.append(make("span", "qb-sr-only", " (새 창)"));
      var reliability = reliabilityLabels[source.reliability] ? source.reliability : "unknown";
      var reliabilityBadge = make("span", "qb-source-meta", reliabilityLabels[reliability]);
      reliabilityBadge.dataset.reliability = reliability;
      item.append(link, reliabilityBadge);
      if (source.locator) {
        item.append(make("p", "qb-source-locator", "확인 위치: " + source.locator));
      }
      container.append(item);
    });
    card.append(container);
  }

  function observationTitle(question) {
    var explicit = asText(question.display_title !== undefined ? question.display_title : question.title, "");
    if (explicit) {
      return explicit;
    }
    var keywords = asArray(question.keywords).map(function (keyword) { return asText(keyword, ""); }).filter(Boolean);
    if (keywords.length) {
      return keywords.slice(0, 3).join(" · ");
    }
    var code = asText(question.primary_topic_code, "");
    return code ? topicTitle(code) + " 관련 관측" : "기출 관측 기록";
  }

  function appendLessonCta(card, question) {
    var code = asText(question.primary_topic_code, "");
    var lessonUrl = state.lessonByTopic.get(code);
    if (!lessonUrl) {
      return;
    }
    var lesson = make("a", "qb-lesson-link", "이 개념의 강의 학습하기");
    lesson.href = lessonUrl;
    card.append(lesson);
  }

  function createQuestionCard(question, options) {
    options = options || {};
    var card = make("article", "qb-question-card");
    var id = storageQuestionId(question) || asText(question.question_id, hashString(JSON.stringify(question)));
    var headingId = "qb-record-" + safeId(id);
    card.setAttribute("aria-labelledby", headingId);
    card.dataset.recordId = id;
    var metadata = make("div", "qb-question-meta");
    if (options.generated) {
      metadata.append(badge("생성문제 · 실제 기출 아님", "review"));
    } else {
      metadata.append(badge(roundLabel(question), "muted"));
    }
    var primaryCode = asText(question.primary_topic_code, "");
    if (primaryCode) {
      metadata.append(badge(primaryCode + ". " + topicTitle(primaryCode), "muted"));
    }
    if (options.generated) {
      metadata.append(badge("검토 승인", "verified"));
    } else {
      var answerStatus = asText(question.answer_status, "unverified");
      if (answerStatus !== "unverified") {
        metadata.append(badge(answerLabel(answerStatus), answerBadgeKind(answerStatus)));
      }
      var mode = asText(question.content_mode, "link_only");
      metadata.append(badge(mode === "link_only" ? "개념 요약·출처" : questionContentLabel(question), mode === "public_fulltext" || mode === "full" ? "verified" : "muted"));
    }
    card.append(metadata);

    var questionText = asText(question.question_text, "");
    if (questionText) {
      var questionHeading = make("h3", "", questionText);
      questionHeading.id = headingId;
      card.append(questionHeading);
      var choices = renderChoices(question);
      if (choices) {
        card.append(choices);
      }
    } else {
      var observationHeading = make("h3", "", observationTitle(question));
      observationHeading.id = headingId;
      card.append(observationHeading);
      card.append(make("p", "qb-restricted", "이 문항의 원문은 공개되지 않습니다. 아래 개념 요약과 출처를 학습 단서로 활용하세요."));
    }
    var keywords = asArray(question.keywords).map(function (keyword) {
      return asText(keyword, "");
    }).filter(Boolean);
    if (keywords.length) {
      var keywordList = make("div", "qb-keywords");
      keywords.forEach(function (keyword) {
        keywordList.append(make("span", "", keyword));
      });
      card.append(keywordList);
    }
    var concept = asText(question.concept_summary, "");
    if (concept) {
      card.append(make("p", "qb-concept", concept));
    }
    appendAnswerDetails(card, question);
    if (!options.generated) {
      appendSourceLinks(card, question.source_links);
    }
    appendLessonCta(card, question);
    return card;
  }

  function renderQuestions() {
    var questions = filteredQuestions();
    var shown = questions.slice(0, state.searchLimit);
    var recordLabel = state.analysisEvidenceOnly ? "분석 포함 기록" : "관측 기록";
    dom.searchResultCount.textContent = questions.length > shown.length ?
      recordLabel + " " + formatNumber(questions.length) + "건 중 " + formatNumber(shown.length) + "건 표시" :
      recordLabel + " " + formatNumber(questions.length) + "건";
    if (!questions.length) {
      setEmpty(dom.questionResults, state.questions.length ?
        (state.analysisEvidenceOnly ? "검색 조건에 맞는 분석 포함 근거가 없습니다." : "검색 조건에 맞는 기출 근거가 없습니다.") :
        "공개 가능한 기출 근거가 아직 없습니다.");
      return;
    }
    var nodes = shown.map(createQuestionCard);
    if (questions.length > shown.length) {
      var more = make("button", "qb-button qb-button-secondary", "관측 기록 더 보기");
      more.type = "button";
      more.addEventListener("click", function () {
        var previousCount = shown.length;
        state.searchLimit += 50;
        renderQuestions();
        var headings = dom.questionResults.querySelectorAll("article h3");
        if (headings[previousCount]) {
          headings[previousCount].tabIndex = -1;
          headings[previousCount].focus();
        }
      });
      nodes.push(more);
    }
    dom.questionResults.replaceChildren.apply(dom.questionResults, nodes);
  }

  function getEligibleQuestions() {
    return state.questions.filter(function (question) {
      return question.practice_eligible === true &&
        asText(question.question_text, "") &&
        asArray(question.choices).length >= 2 &&
        answerIndices(question).length > 0;
    });
  }

  function shuffle(items) {
    var copy = items.slice();
    for (var index = copy.length - 1; index > 0; index -= 1) {
      var next = Math.floor(Math.random() * (index + 1));
      var temporary = copy[index];
      copy[index] = copy[next];
      copy[next] = temporary;
    }
    return copy;
  }

  function resetPracticeQueue(randomize) {
    var selectedTopic = dom.practiceTopic.value;
    var questions = getEligibleQuestions().filter(function (question) {
      return !selectedTopic || questionTopicCodes(question).indexOf(selectedTopic) !== -1;
    });
    state.practiceQueue = randomize ? shuffle(questions) : questions.slice().sort(function (left, right) {
      return compareCodes(storageQuestionId(left), storageQuestionId(right));
    });
    state.practiceIndex = 0;
    renderPractice();
  }

  function updatePracticeProgress() {
    if (!state.practiceQueue.length) {
      dom.practiceProgress.textContent = "연습 가능한 문제 0개";
      return;
    }
    dom.practiceProgress.textContent = (state.practiceIndex + 1) + " / " + state.practiceQueue.length +
      " · 누적 " + currentAttempts().length + "회 풀이";
  }

  function equalNumberSets(left, right) {
    if (left.length !== right.length) {
      return false;
    }
    var sortedLeft = left.slice().sort();
    var sortedRight = right.slice().sort();
    return sortedLeft.every(function (value, index) {
      return value === sortedRight[index];
    });
  }

  function createPracticeFeedback(question, correct) {
    var feedback = make("div", "qb-feedback");
    feedback.dataset.correct = correct ? "true" : "false";
    feedback.tabIndex = -1;
    feedback.append(make("h4", "", correct ? "정답입니다." : "다시 확인해 보세요."));
    feedback.append(make("p", "", "정답: " + acceptedAnswerText(question)));
    var explanation = asText(question.explanation, "");
    if (explanation) {
      feedback.append(make("p", "", explanation));
    }
    var items = explanationItems(question.choice_explanations);
    if (items.length) {
      var details = make("details");
      details.append(make("summary", "", "선택지별 해설"));
      var list = make("ul", "qb-explanation-list");
      items.forEach(function (item) {
        list.append(make("li", "", item));
      });
      details.append(list);
      feedback.append(details);
    }
    return feedback;
  }

  function renderPractice() {
    updatePracticeProgress();
    if (!state.practiceQueue.length) {
      dom.practiceControls.hidden = true;
      setActionEmpty(
        dom.practiceCard,
        "아직 공개 연습문제가 없습니다",
        state.questions.some(function (question) { return question.practice_eligible === true; }) ?
          "연습 가능 표시가 있지만 원문·선택지·검증 답안 형식을 모두 확인하지 못했습니다." :
          "저작권과 정답이 확인된 원문만 연습문제로 제공합니다. 지금은 기출 근거에서 관측 개념을 확인하고 관련 강의로 학습해 주세요.",
        courseUrl(),
        "과정 강의 보기"
      );
      dom.shufflePractice.disabled = true;
      return;
    }
    dom.practiceControls.hidden = false;
    dom.shufflePractice.disabled = false;
    var question = state.practiceQueue[state.practiceIndex];
    var choices = asArray(question.choices);
    var accepted = answerIndices(question);
    var multiple = accepted.length > 1;
    var form = make("form", "qb-practice-question");
    var metadata = make("div", "qb-question-meta");
    metadata.append(badge(roundLabel(question), "muted"));
    var code = asText(question.primary_topic_code, "");
    if (code) {
      metadata.append(badge(code + ". " + topicTitle(code), "muted"));
    }
    metadata.append(badge(multiple ? "복수 선택" : "단일 선택", "verified"));
    form.append(metadata);
    var questionHeading = make("h3", "", asText(question.question_text, ""));
    questionHeading.id = "qb-practice-heading";
    questionHeading.tabIndex = -1;
    form.append(questionHeading);

    var fieldset = make("fieldset", "qb-practice-options");
    fieldset.setAttribute("aria-labelledby", questionHeading.id);
    fieldset.append(make("legend", "", multiple ? "정답을 모두 선택하세요." : "정답 하나를 선택하세요."));
    var inputName = "qb-answer-" + hashString(storageQuestionId(question));
    choices.forEach(function (choice, index) {
      var label = make("label");
      var input = document.createElement("input");
      input.type = multiple ? "checkbox" : "radio";
      input.name = inputName;
      input.value = String(index);
      var text = make("span", "", (index + 1) + ". " + choiceText(choice));
      label.append(input, text);
      fieldset.append(label);
    });
    form.append(fieldset);

    var actions = make("div", "qb-practice-actions");
    var submit = make("button", "qb-button", "정답 확인");
    submit.type = "submit";
    var skip = make("button", "qb-button qb-button-secondary", "건너뛰기");
    skip.type = "button";
    skip.addEventListener("click", function () {
      moveToNextPractice();
    });
    actions.append(submit, skip);
    form.append(actions);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var inputs = Array.from(fieldset.querySelectorAll("input"));
      var selected = inputs.filter(function (input) { return input.checked; }).map(function (input) {
        return Number(input.value);
      });
      if (!selected.length) {
        var existing = form.querySelector(".qb-selection-warning");
        if (!existing) {
          existing = make("p", "qb-note qb-selection-warning", "답을 먼저 선택해 주세요.");
          actions.before(existing);
        }
        existing.setAttribute("role", "alert");
        return;
      }
      var warning = form.querySelector(".qb-selection-warning");
      if (warning) {
        warning.remove();
      }
      var correct = equalNumberSets(selected, accepted);
      inputs.forEach(function (input) {
        input.disabled = true;
        var index = Number(input.value);
        var label = input.closest("label");
        if (accepted.indexOf(index) !== -1) {
          label.classList.add("qb-option-correct");
        } else if (input.checked) {
          label.classList.add("qb-option-wrong");
        }
      });
      submit.disabled = true;
      skip.remove();
      recordAttempt(question, selected, correct);
      var feedback = createPracticeFeedback(question, correct);
      form.append(feedback);
      var next = make("button", "qb-button", state.practiceIndex === state.practiceQueue.length - 1 ? "처음부터 다시" : "다음 문제");
      next.type = "button";
      next.addEventListener("click", moveToNextPractice);
      actions.append(next);
      updatePracticeProgress();
      feedback.focus();
    });

    dom.practiceCard.replaceChildren(form);
    if (state.focusPracticeAfterRender) {
      state.focusPracticeAfterRender = false;
      window.requestAnimationFrame(function () { questionHeading.focus(); });
    }
  }

  function moveToNextPractice() {
    state.practiceIndex = state.practiceIndex >= state.practiceQueue.length - 1 ? 0 : state.practiceIndex + 1;
    state.focusPracticeAfterRender = true;
    renderPractice();
    dom.practiceCard.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "nearest" });
  }

  function progressEnvelope() {
    return {
      schema_version: 1,
      course_id: asText(state.data.course_id, "question-bank"),
      dataset_version: asText(state.data.dataset_version, ""),
      content_hash: state.datasetHash,
      updated_at: new Date().toISOString(),
      attempts: state.progress ? state.progress.attempts.slice(-MAX_STORED_ATTEMPTS) : []
    };
  }

  function loadProgress() {
    var courseId = asText(state.data.course_id, "question-bank").replace(/[^a-zA-Z0-9._-]/g, "-");
    state.storageKey = STORAGE_PREFIX + courseId;
    state.storageAvailable = true;
    var attempts = [];
    try {
      var stored = window.localStorage.getItem(state.storageKey);
      if (stored) {
        var parsed = JSON.parse(stored);
        if (parsed && parsed.schema_version === 1 && Array.isArray(parsed.attempts)) {
          attempts = parsed.attempts.filter(function (attempt) {
            return attempt && typeof attempt === "object" && asText(attempt.question_storage_id, "");
          }).slice(-MAX_STORED_ATTEMPTS);
        }
      }
    } catch (error) {
      console.warn("Question-bank progress is unavailable.", error);
      state.storageAvailable = false;
    }
    state.progress = { attempts: attempts };
    saveProgress();
  }

  function saveProgress() {
    if (!state.storageAvailable) {
      return;
    }
    try {
      window.localStorage.setItem(state.storageKey, JSON.stringify(progressEnvelope()));
    } catch (error) {
      console.warn("Question-bank progress could not be saved.", error);
      state.storageAvailable = false;
    }
  }

  function currentAttempts() {
    if (!state.progress) {
      return [];
    }
    return state.progress.attempts.filter(function (attempt) {
      var id = asText(attempt.question_storage_id, "");
      return state.questionHashes.has(id) && state.questionHashes.get(id) === asText(attempt.question_content_hash, "");
    });
  }

  function recordAttempt(question, selected, correct) {
    var id = storageQuestionId(question);
    state.progress.attempts.push({
      question_storage_id: id,
      question_id: asText(question.question_id, ""),
      appearance_id: asText(question.appearance_id, ""),
      primary_topic_code: asText(question.primary_topic_code, ""),
      selected_answers: selected.slice(),
      correct: correct === true,
      attempted_at: new Date().toISOString(),
      question_content_hash: state.questionHashes.get(id) || questionHash(question)
    });
    if (state.progress.attempts.length > MAX_STORED_ATTEMPTS) {
      state.progress.attempts = state.progress.attempts.slice(-MAX_STORED_ATTEMPTS);
    }
    saveProgress();
    renderWeakTopics();
  }

  function renderWeakTopics() {
    var attempts = currentAttempts();
    if (!state.practiceAvailable && !attempts.length) {
      dom.weakSummary.hidden = true;
      dom.weakActions.hidden = true;
      setActionEmpty(
        dom.weakTopics,
        "취약영역을 계산할 풀이 기록이 없습니다",
        "취약영역은 검증된 연습문제를 푼 기록으로만 계산합니다. 현재는 공개 연습문제가 없어 기출 근거와 관련 강의를 먼저 확인할 수 있습니다.",
        courseUrl(),
        "과정 강의 보기"
      );
      return;
    }
    dom.weakSummary.hidden = false;
    dom.weakActions.hidden = false;
    var correct = attempts.filter(function (attempt) { return attempt.correct === true; }).length;
    var groups = new Map();
    attempts.forEach(function (attempt) {
      var code = asText(attempt.primary_topic_code, "");
      if (!code) {
        var question = state.questionByStorageId.get(asText(attempt.question_storage_id, ""));
        code = question ? asText(question.primary_topic_code, "") : "";
      }
      code = code || "unclassified";
      if (!groups.has(code)) {
        groups.set(code, { code: code, attempts: 0, correct: 0 });
      }
      var group = groups.get(code);
      group.attempts += 1;
      group.correct += attempt.correct === true ? 1 : 0;
    });
    var assessedCount = Array.from(groups.values()).filter(function (group) {
      return group.attempts >= 3;
    }).length;
    dom.weakSummary.replaceChildren(
      createMetric("누적 풀이", formatNumber(attempts.length), "현재 콘텐츠 기준"),
      createMetric("정답", formatNumber(correct), "오답 " + formatNumber(attempts.length - correct) + "개"),
      createMetric("전체 정확도", attempts.length ? formatPercent(correct / attempts.length * 100) : "-", "3회 이상 토픽부터 판정"),
      createMetric("판정 완료", formatNumber(assessedCount), "풀이 토픽 " + formatNumber(groups.size) + "개")
    );
    dom.progressDatasetNote.textContent = state.storageAvailable ?
      "데이터 " + asText(state.data.dataset_version, "-") + " · 콘텐츠 지문 " + state.datasetHash + "에 맞는 기록만 집계합니다." :
      "브라우저 저장소를 사용할 수 없어 현재 페이지를 닫으면 풀이 기록이 사라집니다.";
    dom.resetProgress.disabled = attempts.length === 0;

    if (!groups.size) {
      setEmpty(dom.weakTopics, "아직 풀이 기록이 없습니다. 실전연습에서 같은 토픽을 3회 이상 풀면 취약도를 판단합니다.");
      return;
    }
    var rows = Array.from(groups.values()).map(function (group) {
      group.accuracy = group.correct / group.attempts * 100;
      if (group.attempts < 3) {
        group.status = "pending";
        group.statusLabel = "판정까지 " + (3 - group.attempts) + "회";
      } else if (group.accuracy < 60) {
        group.status = "weak";
        group.statusLabel = "보완 필요";
      } else if (group.accuracy < 80) {
        group.status = "review";
        group.statusLabel = "복습 권장";
      } else {
        group.status = "stable";
        group.statusLabel = "안정";
      }
      return group;
    });
    var rank = { weak: 0, review: 1, pending: 2, stable: 3 };
    rows.sort(function (left, right) {
      return rank[left.status] - rank[right.status] ||
        left.accuracy - right.accuracy ||
        compareCodes(left.code, right.code);
    });
    var cards = rows.map(function (group) {
      var card = make("article", "qb-weak-card");
      var headingId = "qb-weak-" + safeId(group.code);
      card.setAttribute("aria-labelledby", headingId);
      var heading = make("div");
      var headingText = make("h3", "", group.code === "unclassified" ? "미분류 토픽" : group.code + ". " + topicTitle(group.code));
      headingText.id = headingId;
      heading.append(headingText);
      heading.append(make("p", "", group.correct + "개 정답 / " + group.attempts + "회 풀이"));
      card.append(heading);
      var status = make("span", "qb-weak-status", group.statusLabel);
      status.dataset.status = group.status;
      card.append(status);
      var accuracy = make("div", "qb-accuracy");
      var progress = make("progress", "qb-accuracy-progress");
      progress.max = 100;
      progress.value = clamp(group.accuracy, 0, 100);
      progress.setAttribute("aria-label", topicTitle(group.code) + " 정확도 " + Math.round(group.accuracy) + "%");
      accuracy.append(progress);
      accuracy.append(make("strong", "", Math.round(group.accuracy) + "%"));
      card.append(accuracy);
      return card;
    });
    dom.weakTopics.replaceChildren.apply(dom.weakTopics, cards);
  }

  function resetProgress() {
    if (!currentAttempts().length) {
      return;
    }
    if (!window.confirm("이 데이터셋의 학습 기록을 모두 초기화할까요? 이 작업은 되돌릴 수 없습니다.")) {
      return;
    }
    state.progress = { attempts: [] };
    if (state.storageAvailable) {
      try {
        window.localStorage.removeItem(state.storageKey);
      } catch (error) {
        state.storageAvailable = false;
      }
    }
    saveProgress();
    renderWeakTopics();
    updatePracticeProgress();
  }

  function safeLessonUrl(value, topicCode) {
    try {
      var url = new URL(value, document.baseURI);
      var courseId = courseIdFromPath();
      var prefix = "/study/courses/" + encodeURIComponent(courseId) + "/lessons/";
      var lessonSegment = decodeURIComponent(url.pathname.slice(prefix.length).split("/")[0] || "");
      if (url.origin !== window.location.origin || url.pathname.indexOf(prefix) !== 0 ||
          lessonSegment.indexOf(String(topicCode) + "-") !== 0) {
        return "";
      }
      return url.pathname + url.search + url.hash;
    } catch (error) {
      return "";
    }
  }

  async function loadLessonMap() {
    state.topics.forEach(function (topic) {
      var explicit = safeLessonUrl(topic.lesson_url, topic.code);
      if (explicit) {
        state.lessonByTopic.set(String(topic.code), explicit);
      }
    });
    var controller = typeof AbortController === "function" ? new AbortController() : null;
    var timer = controller ? window.setTimeout(function () { controller.abort(); }, FETCH_TIMEOUT_MS) : null;
    try {
      var response = await fetch(courseUrl(), {
        cache: "no-cache",
        credentials: "same-origin",
        signal: controller ? controller.signal : undefined
      });
      if (!response.ok) {
        return;
      }
      var parsed = new DOMParser().parseFromString(await response.text(), "text/html");
      parsed.querySelectorAll("a[href]").forEach(function (anchor) {
        state.topics.forEach(function (topic) {
          var candidate = safeLessonUrl(anchor.getAttribute("href"), topic.code);
          if (candidate && !state.lessonByTopic.has(String(topic.code))) {
            state.lessonByTopic.set(String(topic.code), candidate);
          }
        });
      });
      renderTopicAnalysis();
      renderQuestions();
      if (state.generatedState === "ready") {
        renderGenerated();
      }
    } catch (error) {
      console.warn("Lesson links are unavailable.", error);
    } finally {
      if (timer) {
        window.clearTimeout(timer);
      }
    }
  }

  function normalizeGeneratedQuestion(question) {
    var copy = Object.assign({}, question);
    copy.appearance_id = "generated-" + asText(question.question_id, hashString(JSON.stringify(question)));
    copy.primary_topic_code = asArray(question.topic_codes).map(function (code) { return asText(code, ""); }).filter(Boolean)[0] || "";
    copy.accepted_answer = question.answer;
    copy.answer_status = "expert_reviewed";
    copy.content_mode = "full";
    return copy;
  }

  async function loadGeneratedDataset() {
    state.generatedState = "loading";
    try {
      var generated = await fetchDataset(GENERATED_DATA_PATH, { optional: true, generated: true });
      if (!generated) {
        state.generatedState = "absent";
        state.generatedData = null;
        state.generatedQuestions = [];
      } else {
        state.generatedState = "ready";
        state.generatedData = generated;
        state.generatedQuestions = generated.questions.map(normalizeGeneratedQuestion);
      }
    } catch (error) {
      console.error(error);
      state.generatedState = "error";
      state.generatedData = null;
      state.generatedQuestions = [];
    }
    applyCapabilityNavigation();
    renderGenerated();
  }

  function renderGenerated() {
    if (state.generatedState === "loading") {
      dom.generatedStatus.textContent = "생성문제 파일을 확인하고 있습니다.";
      setEmpty(dom.generatedResults, "생성문제를 준비하고 있습니다.");
      return;
    }
    if (state.generatedState === "absent") {
      dom.generatedStatus.textContent = "게시된 생성문제 0개";
      setActionEmpty(dom.generatedResults, "게시된 생성문제가 없습니다", "검토 승인된 생성문제가 게시되면 실제 기출과 분리된 이 공간에 표시합니다.", courseUrl(), "과정 강의 보기");
      return;
    }
    if (state.generatedState === "error") {
      dom.generatedStatus.textContent = "생성문제 데이터 오류";
      setActionEmpty(dom.generatedResults, "생성문제를 안전하게 표시할 수 없습니다", "공개 범위·승인 상태·무결성을 확인하지 못해 표시를 중단했습니다. 실제 기출 근거 데이터에는 영향을 주지 않습니다.", courseUrl(), "과정 강의 보기");
      return;
    }
    dom.generatedStatus.textContent = "게시된 생성문제 " + formatNumber(state.generatedQuestions.length) + "개";
    if (!state.generatedQuestions.length) {
      setActionEmpty(dom.generatedResults, "승인된 생성문제가 아직 없습니다", "생성문제는 검토 승인을 통과한 항목만 별도로 게시합니다.", courseUrl(), "과정 강의 보기");
      return;
    }
    dom.generatedResults.replaceChildren.apply(dom.generatedResults, state.generatedQuestions.map(function (question) {
      return createQuestionCard(question, { generated: true });
    }));
  }

  function requestedTabName() {
    var name = window.location.hash.slice(1);
    return TAB_NAMES.indexOf(name) === -1 ? "analysis" : name;
  }

  function applyCapabilityNavigation() {
    var requested = requestedTabName();
    var practiceHidden = !state.practiceAvailable && requested !== "practice";
    var weakHidden = !state.practiceAvailable && requested !== "weak";
    dom["practice-tab"].hidden = practiceHidden;
    dom["weak-tab"].hidden = weakHidden;
    dom["practice-tab"].setAttribute("aria-disabled", state.practiceAvailable ? "false" : "true");
    dom["weak-tab"].setAttribute("aria-disabled", state.practiceAvailable ? "false" : "true");
    var generatedVisible = (state.generatedState === "ready" && state.generatedQuestions.length > 0) || requested === "generated";
    dom["generated-tab"].hidden = !generatedVisible;
    dom["generated-tab"].setAttribute("aria-disabled", state.generatedState === "ready" ? "false" : "true");
  }

  var URL_CONTROL_PARAMS = {
    searchQuery: "q",
    roundFilter: "round",
    sectionFilter: "section",
    topicFilter: "topic",
    sourceFilter: "source",
    answerFilter: "answer",
    contentFilter: "content",
    analysisSection: "analysis_section",
    analysisSort: "sort"
  };

  function setControlFromParam(id, value) {
    var control = dom[id];
    if (!control || value === null) {
      return;
    }
    if (control.tagName === "SELECT" && !Array.from(control.options).some(function (item) { return item.value === value && !item.disabled; })) {
      return;
    }
    control.value = value;
  }

  function applyStateFromUrl(shouldRender) {
    if (!state.data) {
      return;
    }
    state.applyingUrlState = true;
    var params = new URLSearchParams(window.location.search);
    Object.keys(URL_CONTROL_PARAMS).forEach(function (id) {
      var value = params.get(URL_CONTROL_PARAMS[id]);
      if (value !== null) {
        setControlFromParam(id, value);
      } else {
        dom[id].value = id === "analysisSort" ? "frequency" : "";
      }
    });
    if (!state.importanceAvailable && dom.analysisSort.value === "importance") {
      dom.analysisSort.value = "frequency";
    }
    state.analysisEvidenceOnly = params.get("eligibility") === "analysis";
    state.showAllTopics = params.get("topics") === "all";
    state.searchLimit = 50;
    applyCapabilityNavigation();
    var requested = requestedTabName();
    if (!window.location.hash && (params.get("topic") || state.analysisEvidenceOnly)) {
      requested = "search";
    }
    switchTab(requested, false, false);
    if (shouldRender) {
      renderTopicAnalysis();
      renderQuestions();
      resetPracticeQueue(false);
    }
    state.applyingUrlState = false;
  }

  function syncUrl(mode) {
    if (!state.data || state.applyingUrlState) {
      return;
    }
    var url = new URL(window.location.href);
    url.searchParams.delete("scope");
    Object.keys(URL_CONTROL_PARAMS).forEach(function (id) {
      var value = dom[id].value.trim();
      if (id === "analysisSort" && value === "frequency") {
        url.searchParams.delete(URL_CONTROL_PARAMS[id]);
      } else if (value) {
        url.searchParams.set(URL_CONTROL_PARAMS[id], value);
      } else {
        url.searchParams.delete(URL_CONTROL_PARAMS[id]);
      }
    });
    if (state.showAllTopics) {
      url.searchParams.set("topics", "all");
    } else {
      url.searchParams.delete("topics");
    }
    if (state.analysisEvidenceOnly) {
      url.searchParams.set("eligibility", "analysis");
    } else {
      url.searchParams.delete("eligibility");
    }
    url.hash = state.activeTab === "analysis" ? "" : state.activeTab;
    window.history[mode === "push" ? "pushState" : "replaceState"](null, "", url.pathname + url.search + url.hash);
  }

  async function copyCurrentView() {
    syncUrl("replace");
    var href = window.location.href;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(href);
      } else {
        var field = document.createElement("textarea");
        field.value = href;
        field.setAttribute("readonly", "");
        field.className = "qb-sr-only";
        document.body.append(field);
        field.select();
        if (!document.execCommand("copy")) {
          throw new Error("copy unavailable");
        }
        field.remove();
      }
      dom.shareStatus.textContent = "현재 보기 링크를 복사했습니다.";
      dom.copyViewLink.textContent = "링크 복사됨";
      window.setTimeout(function () { dom.copyViewLink.textContent = "현재 보기 링크 복사"; }, 1800);
    } catch (error) {
      dom.shareStatus.textContent = "링크를 복사하지 못했습니다. 주소창의 주소를 복사해 주세요.";
    }
  }

  function renderAll() {
    renderAnalysisSummary();
    renderCoverage();
    renderTopicAnalysis();
    state.searchLimit = 50;
    renderQuestions();
    renderPractice();
    renderWeakTopics();
    renderGenerated();
  }

  function setSearchFormDisabled(disabled) {
    dom.searchForm.querySelectorAll("input,select,button").forEach(function (control) {
      control.disabled = disabled;
    });
  }

  function restoreFocusAfterRetry() {
    window.requestAnimationFrame(function () {
      var searchPanel = document.getElementById("search-panel");
      if (state.activeTab === "search" && searchPanel && !searchPanel.hidden && !dom.searchQuery.disabled) {
        dom.searchQuery.focus();
        return;
      }
      var activeTab = document.querySelector(".qb-tabs [role='tab'][aria-selected='true']");
      if (activeTab && !activeTab.hidden) {
        activeTab.focus();
      }
    });
  }

  function renderFatalState() {
    dom["qb-main"].setAttribute("aria-busy", "false");
    dom.datasetScope.textContent = "사용 불가";
    dom.datasetVersion.textContent = "-";
    dom.datasetGenerated.textContent = "-";
    dom.analysisSummary.replaceChildren();
    dom.weakSummary.replaceChildren();
    setEmpty(dom.coverageRows, "자료 범위를 표시할 수 없습니다.");
    setEmpty(dom.topicAnalysis, "출제분석 데이터를 표시할 수 없습니다.");
    setEmpty(dom.questionResults, "기출 근거를 표시할 수 없습니다.");
    setEmpty(dom.practiceCard, "연습 데이터를 표시할 수 없습니다.");
    setEmpty(dom.weakTopics, "학습 기록을 연결할 수 없습니다.");
    dom.searchResultCount.textContent = "데이터 오류";
    dom.practiceProgress.textContent = "데이터 오류";
    setSearchFormDisabled(true);
  }

  function switchTab(name, updateUrl, focusTab) {
    if (TAB_NAMES.indexOf(name) === -1) {
      name = "analysis";
    }
    var requestedTab = document.querySelector(".qb-tabs [data-tab='" + name + "']");
    if (!requestedTab || requestedTab.hidden) {
      name = "analysis";
    }
    state.activeTab = name;
    document.querySelectorAll(".qb-tabs [role='tab']").forEach(function (tab) {
      var active = tab.dataset.tab === name;
      tab.setAttribute("aria-selected", active ? "true" : "false");
      tab.tabIndex = active ? 0 : -1;
      var panel = document.getElementById(tab.getAttribute("aria-controls"));
      if (panel) {
        panel.hidden = !active;
      }
      if (active && focusTab) {
        tab.focus();
        tab.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "nearest", inline: "nearest" });
      }
    });
    if (name === "weak" && state.data) {
      renderWeakTopics();
    }
    if (updateUrl) {
      syncUrl("push");
      applyCapabilityNavigation();
    }
  }

  function bindTabs() {
    var tabs = Array.from(document.querySelectorAll(".qb-tabs [role='tab']"));
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        switchTab(tab.dataset.tab, true, false);
      });
      tab.addEventListener("keydown", function (event) {
        var visibleTabs = tabs.filter(function (item) { return !item.hidden; });
        var index = visibleTabs.indexOf(tab);
        var nextIndex = index;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") {
          nextIndex = (index + 1) % visibleTabs.length;
        } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
          nextIndex = (index - 1 + visibleTabs.length) % visibleTabs.length;
        } else if (event.key === "Home") {
          nextIndex = 0;
        } else if (event.key === "End") {
          nextIndex = visibleTabs.length - 1;
        } else {
          return;
        }
        event.preventDefault();
        switchTab(visibleTabs[nextIndex].dataset.tab, true, true);
      });
    });
    window.addEventListener("hashchange", function () {
      if (state.data) {
        applyStateFromUrl(true);
      } else {
        switchTab(requestedTabName(), false, false);
      }
    });
    window.addEventListener("popstate", function () {
      applyStateFromUrl(true);
    });
    switchTab(requestedTabName(), false, false);
  }

  function bindControls() {
    dom.analysisSection.addEventListener("change", function () {
      renderTopicAnalysis();
      syncUrl("push");
    });
    dom.analysisSort.addEventListener("change", function () {
      renderTopicAnalysis();
      syncUrl("push");
    });
    dom.searchQuery.addEventListener("input", function () {
      window.clearTimeout(state.searchTimer);
      state.searchTimer = window.setTimeout(function () {
        state.searchLimit = 50;
        renderQuestions();
        syncUrl("replace");
      }, SEARCH_DEBOUNCE_MS);
    });
    ["roundFilter", "sectionFilter", "topicFilter", "sourceFilter", "answerFilter", "contentFilter"].forEach(function (id) {
      dom[id].addEventListener("change", function () {
        state.searchLimit = 50;
        renderQuestions();
        syncUrl("push");
      });
    });
    dom.searchForm.addEventListener("submit", function (event) {
      event.preventDefault();
    });
    dom.searchForm.addEventListener("reset", function () {
      window.setTimeout(function () {
        state.analysisEvidenceOnly = false;
        state.searchLimit = 50;
        renderQuestions();
        syncUrl("push");
      }, 0);
    });
    dom.practiceTopic.addEventListener("change", function () {
      resetPracticeQueue(false);
    });
    dom.shufflePractice.addEventListener("click", function () {
      resetPracticeQueue(true);
    });
    dom.resetProgress.addEventListener("click", resetProgress);
    dom.toggleAllTopics.addEventListener("click", function () {
      state.showAllTopics = !state.showAllTopics;
      renderTopicAnalysis();
      syncUrl("push");
    });
    dom.copyViewLink.addEventListener("click", copyCurrentView);
  }

  bindTabs();
  bindControls();
  loadDataset();
}());
