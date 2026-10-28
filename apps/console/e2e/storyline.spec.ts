/**
 * The judge path, typed, from a fresh sandbox to the closed record (AC-01 to AC-10, AC-14).
 *
 * Everything a judge would dictate with Wispr Flow is typed here instead, into
 * the same plain text boxes, which is the proof that the product does not
 * depend on dictation to work.
 */

import { expect, test, type Page } from '@playwright/test';

const APPROVAL =
  'Approve reporting, on the condition that the Reporting Agent only reads from the approved, sanitized report store.';
const RECOVERY =
  'Stop this reporting run, remove its scratchpad access, and rebuild the report from approved summaries. Keep the support work.';

async function stepUntil(page: Page, beat: RegExp) {
  const stepButton = page.getByRole('button', { name: 'Step', exact: true });
  for (let i = 0; i < 20; i += 1) {
    if (await page.getByText(beat).isVisible()) return;
    await stepButton.click();
    // Wait for the step to land: Step comes back, or the story has finished.
    await expect
      .poll(async () => (await stepButton.isEnabled()) || (await page.getByText(beat).isVisible()))
      .toBe(true);
  }
  throw new Error(`never reached ${beat}`);
}

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Live sandbox').first()).toBeVisible();
});

test('labels present', async ({ page }) => {
  await expect(page.getByText('Fictional data').first()).toBeVisible();
  await expect(page.getByText(/Every control is enforced at the gateway/)).toBeVisible();
});

test('judge path, typed', async ({ page }) => {
  // Beat 1: the approval, typed into the box Wispr Flow would type into.
  await page.getByRole('textbox', { name: 'Approval' }).fill(APPROVAL);
  await page.getByRole('button', { name: 'Interpret' }).first().click();
  const readBack = page.getByLabel('Approval read-back');
  await expect(readBack).toContainText('ReadsOnlyFrom(reporting-agent');
  await readBack.getByRole('button', { name: 'Confirm' }).click();
  const card = page.getByRole('article', { name: 'Approval D-1' });
  await expect(card).toContainText('active');
  await expect(card).toContainText('epoch 1');

  // Beats 2 to 8: agents work, HIVE finds the route, the gateway holds and rejects.
  await stepUntil(page, /Beat 8: Late action\./);
  await expect(
    page.getByRole('region', { name: 'Interaction map' }).getByText('PS-001 possible route'),
  ).toBeVisible();
  await expect(card).toContainText('suspended');
  await expect(card).toContainText('epoch 2');
  await expect(card).toContainText('held');
  await expect(card).toContainText('stale_epoch');
  await expect(page.getByRole('alert').first()).toContainText(
    'Reporting was approved on the condition that this agent receives only sanitized summaries.',
  );

  // Beat 9: the dictated recovery, typed, then read back and confirmed.
  await page.keyboard.press('Control+k');
  await expect(page.getByRole('textbox', { name: 'Tell AEGIS' })).toBeFocused();
  await page.keyboard.type(RECOVERY);
  await page.keyboard.press('Control+Enter');
  const plan = page.getByLabel('Recovery read-back');
  await expect(plan).toContainText('Cancel reporting run R-1 and its held external send A-1.');
  await expect(plan).toContainText('I will not overwrite it. I will ask you.');
  await plan.getByRole('button', { name: 'Confirm' }).click();

  // Beat 11: the human edit survives as a conflict.
  await expect(page.getByRole('article', { name: 'Conflict on draft-1' })).toBeVisible();
  await expect(page.getByRole('button', { name: /overwrite/i })).toHaveCount(0);
  await page.getByRole('button', { name: 'Keep the human version' }).click();

  // Beats 12 to 14: the replacement, the four checks and the record.
  await stepUntil(page, /The story is finished\./);
  const verification = page.getByRole('region', { name: 'Verification' });
  await expect(verification.getByText('passed')).toHaveCount(4);
  const record = page.getByRole('region', { name: 'Final record' });
  await expect(record).toContainText('Affected send cancelled.');
  await expect(record).toContainText('Support work preserved.');
  await expect(record).toContainText('The human version was kept for review.');
});
