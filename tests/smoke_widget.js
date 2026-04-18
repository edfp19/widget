const assert = require('node:assert/strict');
const { chromium } = require('playwright');

async function textContent(page, selector) {
  const value = await page.textContent(selector);
  return value ? value.trim() : '';
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    await page.goto('http://localhost:8080/example', { waitUntil: 'networkidle' });

    await page.waitForSelector('.sr-widget-root');
    await page.waitForSelector('.sr-tab-button[data-tab-id="table"]');

    const teams = await textContent(page, '.sr-teams');
    assert.equal(teams, 'Arsenal vs Chelsea');

    const activeTable = await page.locator('.sr-tab-button.active').getAttribute('data-tab-id');
    assert.equal(activeTable, 'table');

    await page.click('.sr-tab-button[data-tab-id="fixtures"]');
    await page.waitForSelector('.sr-tab-panel[data-tab-id="fixtures"] .sr-fixture-row');
    const activeFixtures = await page.locator('.sr-tab-button.active').getAttribute('data-tab-id');
    assert.equal(activeFixtures, 'fixtures');

    await page.click('.sr-tab-button[data-tab-id="h2h"]');
    await page.waitForSelector('.sr-h2h-selectors select');
    const selectCount = await page.locator('.sr-h2h-selectors select').count();
    assert.equal(selectCount, 2);

    await page.click('button[data-phase="LIVE"]');
    await page.waitForSelector('.sr-tab-button[data-tab-id="xg-race"]:visible');

    await page.click('.sr-tab-button[data-tab-id="xg-race"]');
    await page.waitForSelector('.sr-xg-canvas');

    console.log('Widget smoke test passed.');
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
