import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const QUESTION_PATH =
  "/study/courses/big-data-analysis-engineer-written/questions/";

for (const location of ["", "#search", "#practice", "#weak", "#generated"]) {
  test(`has no automatically detectable accessibility violations at ${location || "analysis"}`, async ({
    page,
  }) => {
    await page.goto(`${QUESTION_PATH}${location}`);
    await expect(page.locator("#datasetScope")).toHaveText("공개 데이터");

    const results = await new AxeBuilder({ page }).analyze();

    expect(
      results.violations,
      JSON.stringify(results.violations, null, 2),
    ).toEqual([]);
  });
}
