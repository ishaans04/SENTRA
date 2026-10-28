/**
 * The fallback link (AC-13): with no service behind it, the static console
 * plays the recorded storyline, says so, and disables every command.
 */

import { expect, test } from '@playwright/test';

test('the recorded replay plays the storyline with commands disabled', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Recorded replay').first()).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Approval' })).toBeDisabled();
  await expect(page.getByRole('textbox', { name: 'Tell AEGIS' })).toBeDisabled();

  const step = page.getByRole('button', { name: 'Step', exact: true });
  for (let i = 0; i < 12 && (await step.isEnabled()); i += 1) await step.click();

  await expect(page.getByText('The story is finished.')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Final record' })).toContainText(
    'Support work preserved.',
  );
});
