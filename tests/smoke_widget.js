const assert = require('node:assert/strict');
const { chromium } = require('playwright');

async function textContent(page, selector) {
  const value = await page.textContent(selector);
  return value ? value.trim() : '';
}

async function run() {
  const browser = await chromium.launch({
    headless: true,
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined
  });
  const page = await browser.newPage();

  try {
    await page.goto('http://localhost:8080/example', { waitUntil: 'networkidle' });

    await page.waitForSelector('[data-testid="widget-root"]');
    await page.waitForSelector('[data-testid="widget-tab-table"]');

    const teams = await textContent(page, '[data-testid="widget-match-teams"]');
    assert.equal(teams, 'Arsenal vs Chelsea');

    const activeTable = await page.locator('.sr-tab-button.active').getAttribute('data-tab-id');
    assert.equal(activeTable, 'table');

    await page.getByTestId('widget-tab-fixtures').click();
    await page.waitForSelector('.sr-tab-panel[data-tab-id="fixtures"] .sr-fixture-row');
    const activeFixtures = await page.locator('.sr-tab-button.active').getAttribute('data-tab-id');
    assert.equal(activeFixtures, 'fixtures');

    await page.getByTestId('widget-tab-h2h').click();
    await page.waitForSelector('[data-testid="widget-h2h-home-player"]');
    const selectCount = await page.locator('.sr-h2h-selectors select').count();
    assert.equal(selectCount, 2);

    await page.getByTestId('example-phase-live').click();
    await page.waitForSelector('[data-testid="widget-tab-xg-race"]:visible');

    await page.getByTestId('widget-tab-xg-race').click();
    await page.waitForSelector('[data-testid="widget-xg-canvas"]');

    console.log('Widget smoke test passed.');
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
