import { expect, test } from "@playwright/test";

const QUESTION_PATH =
  "/study/courses/big-data-analysis-engineer-written/questions/";
const COURSE_PATH = "/study/courses/big-data-analysis-engineer-written/";
const COURSE_INDEX_GLOB = `**${COURSE_PATH}`;
const PUBLIC_DATA_PATH = `${QUESTION_PATH}data/questions.public.json`;

async function openPublicArchive(page, suffix = "") {
  await page.goto(`${QUESTION_PATH}${suffix}`);
  await expect(page.locator("#datasetScope")).toHaveText("공개 데이터");
  await expect(page.locator("#datasetVersion")).toHaveAttribute(
    "title",
    /^[0-9a-f]{64}$/,
  );
  await expect(page.locator("#datasetVersion")).toContainText("무결성 확인");
  await page.waitForLoadState("networkidle");
}

async function publicDataset(request) {
  const response = await request.get(PUBLIC_DATA_PATH);
  expect(response.ok()).toBeTruthy();
  return response.json();
}

test.describe("question archive browser contract", () => {
  test("loads the public archive without probing local-only data", async ({
    page,
  }) => {
    const requestedPaths = [];
    page.on("request", (request) =>
      requestedPaths.push(new URL(request.url()).pathname),
    );

    await openPublicArchive(page);

    await expect(page).toHaveTitle("빅데이터분석기사 필기 기출·출제분석");
    await expect(page.locator("html")).toHaveAttribute("lang", "ko");
    await expect(page.locator('meta[name="description"]')).toHaveAttribute(
      "content",
      /공개 기출 근거/,
    );
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
      "href",
      "https://stagnes307.github.io/study/courses/big-data-analysis-engineer-written/questions/",
    );
    await expect(page.locator('link[rel="icon"]')).toHaveAttribute(
      "href",
      "/study/assets/study-mark.svg",
    );
    const csp = await page
      .locator('meta[http-equiv="Content-Security-Policy"]')
      .getAttribute("content");
    expect(csp).toEqual(expect.stringContaining("default-src 'self'"));
    expect(csp).toEqual(expect.stringContaining("object-src 'none'"));
    expect(csp).toEqual(expect.stringContaining("connect-src 'self'"));
    await expect(page.locator("#appStatus")).toBeHidden();
    await expect(page.locator("#analysisSummary .qb-metric")).toHaveCount(4);
    await expect
      .poll(() => page.locator("#topicAnalysis .qb-topic-card").count())
      .toBeGreaterThan(0);
    expect(
      requestedPaths.some((path) => path.endsWith("questions.local.json")),
    ).toBeFalsy();
  });

  test("default analysis makes its limited scope and non-probability ordering explicit", async ({
    page,
    request,
  }) => {
    const data = await publicDataset(request);
    const expectedCodes = data.topics
      .filter((topic) => Number(topic.observed_questions) > 0)
      .sort(
        (left, right) =>
          Number(right.distinct_rounds) - Number(left.distinct_rounds) ||
          Number(right.source_count) - Number(left.source_count) ||
          Number(right.observed_questions) - Number(left.observed_questions) ||
          left.code.localeCompare(right.code, "ko", { numeric: true }),
      )
      .slice(0, 6)
      .map((topic) => topic.code);

    await openPublicArchive(page);

    const scope = page.locator("#analysisScope");
    await expect(scope).toContainText("2021년 제2·3회");
    await expect(scope).toContainText("시행 11회 중 9회 미수집");
    await expect(scope).toContainText("순위 참고 28건 · 제외 10건");
    await expect(scope).toContainText("출처 품질 기준 충족 0/2회");
    await expect(page.locator("#analysisSort")).toHaveValue("repeat");
    await expect(page.locator("#topicSortHint")).toContainText(
      /출제 확률이나 중요도 순위는 아닙니다/,
    );
    await expect(page.locator("#questionResults .qb-question-card")).toHaveCount(
      0,
    );
    const renderedCodes = await page
      .locator("#topicAnalysis .qb-topic-card .qb-code")
      .allTextContents();
    expect(renderedCodes).toEqual(expectedCodes);
  });

  test("archive records explain analysis inclusion and exclusion", async ({
    page,
  }) => {
    await openPublicArchive(page, "#search");

    await expect(page.locator("#searchResultCount")).toContainText(
      "관측 기록 38건 · 순위 참고 28건 · 제외 10건",
    );
    await expect(
      page.locator('.qb-badge[data-kind="analysis"]'),
    ).toHaveCount(28);
    await expect(
      page.locator('.qb-badge[data-kind="excluded"]'),
    ).toHaveCount(10);
    await expect(page.locator(".qb-analysis-exclusion")).toHaveCount(10);

    await page.locator("#eligibilityFilter").selectOption("excluded");
    await expect(page.locator("#searchResultCount")).toHaveText(
      "분석 제외 기록 10건",
    );
    await expect(page.locator("#questionResults .qb-question-card")).toHaveCount(
      10,
    );
    expect(new URL(page.url()).searchParams.get("eligibility")).toBe("excluded");
  });

  test("public export is fail-closed for restricted content and unsafe links", async ({
    request,
  }) => {
    const data = await publicDataset(request);

    expect(data.privacy).toEqual({
      scope: "public",
      contains_private_content: false,
    });
    expect(data.questions.length).toBeGreaterThan(0);
    for (const question of data.questions) {
      expect(["public_fulltext", "link_only"]).toContain(
        question.rights_status,
      );
      if (question.question_text) {
        expect(question.rights_status).toBe("public_fulltext");
      }
      for (const source of question.source_links || []) {
        expect(["public_fulltext", "link_only"]).toContain(
          source.rights_status,
        );
        expect(source.url).toMatch(/^https?:\/\//);
      }
    }
  });

  test("topic URL opens a filtered, shareable search view", async ({
    page,
    request,
  }) => {
    const data = await publicDataset(request);
    const topic = data.topics.find(
      (item) => Number(item.observed_questions) > 0,
    );
    expect(topic).toBeTruthy();

    await page.goto(`${QUESTION_PATH}?topic=${encodeURIComponent(topic.code)}`);

    await expect(page.locator("#datasetScope")).toHaveText("공개 데이터");
    await expect(page.locator("#search-tab")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.locator("#topicFilter")).toHaveValue(topic.code);
    await expect
      .poll(() => page.locator("#questionResults .qb-question-card").count())
      .toBeGreaterThan(0);
  });

  test("topic analysis drill-down matches its analysis-eligible evidence count", async ({
    page,
    request,
  }) => {
    const data = await publicDataset(request);
    const topic = data.topics.find((item) => item.code === "4-1-1-1");
    expect(topic).toBeTruthy();
    expect(Number(topic.observed_questions)).toBe(4);
    const eligibleIds = data.questions
      .filter(
        (question) =>
          question.analysis_eligible === true &&
          question.primary_topic_code === topic.code,
      )
      .map((question) => question.appearance_id || question.question_id)
      .sort();
    expect(eligibleIds).toHaveLength(4);
    expect(
      data.questions.filter(
        (question) =>
          question.analysis_eligible !== true &&
          question.primary_topic_code === topic.code,
      ).length,
    ).toBeGreaterThan(0);

    await openPublicArchive(page);
    const topicCard = page.locator("#topicAnalysis .qb-topic-card").filter({
      has: page.locator(".qb-code", { hasText: /^4-1-1-1$/ }),
    });
    await expect(topicCard).toHaveCount(1);
    await topicCard
      .getByRole("button", { name: "분석 포함 근거 4건 보기" })
      .click();

    await expect(page.locator("#search-tab")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.locator("#topicFilter")).toHaveValue(topic.code);
    await expect(page.locator("#searchResultCount")).toHaveText(
      "분석 포함 기록 4건",
    );
    await expect(page.locator("#questionResults .qb-question-card")).toHaveCount(
      4,
    );
    await expect
      .poll(() => new URL(page.url()).searchParams.get("eligibility"))
      .toBe("analysis");
    expect(new URL(page.url()).hash).toBe("#search");
    const renderedIds = await page
      .locator("#questionResults .qb-question-card")
      .evaluateAll((nodes) => nodes.map((node) => node.dataset.recordId).sort());
    expect(renderedIds).toEqual(eligibleIds);

    await page.reload();
    await expect(page.locator("#datasetScope")).toHaveText("공개 데이터");
    await expect(page.locator("#searchResultCount")).toHaveText(
      "분석 포함 기록 4건",
    );
    await expect(page.locator("#questionResults .qb-question-card")).toHaveCount(
      4,
    );
  });

  test("explicit lesson links need no discovery fetch and preserve keyboard focus", async ({
    page,
  }) => {
    let courseFetches = 0;
    page.on("request", (request) => {
      if (
        request.resourceType() === "fetch" &&
        new URL(request.url()).pathname === COURSE_PATH
      ) {
        courseFetches += 1;
      }
    });

    await page.goto(QUESTION_PATH);
    await expect(page.locator("#datasetScope")).toHaveText("공개 데이터");
    const firstTopicCard = page.locator("#topicAnalysis .qb-topic-card").first();
    const firstAnalysisCta = firstTopicCard.getByRole("button", {
      name: /분석 포함 근거 \d+건 보기/,
    });
    await expect(firstAnalysisCta).toBeVisible();
    await firstAnalysisCta.focus();
    await expect(firstAnalysisCta).toBeFocused();

    await page.waitForLoadState("networkidle");
    expect(courseFetches).toBe(0);
    await expect(firstTopicCard.locator(".qb-lesson-link")).toBeVisible({
      timeout: 10_000,
    });
    await expect(firstAnalysisCta).toBeFocused();

    await page.keyboard.press("Enter");
    await expect(page.locator("#search-tab")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.locator("#searchResultCount")).toContainText(
      /분석 포함 기록 [1-9]\d*건/,
    );
  });

  test("lesson CTAs survive a failed course-index lookup and open a valid destination", async ({
    page,
  }) => {
    await page.route(COURSE_INDEX_GLOB, async (route) => {
      if (route.request().resourceType() === "fetch") {
        await route.abort("failed");
      } else {
        await route.continue();
      }
    });

    await page.goto(QUESTION_PATH);
    await expect(page.locator("#datasetScope")).toHaveText("공개 데이터");
    await page.waitForLoadState("networkidle");
    const topicCards = page.locator("#topicAnalysis .qb-topic-card");
    const visibleTopicCount = await topicCards.count();
    expect(visibleTopicCount).toBeGreaterThan(0);
    await expect(topicCards.locator(".qb-lesson-link")).toHaveCount(
      visibleTopicCount,
    );

    const firstTopicCard = topicCards.first();
    const topicCode = (await firstTopicCard.locator(".qb-code").innerText()).trim();
    const lessonCta = firstTopicCard.locator(".qb-lesson-link");
    const href = await lessonCta.getAttribute("href");
    expect(href).toBeTruthy();
    const destination = new URL(href, page.url());
    const exactLessonPrefix = `${COURSE_PATH}lessons/${topicCode}-`;
    const isExactLesson = destination.pathname.startsWith(exactLessonPrefix);
    const isExplicitFallback = destination.pathname === COURSE_PATH;
    expect(isExactLesson || isExplicitFallback).toBeTruthy();
    if (isExplicitFallback) {
      await expect(lessonCta).toHaveAccessibleName(/과정|목차|찾기/);
    }

    const destinationResponse = await page.request.get(destination.href);
    expect(destinationResponse.ok()).toBeTruthy();
    await lessonCta.click();
    await expect
      .poll(() => new URL(page.url()).pathname)
      .toBe(destination.pathname);
  });

  test("observed topics progressively reveal 6 to 20 with URL and focus persistence", async ({
    page,
    request,
  }) => {
    const data = await publicDataset(request);
    const observedTopicCount = data.topics.filter(
      (topic) => Number(topic.observed_questions) > 0,
    ).length;
    expect(observedTopicCount).toBe(20);

    await openPublicArchive(page);
    const initialUrl = page.url();
    const topicCards = page.locator("#topicAnalysis .qb-topic-card");
    await expect(topicCards).toHaveCount(6);
    const revealTopics = page.locator("#toggleObservedTopics");
    await expect(revealTopics).toHaveAccessibleName(/관측 토픽.*보기/);
    await revealTopics.focus();
    await page.keyboard.press("Enter");

    await expect(topicCards).toHaveCount(observedTopicCount);
    await expect(revealTopics).toBeFocused();
    const expandedUrl = page.url();
    expect(expandedUrl).not.toBe(initialUrl);

    await page.reload();
    await expect(page.locator("#datasetScope")).toHaveText("공개 데이터");
    await expect(topicCards).toHaveCount(observedTopicCount);
    expect(page.url()).toBe(expandedUrl);

    await page.goBack();
    await expect(page.locator("#datasetScope")).toHaveText("공개 데이터");
    await expect(topicCards).toHaveCount(6);
    expect(page.url()).toBe(initialUrl);
  });

  test("search and round filters update and reset without navigation", async ({
    page,
    request,
  }) => {
    const data = await publicDataset(request);
    const searchableQuestion = data.questions.find(
      (question) =>
        (question.keywords || []).some(Boolean) && question.exam_round,
    );
    expect(searchableQuestion).toBeTruthy();
    const keyword = searchableQuestion.keywords.find(Boolean);
    await openPublicArchive(page, "#search");

    await page.locator("#searchQuery").fill(keyword);
    await expect
      .poll(() => page.locator("#questionResults .qb-question-card").count())
      .toBeGreaterThan(0);

    await page
      .locator("#roundFilter")
      .selectOption(String(searchableQuestion.exam_round));
    await expect
      .poll(() => page.locator("#questionResults .qb-question-card").count())
      .toBeGreaterThan(0);

    await page.getByRole("button", { name: "조건 초기화" }).click();
    await expect(page.locator("#searchQuery")).toHaveValue("");
    await expect(page.locator("#roundFilter")).toHaveValue("");
  });

  test("tab keyboard navigation follows the ARIA tabs pattern", async ({
    page,
  }) => {
    await openPublicArchive(page);
    const tabs = page.locator(".qb-tabs [role='tab']:visible");
    await expect.poll(() => tabs.count()).toBeGreaterThanOrEqual(2);
    const first = tabs.first();
    const second = tabs.nth(1);
    const last = tabs.last();

    await first.focus();
    await page.keyboard.press("ArrowRight");
    await expect(second).toBeFocused();
    await expect(second).toHaveAttribute("aria-selected", "true");
    await page.keyboard.press("End");
    await expect(last).toBeFocused();
    await page.keyboard.press("Home");
    await expect(first).toBeFocused();
  });

  test("local scope never probes private web data and safely uses the public export", async ({
    page,
  }, testInfo) => {
    const configuredOrigin = new URL(String(testInfo.project.use.baseURL));
    const localhostOrigin = new URL(configuredOrigin);
    localhostOrigin.hostname = "localhost";

    for (const origin of new Set([
      configuredOrigin.origin,
      localhostOrigin.origin,
    ])) {
      const requests = [];
      const recordRequest = (request) => requests.push(new URL(request.url()));
      page.on("request", recordRequest);

      await page.goto(new URL(`${QUESTION_PATH}?scope=local`, origin).href);
      await expect(page.locator("#datasetScope")).toHaveText("공개 데이터");
      await expect(page.locator("#appStatus")).toContainText(/로컬|공개/);
      await page.waitForLoadState("networkidle");

      expect(
        requests.some(({ pathname }) => pathname.endsWith("questions.local.json")),
      ).toBeFalsy();
      expect(
        requests.some(({ pathname }) => pathname === PUBLIC_DATA_PATH),
      ).toBeTruthy();

      page.off("request", recordRequest);
    }
  });

  test("dataset failure is recoverable through the visible retry control", async ({
    page,
  }) => {
    let failRequest = true;
    await page.route("**/questions.public.json", async (route) => {
      if (failRequest) {
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: "{}",
        });
      } else {
        await route.continue();
      }
    });

    await page.goto(`${QUESTION_PATH}#search`);
    await expect(page.locator("#appStatus")).toContainText(
      /안전하게 확인하지 못했습니다|불러오지 못했습니다/,
    );
    await expect(page.getByRole("button", { name: "다시 시도" })).toBeVisible();

    failRequest = false;
    await page.getByRole("button", { name: "다시 시도" }).click();
    await expect(page.locator("#datasetScope")).toHaveText("공개 데이터");
    await expect(page.locator("#appStatus")).toBeHidden();
    await expect(page.locator("#searchQuery")).toBeEnabled();
    await expect(page.locator("#roundFilter")).toBeEnabled();
    await expect(page.locator("#sectionFilter")).toBeEnabled();
    await expect(page.locator("#topicFilter")).toBeEnabled();
    await expect(
      page.getByRole("button", { name: "조건 초기화" }),
    ).toBeEnabled();
    await expect(page.locator("#searchQuery")).toBeFocused();
    await page.locator("#searchQuery").fill("평가");
    await expect(page.locator("#searchResultCount")).toContainText(/기록 [1-9]/);
  });

  test("source links remain safe when rendered", async ({ page }) => {
    await openPublicArchive(page, "#search");
    const links = page.locator(".qb-source-link");
    await expect.poll(() => links.count()).toBeGreaterThan(0);
    const attributes = await links.evaluateAll((nodes) =>
      nodes.map((node) => ({
        href: node.href,
        rel: node.rel,
        target: node.target,
      })),
    );
    for (const link of attributes) {
      expect(link.href).toMatch(/^https?:\/\//);
      expect(link.rel.split(/\s+/)).toEqual(
        expect.arrayContaining(["noopener", "noreferrer"]),
      );
      expect(link.target).toBe("_blank");
    }
  });

  test("mobile layout does not overflow the viewport", async ({
    page,
  }, testInfo) => {
    test.skip(
      !testInfo.project.name.includes("mobile"),
      "mobile viewport assertion",
    );
    await openPublicArchive(page);

    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport + 1);
    await expect(page.locator("#analysis-tab")).toBeVisible();
  });
});
