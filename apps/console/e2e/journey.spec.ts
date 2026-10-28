/**
 * The operator journey, through a real browser against the real console.
 *
 * This is the claim the project makes, executed rather than described: a
 * baseline that reports nothing, a path that closes on an ordinary read, a
 * containment chosen from pre-authorised options, and a verification that the
 * declared workflow survived.
 *
 * The suite runs against whichever source the console selects. With the core
 * service running it drives the live engine; without it, the recorded snapshot.
 * Both must behave identically, which is itself worth testing.
 */

import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('between agents');
  // Replay state lives in the service, so start every journey from the top.
  await page.getByRole('button', { name: 'Restart' }).click();
  await expect(page.getByText('Nothing composed yet.')).toBeVisible();
});

test('the safety posture is stated before anything else', async ({ page }) => {
  await expect(page.getByText(/Simulated environment\. Fictional data\./)).toBeVisible();
});

test('the baseline reports nothing, and says so as an invitation', async ({ page }) => {
  await expect(page.getByText('Nothing composed yet.')).toBeVisible();
  await expect(page.getByText('00 / 12')).toBeVisible();
});

test('a risk appears only once the path actually closes', async ({ page }) => {
  // Two actors have found the undeclared scratchpad and one has written to it,
  // but nothing has read it back: there is no route yet.
  await page.getByLabel('Replay position').fill('11');
  await expect(page.getByText('Nothing composed yet.')).toBeVisible();

  // The final event is an ordinary read. It closes the route.
  await page.getByLabel('Replay position').fill('12');
  await expect(page.getByText('PS-001 · finding')).toBeVisible();
  await expect(
    page.getByRole('heading', { name: /Restricted data can reach external egress/ }),
  ).toBeVisible();
});

test('the finding names its path, its evidence, and its limits', async ({ page }) => {
  await page.getByRole('button', { name: 'Run to end' }).click();

  const path = page.locator('[data-panel="Composed path"]');
  await expect(page.getByText('4 hops')).toBeVisible();

  // Three of the four hops are relationships the architecture declares. That is
  // the whole argument, so it must be on screen.
  await expect(path.getByText('declared', { exact: true }).first()).toBeVisible();
  await expect(path.getByText('not declared', { exact: true }).first()).toBeVisible();

  await expect(page.getByText(/does not establish/i)).toBeVisible();
  await expect(page.getByText('evidence', { exact: true }).first()).toBeVisible();
});

test('containment compares every registered control and rejects unsafe ones', async ({ page }) => {
  await page.getByRole('button', { name: 'Run to end' }).click();

  await expect(page.getByText('PS-001 · finding')).toBeVisible();

  const table = page.getByRole('table');
  await expect(table).toBeVisible();
  await expect(table.getByRole('row')).toHaveCount(6); // header plus five controls

  await expect(page.getByText('recommended', { exact: true })).toHaveCount(1);
  await expect(page.getByText(/Breaks declared relationships/).first()).toBeVisible();
});

test('applying the recommendation verifies the result', async ({ page }) => {
  await page.getByRole('button', { name: 'Run to end' }).click();
  await page.getByRole('button', { name: 'Apply recommended control' }).click();

  await expect(page.getByText('Containment verified')).toBeVisible();
  await expect(page.getByText('Composed path removed').first()).toBeVisible();
  await expect(page.getByText('Declared work preserved').first()).toBeVisible();
  await expect(page.getByText('verified').first()).toBeVisible();

  // The finding is gone and the declared workflow is still listed as in use.
  await expect(page.getByText('PS-001 · finding')).toHaveCount(0);
  await expect(page.getByText('in use').first()).toBeVisible();
});

test('containment records a draft pattern that a person must promote', async ({ page }) => {
  await page.getByRole('button', { name: 'Run to end' }).click();
  await page.getByRole('button', { name: 'Apply recommended control' }).click();

  await expect(page.getByText('Containment verified')).toBeVisible();
  await expect(page.getByText('1 recorded')).toBeVisible();
  await expect(page.getByText('draft', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /Promote to shadow/i })).toBeVisible();
});

test('restarting the replay returns the estate to its baseline', async ({ page }) => {
  await page.getByRole('button', { name: 'Run to end' }).click();
  await expect(page.getByText('PS-001 · finding')).toBeVisible();

  await page.getByRole('button', { name: 'Restart' }).click();
  await expect(page.getByText('Nothing composed yet.')).toBeVisible();
  await expect(page.getByText(/The estate is at rest/)).toBeVisible();
});

test('the second estate reaches the same conclusion with different names', async ({ page }) => {
  await page.getByRole('radio', { name: /unreviewed instruction channel/i }).click();
  await page.getByRole('button', { name: 'Run to end' }).click();

  await expect(page.getByText('PS-002 · finding')).toBeVisible();
  await expect(
    page.getByRole('heading', { name: /executes content authored by another/ }),
  ).toBeVisible();
});

test('the lab answers no, and says which parameter to change', async ({ page }) => {
  await page.getByRole('radio', { name: 'off' }).click();
  await page.getByRole('button', { name: 'Run experiment' }).click();

  await expect(page.getByText('No composition formed.')).toBeVisible();
  await expect(page.getByText(/undeclared shared state/)).toBeVisible();
});

test('the lab runs the real rules when a composition is possible', async ({ page }) => {
  await page.getByRole('radio', { name: 'enabled' }).click();
  await page.getByRole('radio', { name: 'broad' }).click();
  await page.getByRole('button', { name: 'Run experiment' }).click();

  await expect(page.getByText('A composition formed.')).toBeVisible();

  // At this population a single targeted block no longer removes every path,
  // so the planner falls through to the heavier control that does. Which one
  // it picks is the engine's business; that it picks a registered one is ours.
  await expect(page.getByText(/recommends \S+/).first()).toBeVisible();
  await expect(page.getByText(/controls viable/)).toBeVisible();
});

test('the map is described for assistive technology', async ({ page }) => {
  await page.getByRole('button', { name: 'Run to end' }).click();
  const map = page.getByRole('img', { name: 'Agent interaction map' });
  await expect(map).toBeVisible();
  await expect(page.getByText(/Zones run from the trusted interior/)).toBeAttached();
});

test('the console is operable from the keyboard alone', async ({ page }) => {
  // Reload so focus starts at the top of the document rather than on whatever
  // the shared setup last clicked.
  await page.goto('/');
  await page.locator('body').press('Tab');
  await expect(page.getByRole('link', { name: /Skip to the interaction map/ })).toBeFocused();

  // Every replay control must be reachable and operable without a pointer.
  await page.getByRole('button', { name: 'Run to end' }).press('Enter');
  await expect(page.getByText('PS-001 · finding')).toBeVisible();
});
