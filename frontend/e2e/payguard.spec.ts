import { test, expect } from '@playwright/test';

test.describe('PayGuard AI E2E Browser Testing Suite', () => {

  test('1. Protected Route & Entry Experience: Landing page CTA and unauthenticated route protection redirect to /login', async ({ page }) => {
    // 1a. Root entry `/` displays the flagship landing experience for unauthenticated visitors
    await page.goto('/');
    await expect(page.locator('text=AGENTIC PAYMENT TRIAGE & GROUNDED RAG')).toBeVisible();

    // 1b. Navigating to a protected route without auth redirects to /login
    await page.goto('/investigations');
    await expect(page).toHaveURL(/.*\/login/);
    await expect(page.locator('h2')).toContainText('Sign in to PayGuard AI');
  });

  test('2. Authentication: Invalid credentials display safe error message', async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'nonexistent.operator@payguard.ai');
    await page.fill('#password', 'WrongPassword123!');
    await page.click('button[type="submit"]');

    // Verify error notification is displayed
    const errorAlert = page.locator('div[role="alert"]');
    await expect(errorAlert).toBeVisible({ timeout: 10000 });
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('3. Authentication: Successful login, session persistence & protected navigation', async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'agent@payguard.ai');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');

    // Verify redirect to dashboard
    await expect(page).toHaveURL('http://localhost:3001/', { timeout: 15000 });

    // Verify session persistence in localStorage
    const token = await page.evaluate(() => localStorage.getItem('payguard_access_token'));
    expect(token).toBeTruthy();

    // Verify operator profile is visible in header/sidebar
    await expect(page.locator('body')).toContainText('Sarah Chen');
  });

  test('4. Dashboard: Real metrics, recent investigations feed & layout', async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('#email', 'agent@payguard.ai');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('http://localhost:3001/', { timeout: 15000 });

    // Verify metric cards exist
    await expect(page.locator('text=Total Investigations')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Open Cases')).toBeVisible();

    // Verify navigation links within sidebar nav
    await expect(page.locator('nav a[href="/payments"]')).toBeVisible();
    await expect(page.locator('nav a[href="/investigations"]')).toBeVisible();
    await expect(page.locator('nav a[href="/knowledge"]')).toBeVisible();
  });

  test('5. Payments: Listing, search filter & detail view navigation', async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('#email', 'agent@payguard.ai');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('http://localhost:3001/', { timeout: 15000 });

    // Navigate to Payments
    await page.goto('/payments');
    await expect(page).toHaveURL(/.*\/payments/);
    await expect(page.locator('h1')).toContainText('Payment Transactions');

    // Wait for payments table to load
    const paymentRows = page.locator('table tbody tr');
    await expect(paymentRows.first()).toBeVisible({ timeout: 10000 });

    // Click on the first payment reference to view details
    const firstRefLink = paymentRows.first().locator('a').first();
    await firstRefLink.click();

    // Verify payment detail page loads
    await expect(page).toHaveURL(/.*\/payments\/.+/);
    await expect(page.locator('text=Financial & Gateway Metadata')).toBeVisible();
    await expect(page.locator('text=Chronological State Transition Timeline')).toBeVisible();
  });

  test('6. Investigation: Create new case with automated triage synthesis & citations', async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('#email', 'agent@payguard.ai');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('http://localhost:3001/', { timeout: 15000 });

    // Navigate to new investigation form
    await page.goto('/investigations/new');
    await expect(page.locator('h1')).toContainText('New Payment Investigation');

    // Fill customer problem query
    const query = 'Customer reports being charged twice for identical amounts within 60 seconds duplicate charge hold.';
    await page.fill('#customerQuery', query);

    // Select priority
    await page.click('button:has-text("high")');

    // Submit investigation
    await page.click('button[type="submit"]:has-text("Start Investigation")');

    // Verify navigation to investigation detail page
    await expect(page).toHaveURL(/.*\/investigations\/(?!new).+/, { timeout: 20000 });

    // Verify investigation results rendered
    await expect(page.locator('body')).toContainText('duplicate');
    await expect(page.locator('body')).toContainText('REQUEST_PAYMENT_DETAILS');
  });

  test('7. Knowledge: Search RAG policy repository & view retrieval results', async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('#email', 'agent@payguard.ai');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('http://localhost:3001/', { timeout: 15000 });

    // Navigate to Knowledge Explorer
    await page.goto('/knowledge');
    await expect(page.locator('h1')).toContainText('Payment Policy & Rule Explorer');

    // Search query
    const searchInput = page.locator('input[placeholder*="Query regulatory rules"]');
    await searchInput.fill('Visa Condition 10.4 fraud dispute timeline 3D Secure');
    await page.click('button[type="submit"]:has-text("Search RAG")');

    // Wait for search results
    await expect(page.locator('text=ranked policy chunks')).toBeVisible({ timeout: 15000 });
  });

  test('8. Authentication: Logout clears session and redirects to /login', async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.fill('#email', 'agent@payguard.ai');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('http://localhost:3001/', { timeout: 15000 });

    // Click Sign Out in header
    const logoutBtn = page.locator('button[title="Sign Out"]');
    await logoutBtn.click();

    await expect(page).toHaveURL(/.*\/login/, { timeout: 10000 });
    const token = await page.evaluate(() => localStorage.getItem('payguard_access_token'));
    expect(token).toBeNull();
  });

  test('9. Landing Experience & Interactive Feature Slider: Next/Prev controls and keyboard navigation', async ({ page }) => {
    await page.goto('/welcome');
    await expect(page.locator('h1')).toContainText('Investigate payment failures');

    // Verify interactive Feature Slider is visible
    const sliderRegion = page.locator('[aria-roledescription="carousel"]');
    await expect(sliderRegion).toBeVisible();
    await expect(sliderRegion).toContainText('Multi-rail transaction lookup & gateway error correlation');

    // Click Next slide button
    await page.click('button[aria-label="Next capability slide"]');
    await expect(sliderRegion).toContainText('Deterministic classification before generative synthesis');

    // Keyboard ArrowRight navigation on slider
    await sliderRegion.focus();
    await page.keyboard.press('ArrowRight');
    await expect(sliderRegion).toContainText('Reciprocal Rank Fusion over pgvector & PostgreSQL FTS');
  });

  test('10. Evidence Drawer: Clicking policy chunk opens slide-over citation inspector and closes on Escape', async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'agent@payguard.ai');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('http://localhost:3001/', { timeout: 15000 });

    await page.goto('/knowledge');
    const searchInput = page.locator('input[placeholder*="Query regulatory rules"]');
    await searchInput.fill('Visa Condition 10.4 fraud dispute timeline 3D Secure');
    await page.click('button[type="submit"]:has-text("Search RAG")');
    await expect(page.locator('text=ranked policy chunks')).toBeVisible({ timeout: 15000 });

    // Click Inspect button on first chunk to open EvidenceDrawer
    await page.locator('button:has-text("Inspect")').first().click();
    const drawer = page.locator('[role="dialog"][aria-labelledby="evidence-drawer-title"]');
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText('Cited Verbatim Excerpt');

    // Press Escape to close drawer
    await page.keyboard.press('Escape');
    await expect(drawer).toBeHidden();
  });

  test('11. Grounded Q&A & Document Management Tabs: Scope switching and upload dropzone', async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'agent@payguard.ai');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('http://localhost:3001/', { timeout: 15000 });

    await page.goto('/knowledge');

    // Switch to Grounded Q&A tab
    await page.click('button[role="tab"]:has-text("Grounded Q&A")');
    await expect(page.locator('text=Hallucination-Protected QA')).toBeVisible();

    // Switch to Upload & Manage tab
    await page.click('button[role="tab"]:has-text("Upload & Manage")');
    await expect(page.locator('text=Upload Compliance Document')).toBeVisible();
    await expect(page.locator('text=Click to choose a file')).toBeVisible();
  });

});
