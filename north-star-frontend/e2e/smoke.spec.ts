import { test, expect } from '@playwright/test';
test('login screen renders', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByText('Your personal NorthStar')).toBeVisible();
});
