import { expect, test, type Page } from '@playwright/test';

const INTERNAL_NAMES = /\bsentra_core\b|\bSENTRA_[A-Z]/;

function failOnConsoleErrors(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  return errors;
}

test('landing page tells the story and links to both demos', async ({ page }) => {
  const errors = failOnConsoleErrors(page);
  await page.goto('./');
  await expect(page.getByRole('heading', { level: 1 })).toContainText(
    'Stop what went wrong. Keep everything else.',
  );
  await expect(page.locator('body')).not.toContainText(INTERNAL_NAMES);

  // The problem scene pins; scrolling through it links the four steps.
  await page.getByRole('link', { name: 'How it works' }).first().click();
  await expect(page.getByText('Every step was allowed.')).toBeVisible();
  await expect(page.getByText('of 04 steps')).toBeVisible();
  // Jump to 90% of the pinned scene rather than wheeling: wheel steps are
  // smoothed, so how far a fixed number of them travels depends on the machine.
  await page.evaluate(() => {
    const scene = document.getElementById('how')!;
    const top = scene.getBoundingClientRect().top + window.scrollY;
    const travel = scene.offsetHeight - window.innerHeight;
    window.scrollTo({ top: top + travel * 0.9, behavior: 'instant' });
  });
  await expect(page.getByText('steps, linked')).toBeVisible();
  await expect(page.getByText('✓ Allowed · but linked')).toHaveCount(4);

  // Asking both: the assistant advises, SENTRA holds the report.
  await page.locator('#why').scrollIntoViewIfNeeded();
  await page.getByText('THE SITUATION').scrollIntoViewIfNeeded();
  await expect(page.getByText('✓ Stopped in time. Support kept working.')).toHaveCSS(
    'opacity',
    '1',
    { timeout: 10000 },
  );

  // Three differences, boxed like the reasons beneath them.
  await page.getByText('Three differences that matter at work.').scrollIntoViewIfNeeded();
  await expect(page.locator('.ld-diff')).toHaveCount(3);
  await expect(page.locator('.ld-diff').first()).toHaveCSS('opacity', '1', { timeout: 5000 });

  await page.getByRole('button', { name: 'Speak' }).scrollIntoViewIfNeeded();
  await page.getByRole('button', { name: 'Speak' }).click();
  await page.getByRole('button', { name: 'Yes, do it' }).click({ timeout: 8000 });
  await expect(page.getByText(/Only the report was redone/)).toBeVisible({ timeout: 8000 });

  await page.getByRole('button', { name: 'Shut everything down' }).click();
  await expect(page.getByText('Everything stops.', { exact: false })).toBeVisible();

  await page.getByRole('button', { name: 'Try the demo' }).click();
  await expect(page).toHaveURL(/#\/demo$/);
  expect(errors).toEqual([]);
});

test('guided walkthrough runs from first step to a week later', async ({ page }) => {
  const errors = failOnConsoleErrors(page);
  await page.goto('./#/demo');
  await expect(page.getByText('STEP 01 OF 08')).toBeVisible();
  for (let i = 0; i < 4; i++) await page.keyboard.press('ArrowRight');
  await expect(page.getByText('STEP 05 OF 08')).toBeVisible();
  await page.getByRole('button', { name: 'Speak →' }).click();
  await page.getByRole('button', { name: 'Yes, do it →' }).click({ timeout: 8000 });
  await expect(page.getByText('STEP 06 OF 08')).toBeVisible({ timeout: 8000 });
  await page.getByRole('button', { name: 'See the result →' }).click({ timeout: 12000 });
  await expect(page.getByText('All clear')).toBeVisible();
  await page.getByRole('button', { name: 'Remember this →' }).click();
  await expect(page.getByText('STEP 08 OF 08')).toBeVisible();
  await page.getByRole('button', { name: 'Speak →' }).click();
  await page.getByRole('button', { name: 'Yes, keep it →' }).click();
  await expect(page.getByText('Turned away at the gateway, citing your words.')).toBeVisible({
    timeout: 8000,
  });
  await expect(page.locator('body')).not.toContainText(INTERNAL_NAMES);
  await page.getByRole('button', { name: 'Open the full console →' }).click();
  await expect(page).toHaveURL(/#\/console$/);
  expect(errors).toEqual([]);
});

test('console replays the session through the operator’s decision', async ({ page }) => {
  const errors = failOnConsoleErrors(page);
  await page.goto('./#/console');
  await expect(page.getByRole('heading', { name: 'The approved workflow' })).toBeVisible();
  await expect(page.locator('body')).not.toContainText(INTERNAL_NAMES);

  await page.keyboard.press('Control+k');
  const box = page.getByRole('textbox', { name: /Tell SENTRA/ });
  await expect(box).toBeFocused();
  await expect(
    page.getByRole('heading', { name: 'The operator decides, in plain words' }),
  ).toBeVisible();

  await box.fill('Cancel the run and keep the support work.');
  await page.keyboard.press('Control+Enter');
  await expect(page.getByText(/CONFIRMED #16/)).toBeVisible();
  await expect(page.getByText('not requested — left as it is').first()).toBeVisible({
    timeout: 8000,
  });

  await page.getByRole('button', { name: /Fictional CRM/ }).click();
  await expect(page.getByText('Support Agent may read')).toBeVisible();

  // The case file is a glass panel: it can be closed and brought back.
  const glass = page.getByRole('complementary', { name: 'Case file' });
  await expect(glass).toBeInViewport();
  await page.getByRole('button', { name: 'Close case file' }).click();
  await expect(glass).not.toBeInViewport();
  await page.getByRole('button', { name: /Case file/ }).click();
  await expect(glass).toBeInViewport();

  // The record pops up, then moves into the case file after three seconds.
  await page.getByRole('button', { name: /07 Verified/ }).click();
  await expect(page.getByRole('dialog', { name: 'Outcome record' })).toBeVisible();
  await expect(page.getByRole('dialog', { name: 'Outcome record' })).toBeHidden({
    timeout: 6000,
  });
  await expect(glass.getByText('OUTCOME RECORD · REPLAYABLE')).toBeVisible();
  expect(errors).toEqual([]);
});
