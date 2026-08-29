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
  var TAB_NAMES = ["analysis", "search", "practice", "weak"];
  var STORAGE_PREFIX = "study.question-bank.progress.v1:";
  var MAX_STORED_ATTEMPTS = 2500;

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
    storageAvailable: true
  };

  var elementIds = [
    "appStatus", "datasetScope", "datasetVersion", "datasetGenerated",
    "analysisSummary", "analysisNotice", "analysisSection", "analysisSort",
    "topicAnalysis", "searchForm", "searchQuery", "roundFilter", "sectionFilter",
    "topicFilter", "sourceFilter", "answerFilter", "contentFilter", "searchResultCount", "questionResults",
    "practiceTopic", "shufflePractice", "practiceProgress", "practiceCard",
    "weakSummary", "progressDatasetNote", "resetProgress", "weakTopics"
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
    if (round && year && round.indexOf(year) === -1) {
      return year + " · " + round;
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
    dom.appStatus.hidden = false;
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
      retry.addEventListener("click", loadDataset);
      nodes.push(retry);
    }
    dom.appStatus.replaceChildren.apply(dom.appStatus, nodes);
  }

  function hideStatus() {
    dom.appStatus.hidden = true;
    dom.appStatus.replaceChildren();
  }

  function validateDataset(data) {
    if (!data || typeof data !== "object") {
      throw new Error("데이터셋이 JSON 객체가 아닙니다.");
    }
    if (!Array.isArray(data.topics) || !Array.isArray(data.questions)) {
      throw new Error("topics 또는 questions 배열이 없습니다.");
    }
    return data;
  }

  async function fetchDataset(path) {
    var response = await fetch(path, { cache: "no-store", credentials: "same-origin" });
    if (!response.ok) {
      throw new Error(path + " (" + response.status + ")");
    }
    return validateDataset(await response.json());
  }

  async function loadDataset() {
    setStatus("loading", "기출 데이터를 불러오는 중입니다.", false);
    state.requestedLocal = new URLSearchParams(window.location.search).get("scope") === "local";
    var data;
    var fallback = false;
    try {
      if (state.requestedLocal) {
        try {
          data = await fetchDataset("./data/questions.local.json");
          state.loadedScope = "local";
        } catch (localError) {
          data = await fetchDataset("./data/questions.public.json");
          state.loadedScope = "public";
          fallback = true;
        }
      } else {
        data = await fetchDataset("./data/questions.public.json");
        state.loadedScope = "public";
      }
      prepareDataset(data);
      populateFilters();
      applyInitialTopicFilter();
      loadProgress();
      renderAll();
      if (fallback) {
        setStatus("warning", "로컬 데이터가 없거나 유효하지 않아 공개 데이터로 안전하게 전환했습니다.", false);
      } else {
        hideStatus();
      }
    } catch (error) {
      console.error(error);
      renderFatalState();
      setStatus("error", "기출 데이터를 불러오지 못했습니다. 배포된 JSON 파일과 형식을 확인해 주세요.", true);
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
    state.questions.forEach(function (question) {
      var id = storageQuestionId(question);
      if (id) {
        state.questionByStorageId.set(id, question);
        state.questionHashes.set(id, questionHash(question));
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
    dom.datasetScope.textContent = state.loadedScope === "local" ? "로컬 전체" : "공개 데이터";
    dom.datasetVersion.textContent = asText(data.dataset_version, "-");
    dom.datasetGenerated.textContent = formatDate(data.generated_at);
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

    var contentModes = Array.from(new Set(state.questions.map(function (question) {
      return asText(question.content_mode, "");
    }).filter(Boolean))).sort();
    setOptions(dom.contentFilter, "전체 상태", contentModes.map(function (mode) {
      return { value: mode, label: contentLabel(mode) };
    }));

    setOptions(dom.sourceFilter, "전체 출처", sourceFilterEntries());

    var eligibleCodes = new Set();
    getEligibleQuestions().forEach(function (question) {
      questionTopicCodes(question).forEach(function (code) {
        eligibleCodes.add(code);
      });
    });
    setOptions(dom.practiceTopic, "전체 토픽", topicEntries.filter(function (entry) {
      return eligibleCodes.has(String(entry.value));
    }));
    resetPracticeQueue(false);
  }

  function applyInitialTopicFilter() {
    var requestedTopic = new URLSearchParams(window.location.search).get("topic");
    if (!requestedTopic || !state.topicByCode.has(requestedTopic)) {
      return;
    }
    dom.topicFilter.value = requestedTopic;
    state.searchLimit = 50;
    switchTab("search", true, false);
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
    var roundNote = eligibleRounds === null ? "현재 데이터 기준" : "빈도 분모 적격 " + formatNumber(eligibleRounds) + "개";
    dom.analysisSummary.replaceChildren(
      createMetric("관측 문항", formatNumber(summaryNumber(["observed_questions", "observed_appearances", "total_questions", "question_count"], state.questions.length)), "중복 appearance 포함"),
      createMetric("관측 회차", formatNumber(summaryNumber(["distinct_rounds", "round_count"], distinctRounds)), roundNote),
      createMetric("관측 토픽", formatNumber(summaryNumber(["observed_topics", "topic_count"], observedTopics)), "전체 " + formatNumber(state.topics.length) + "개 토픽"),
      createMetric("공개 원문", formatNumber(summaryNumber(["public_question_count", "public_questions", "public_fulltext_questions"], publicQuestions)), "연습 가능 " + formatNumber(eligibleQuestions) + "개")
    );

    var summary = state.data.summary;
    var note = "";
    if (summary && typeof summary === "object") {
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
      return !section || String(topic.section_id) === section;
    });
    topics.sort(function (left, right) {
      if (sortMode === "frequency") {
        return numberOr(right.observed_questions, 0) - numberOr(left.observed_questions, 0) ||
          compareCodes(left.code, right.code);
      }
      if (sortMode === "code") {
        return compareCodes(left.code, right.code);
      }
      return numberOr(right.importance_score, -1) - numberOr(left.importance_score, -1) ||
        numberOr(right.observed_questions, 0) - numberOr(left.observed_questions, 0) ||
        compareCodes(left.code, right.code);
    });
    if (!topics.length) {
      setEmpty(dom.topicAnalysis, state.topics.length ? "선택한 과목에 해당하는 토픽이 없습니다." : "아직 분류된 기출 토픽이 없습니다.");
      return;
    }
    var cards = topics.map(function (topic) {
      var evidence = normalEvidence(topic.evidence_level);
      var score = numberOrNull(topic.importance_score);
      var card = make("article", "qb-topic-card");
      card.dataset.evidence = evidence;
      var top = make("div", "qb-topic-top");
      top.append(make("span", "qb-code", asText(topic.code, "-")));
      var evidenceBadge = make("span", "qb-evidence", EVIDENCE_LABELS[evidence]);
      evidenceBadge.dataset.level = evidence;
      top.append(evidenceBadge);
      card.append(top);
      card.append(make("h3", "", asText(topic.title, topic.code)));
      card.append(make("p", "qb-topic-section",
        asText(topic.section_id, "") + (topic.section_title ? ". " + asText(topic.section_title, "") : "")));

      var scoreRow = make("div", "qb-score-row");
      var track = make("span", "qb-score-track");
      var fill = make("i");
      fill.style.setProperty("--value", String(score === null ? 0 : clamp(score, 0, 100)));
      track.append(fill);
      scoreRow.append(track);
      scoreRow.append(make("span", "qb-score", score === null ? "산정 전" : Math.round(score) + "점"));
      card.append(scoreRow);
      var stars = make("p", "qb-stars", starText(topic));
      stars.setAttribute("aria-label", "중요도 " + starText(topic));
      card.append(stars);

      var stats = make("div", "qb-topic-stats");
      [
        [topic.observed_questions, "관측 문항"],
        [topic.distinct_rounds, "출제 회차"],
        [topic.public_question_count, "공개 원문"]
      ].forEach(function (item) {
        var stat = make("div");
        stat.append(make("strong", "", formatNumber(item[0])));
        stat.append(make("span", "", item[1]));
        stats.append(stat);
      });
      card.append(stats);
      var action = make("button", "qb-topic-action", "관련 문제 보기");
      action.type = "button";
      action.addEventListener("click", function () {
        dom.topicFilter.value = String(topic.code);
        state.searchLimit = 50;
        renderQuestions();
        switchTab("search", true, true);
      });
      card.append(action);
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
      return (!query || searchableText(question).indexOf(query) !== -1) &&
        (!round || roundValue(question) === round) &&
        questionMatchesSection(question, section) &&
        (!topic || questionTopicCodes(question).indexOf(topic) !== -1) &&
        questionMatchesSource(question, source) &&
        (!answer || asText(question.answer_status, "") === answer) &&
        (!content || asText(question.content_mode, "") === content);
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
      return href ? { href: href, label: label } : null;
    }).filter(Boolean);
    if (!validLinks.length) {
      return;
    }
    var container = make("div", "qb-source-list");
    validLinks.forEach(function (source) {
      var link = make("a", "qb-source-link", source.label);
      link.href = source.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      container.append(link);
    });
    card.append(container);
  }

  function createQuestionCard(question) {
    var card = make("article", "qb-question-card");
    var metadata = make("div", "qb-question-meta");
    metadata.append(badge(roundLabel(question), "muted"));
    var primaryCode = asText(question.primary_topic_code, "");
    if (primaryCode) {
      metadata.append(badge(primaryCode + ". " + topicTitle(primaryCode), "muted"));
    }
    var answerStatus = asText(question.answer_status, "unverified");
    metadata.append(badge(answerLabel(answerStatus), answerBadgeKind(answerStatus)));
    var mode = asText(question.content_mode, "link_only");
    metadata.append(badge(questionContentLabel(question), mode === "public_fulltext" || mode === "full" ? "verified" : "muted"));
    var id = storageQuestionId(question);
    if (id) {
      metadata.append(make("span", "qb-question-id", id));
    }
    card.append(metadata);

    var questionText = asText(question.question_text, "");
    if (questionText) {
      card.append(make("h3", "", questionText));
      var choices = renderChoices(question);
      if (choices) {
        card.append(choices);
      }
    } else {
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
    appendSourceLinks(card, question.source_links);
    return card;
  }

  function renderQuestions() {
    var questions = filteredQuestions();
    var shown = questions.slice(0, state.searchLimit);
    dom.searchResultCount.textContent = questions.length > shown.length ?
      formatNumber(questions.length) + "개 중 " + formatNumber(shown.length) + "개 표시" :
      formatNumber(questions.length) + "개 문제";
    if (!questions.length) {
      setEmpty(dom.questionResults, state.questions.length ? "검색 조건에 맞는 문제가 없습니다." : "공개 가능한 문제 데이터가 아직 없습니다.");
      return;
    }
    var nodes = shown.map(createQuestionCard);
    if (questions.length > shown.length) {
      var more = make("button", "qb-button qb-button-secondary", "문제 더 보기");
      more.type = "button";
      more.addEventListener("click", function () {
        state.searchLimit += 50;
        renderQuestions();
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
      setEmpty(dom.practiceCard, state.questions.some(function (question) {
        return question.practice_eligible === true;
      }) ? "연습 가능 표시가 있지만 정답 또는 선택지 형식을 확인할 수 없습니다." : "현재 범위에는 연습 가능한 문제가 없습니다.");
      dom.shufflePractice.disabled = true;
      return;
    }
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
    form.append(make("h3", "", asText(question.question_text, "")));

    var fieldset = make("fieldset", "qb-practice-options");
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
  }

  function moveToNextPractice() {
    state.practiceIndex = state.practiceIndex >= state.practiceQueue.length - 1 ? 0 : state.practiceIndex + 1;
    renderPractice();
    dom.practiceCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
      var heading = make("div");
      heading.append(make("h3", "", group.code === "unclassified" ? "미분류 토픽" : group.code + ". " + topicTitle(group.code)));
      heading.append(make("p", "", group.correct + "개 정답 / " + group.attempts + "회 풀이"));
      card.append(heading);
      var status = make("span", "qb-weak-status", group.statusLabel);
      status.dataset.status = group.status;
      card.append(status);
      var accuracy = make("div", "qb-accuracy");
      var track = make("span", "qb-accuracy-track");
      var fill = make("i");
      fill.style.setProperty("--value", String(clamp(group.accuracy, 0, 100)));
      track.append(fill);
      accuracy.append(track);
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

  function renderAll() {
    renderAnalysisSummary();
    renderTopicAnalysis();
    state.searchLimit = 50;
    renderQuestions();
    renderPractice();
    renderWeakTopics();
  }

  function renderFatalState() {
    dom.datasetScope.textContent = "사용 불가";
    dom.datasetVersion.textContent = "-";
    dom.datasetGenerated.textContent = "-";
    dom.analysisSummary.replaceChildren();
    dom.weakSummary.replaceChildren();
    setEmpty(dom.topicAnalysis, "출제분석 데이터를 표시할 수 없습니다.");
    setEmpty(dom.questionResults, "문제 데이터를 표시할 수 없습니다.");
    setEmpty(dom.practiceCard, "연습 데이터를 표시할 수 없습니다.");
    setEmpty(dom.weakTopics, "학습 기록을 연결할 수 없습니다.");
    dom.searchResultCount.textContent = "데이터 오류";
    dom.practiceProgress.textContent = "데이터 오류";
  }

  function switchTab(name, updateHash, focusTab) {
    if (TAB_NAMES.indexOf(name) === -1) {
      name = "analysis";
    }
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
      }
    });
    if (name === "weak" && state.data) {
      renderWeakTopics();
    }
    if (updateHash && window.location.hash !== "#" + name) {
      window.history.replaceState(null, "", window.location.pathname + window.location.search + "#" + name);
    }
  }

  function bindTabs() {
    var tabs = Array.from(document.querySelectorAll(".qb-tabs [role='tab']"));
    tabs.forEach(function (tab, index) {
      tab.addEventListener("click", function () {
        switchTab(tab.dataset.tab, true, false);
      });
      tab.addEventListener("keydown", function (event) {
        var nextIndex = index;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") {
          nextIndex = (index + 1) % tabs.length;
        } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
          nextIndex = (index - 1 + tabs.length) % tabs.length;
        } else if (event.key === "Home") {
          nextIndex = 0;
        } else if (event.key === "End") {
          nextIndex = tabs.length - 1;
        } else {
          return;
        }
        event.preventDefault();
        switchTab(tabs[nextIndex].dataset.tab, true, true);
      });
    });
    window.addEventListener("hashchange", function () {
      switchTab(window.location.hash.slice(1), false, false);
    });
    switchTab(window.location.hash.slice(1) || "analysis", false, false);
  }

  function bindControls() {
    dom.analysisSection.addEventListener("change", renderTopicAnalysis);
    dom.analysisSort.addEventListener("change", renderTopicAnalysis);
    ["searchQuery", "roundFilter", "sectionFilter", "topicFilter", "sourceFilter", "answerFilter", "contentFilter"].forEach(function (id) {
      dom[id].addEventListener(id === "searchQuery" ? "input" : "change", function () {
        state.searchLimit = 50;
        renderQuestions();
      });
    });
    dom.searchForm.addEventListener("submit", function (event) {
      event.preventDefault();
    });
    dom.searchForm.addEventListener("reset", function () {
      window.setTimeout(function () {
        state.searchLimit = 50;
        renderQuestions();
      }, 0);
    });
    dom.practiceTopic.addEventListener("change", function () {
      resetPracticeQueue(false);
    });
    dom.shufflePractice.addEventListener("click", function () {
      resetPracticeQueue(true);
    });
    dom.resetProgress.addEventListener("click", resetProgress);
  }

  bindTabs();
  bindControls();
  loadDataset();
}());
