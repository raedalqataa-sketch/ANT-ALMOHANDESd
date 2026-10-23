import { test, expect } from '@playwright/test';

test('architectural client launches as an Arabic right-to-left page', async ({ page }) => {
  await page.goto('/client/');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.getByRole('link', { name: /أنت المهندس/ })).toBeVisible();
  await expect(page.getByRole('main')).toBeVisible();
  await expect(page.getByText('المقترحات مسودات للمراجعة الهندسية', { exact: false })).toBeVisible();
});
