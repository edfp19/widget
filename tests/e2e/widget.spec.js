const { test, expect } = require('@playwright/test');

test.describe('Widget prototype verification', () => {
  test('example page renders tabs, phase transitions, and interactive widgets', async ({ page }) => {
    await page.goto('/example', { waitUntil: 'networkidle' });

    await expect(page.getByTestId('widget-boot-error')).toHaveCount(0);
    await expect(page.getByTestId('widget-root')).toBeVisible();
    await expect(page.getByTestId('widget-match-teams')).toHaveText('Arsenal vs Chelsea');
    await expect(page.getByTestId('widget-tab-table')).toHaveClass(/active/);
    await expect(page.getByTestId('widget-tab-xg-race')).toBeHidden();

    await page.getByTestId('widget-tab-fixtures').click();
    await expect(page.getByTestId('widget-panel-fixtures')).toBeVisible();
    await expect(page.locator('.sr-fixture-row').first()).toBeVisible();

    await page.getByTestId('widget-tab-squads').click();
    await expect(page.getByTestId('widget-panel-squads')).toHaveAttribute('data-view-state', 'pre-match-squad');

    await page.getByTestId('example-phase-lineups').click();
    await expect(page.getByTestId('widget-panel-squads')).toHaveAttribute('data-view-state', 'confirmed-lineups');
    await expect(page.getByTestId('widget-squads-confirmed-pitch')).toBeVisible();

    await page.getByTestId('widget-tab-team-stats').click();
    await page.getByTestId('widget-team-stats-split').selectOption('last_10');
    await expect(page.locator('.sr-stats-list')).toContainText('2.2');

    await page.getByTestId('widget-tab-h2h').click();
    await page.getByTestId('widget-h2h-view-players').click();
    await page.getByTestId('widget-h2h-home-player').selectOption('p_09');
    await page.getByTestId('widget-h2h-away-player').selectOption('p_28');
    await expect(page.getByTestId('widget-h2h-player-comparison')).toContainText('Bukayo Saka');
    await expect(page.getByTestId('widget-h2h-player-comparison')).toContainText('Cole Palmer');

    await page.getByTestId('example-phase-live').click();
    await expect(page.getByTestId('widget-tab-xg-race')).toBeVisible();
    await expect(page.getByTestId('widget-tab-h2h')).toBeHidden();

    await page.getByTestId('widget-tab-squads').click();
    await expect(page.getByTestId('widget-panel-squads')).toHaveAttribute('data-view-state', 'live-formation');
    await expect(page.getByTestId('widget-squads-live-pitch')).toBeVisible();

    await page.getByTestId('widget-tab-xg-race').click();
    await expect(page.getByTestId('widget-xg-canvas')).toBeVisible();

    await page.getByTestId('widget-tab-facts').click();
    await page.getByTestId('widget-facts-filter-live').click();
    await expect(page.getByTestId('widget-facts-list')).toContainText('GOAL');
  });

  test('configurator updates preview, embed output, and css output', async ({ page }) => {
    await page.goto('/config', { waitUntil: 'networkidle' });

    await expect(page.getByTestId('widget-boot-error')).toHaveCount(0);
    await expect(page.locator('#preview-mount [data-testid="widget-root"]')).toBeVisible();
    await expect(page.getByTestId('config-page-type-state')).toHaveText('Match Preview');

    const embedOutput = page.getByTestId('config-embed-output');
    const cssOutput = page.getByTestId('config-css-output');

    await expect(embedOutput).toContainText('data-page-type="match"');
    await expect(embedOutput).toContainText('data-default-tab="table"');
    await expect(embedOutput).toContainText('data-visible-tabs="table,fixtures,squads,team-stats,h2h,facts,xg-race"');

    await page.getByTestId('config-tab-move-up-facts').click();
    await expect(embedOutput).toContainText('data-visible-tabs="table,fixtures,squads,team-stats,facts,h2h,xg-race"');

    await page.getByTestId('config-default-tab-select').selectOption('fixtures');
    await expect(embedOutput).toContainText('data-default-tab="fixtures"');

    await page.getByTestId('config-theme-toggle').click();
    await expect(page.getByTestId('config-theme-state')).toHaveText('Dark Mode');
    await expect(embedOutput).toContainText('data-theme="dark"');
    await expect(cssOutput).toContainText('.sr-widget-root[data-theme="dark"]');

    await page.getByTestId('config-page-type-select').selectOption('competition');
    await expect(page.getByTestId('config-page-type-state')).toHaveText('Competition Preview');
    await expect(embedOutput).toContainText('data-page-type="competition"');
    await expect(embedOutput).toContainText('data-competition-id="{{page.competition_id}}"');
    await expect(page.locator('#preview-mount [data-testid="widget-root"]')).toBeVisible();
  });
});
