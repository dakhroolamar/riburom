const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');

const BASE = process.env.CMS_QA_BASE_URL || 'http://127.0.0.1:5055';
const OUT = '/tmp/riburom-cms-qa';
fs.mkdirSync(OUT, { recursive: true });

async function assertNoHorizontalOverflow(page, label) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  assert.ok(
    overflow.scrollWidth <= overflow.clientWidth + 2,
    `${label}: horizontal overflow ${overflow.scrollWidth}px > ${overflow.clientWidth}px`
  );
}

async function waitForImages(page, selector) {
  await page.waitForFunction((sel) => {
    const images = [...document.querySelectorAll(sel)];
    return images.length > 0 && images.every((img) => img.complete && img.naturalWidth > 0);
  }, selector, { timeout: 10000 });
}

async function scrollThrough(page) {
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  const viewport = page.viewportSize()?.height || 800;
  for (let y = 0; y < height; y += Math.max(320, Math.floor(viewport * 0.7))) {
    await page.evaluate((top) => window.scrollTo(0, top), y);
    await page.waitForTimeout(45);
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(150);
}

async function assertPublicCmsRendering(page, label) {
  await page.waitForFunction(() => {
    const hero = document.querySelector('.cms-hero-gallery');
    const river = document.querySelector('[data-rb-river-gallery]');
    const about = document.querySelector('[data-rb-about-flip]');
    return hero && hero.querySelectorAll('.cms-gallery-track figure').length >= 3 &&
      river && !river.hidden && river.querySelectorAll('.rb-river-gallery-slide').length >= 3 &&
      about && !about.hidden && about.querySelector('img')?.complete && about.querySelector('img')?.naturalWidth > 0;
  }, { timeout: 10000 });
  await waitForImages(page, '.cms-hero-gallery img');
  assert.ok(await page.locator('.rb-river-gallery-slide').count() >= 3, `${label}: CMS river gallery was not rendered`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const errors = [];

  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`);
  });

  await page.goto(`${BASE}/__visual/cms`, { waitUntil: 'networkidle' });
  assert.equal(page.url(), `${BASE}/workspace/pages`);
  await page.locator('h1').waitFor();
  assert.equal((await page.locator('h1').textContent()).trim(), 'Home');
  assert.equal(await page.locator('meta[name="csrf-token"]').count(), 1);
  await assertNoHorizontalOverflow(page, 'CMS desktop');

  await page.locator('button[data-section="hero"]').click();
  await page.locator('#media-editor:not([hidden])').waitFor();
  assert.ok(await page.locator('#collection-items .media-card').count() >= 3, 'Hero CMS collection did not load seeded media');
  await waitForImages(page, '#collection-items .media-card > img');

  const collectionSave = page.waitForResponse((response) =>
    response.url().includes('/workspace/media-api/collections/hero') &&
    response.request().method() === 'POST'
  );
  await page.locator('#save-collection').click();
  assert.equal((await collectionSave).status(), 200, 'Hero collection save failed');

  await page.locator('[data-panel="appearance"]').click();
  await page.locator('#logo-editor:not([hidden])').waitFor();
  await page.locator('#logo-device').selectOption('mobile');
  await page.locator('#logo-size').fill('55');
  const placementSave = page.waitForResponse((response) =>
    response.url().includes('/workspace/media-api/hero-placement') &&
    response.request().method() === 'POST'
  );
  await page.locator('#logo-save').click();
  assert.equal((await placementSave).status(), 200, 'Responsive hero logo placement save failed');

  await page.screenshot({ path: `${OUT}/cms-pages-desktop.png`, fullPage: true });

  await page.goto(`${BASE}/workspace/library`, { waitUntil: 'networkidle' });
  await page.locator('#library-page').waitFor();
  assert.ok(await page.locator('#library-results .media-card').count() >= 3, 'Reusable media library did not render seeded assets');
  await assertNoHorizontalOverflow(page, 'CMS media library desktop');
  await page.screenshot({ path: `${OUT}/cms-library-desktop.png`, fullPage: true });

  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await assertNoHorizontalOverflow(page, 'Public homepage desktop');
  const publicMedia = await page.evaluate(async () => {
    const response = await fetch('/api/public-section-backgrounds');
    if (!response.ok) throw new Error(`public CMS API returned ${response.status}`);
    return response.json();
  });
  assert.ok(publicMedia.media_details, 'Public CMS response is missing media_details');
  assert.ok((publicMedia.media_details.home_gallery || []).length >= 3, 'Public homepage did not expose CMS river gallery media');
  assert.ok((publicMedia.media_details.home_about_gallery || []).length >= 3, 'Public homepage did not expose CMS About gallery media');
  await assertPublicCmsRendering(page, 'desktop');
  await scrollThrough(page);
  await page.screenshot({ path: `${OUT}/home-desktop.png`, fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/__visual/cms`, { waitUntil: 'networkidle' });
  await page.locator('h1').waitFor();
  await assertNoHorizontalOverflow(page, 'CMS mobile 390px');
  await page.screenshot({ path: `${OUT}/cms-pages-mobile-390.png`, fullPage: true });

  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await assertNoHorizontalOverflow(page, 'Public homepage mobile 390px');
  await assertPublicCmsRendering(page, 'mobile 390px');
  await scrollThrough(page);
  await page.screenshot({ path: `${OUT}/home-mobile-390.png`, fullPage: true });

  assert.deepEqual(errors, [], `Browser errors detected:\n${errors.join('\n')}`);
  await browser.close();
  console.log('CMS browser QA passed: editor, collection persistence, logo placement, media library, rendered public galleries, desktop and 390px layouts.');
})().catch(async (error) => {
  console.error(error.stack || error);
  process.exit(1);
});
