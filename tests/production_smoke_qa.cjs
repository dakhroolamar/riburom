/* Read-only production smoke QA. Never submits forms or mutates server state. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

const BASE = process.env.RB_QA_BASE_URL || 'https://riburomtours.com';
const desktop = { width: 1440, height: 900 };
const mobile = { width: 390, height: 844 };

function absolute(path) { return new URL(path, BASE).toString(); }

async function waitForPublicReady(page) {
  await page.locator('#rb-page-loader').waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  await page.waitForLoadState('domcontentloaded');
}

async function assertNoHorizontalOverflow(page, label) {
  const m = await page.evaluate(() => ({
    viewport: innerWidth,
    html: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  assert.ok(m.html <= m.viewport + 2 && m.body <= m.viewport + 2,
    `${label} horizontal overflow: ${JSON.stringify(m)}`);
}

async function assertBasicMetadata(page, label) {
  const meta = await page.evaluate(() => ({
    title: document.title.trim(),
    canonical: document.querySelector('link[rel="canonical"]')?.href || '',
    description: document.querySelector('meta[name="description"]')?.content?.trim() || '',
    h1: document.querySelector('h1')?.textContent?.trim() || '',
  }));
  assert.ok(meta.title, `${label}: missing title`);
  assert.ok(meta.canonical.startsWith(BASE), `${label}: invalid canonical ${meta.canonical}`);
  assert.ok(meta.description.length >= 40, `${label}: weak/missing meta description`);
  assert.ok(meta.h1, `${label}: missing h1`);
}

async function assertLoadedVisibleImages(page, label) {
  await page.evaluate(async () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    for (const y of [0, .25, .5, .75, 1]) {
      scrollTo(0, Math.max(0, Math.round(max * y)));
      await new Promise(r => setTimeout(r, 120));
    }
    scrollTo(0, 0);
  });
  await page.waitForTimeout(250);
  const broken = await page.evaluate(() => [...document.images]
    .filter(img => {
      const r = img.getBoundingClientRect();
      const meaningful = img.getAttribute('src') && !img.hidden;
      return meaningful && img.complete && img.naturalWidth === 0 && r.width > 1 && r.height > 1;
    })
    .map(img => img.currentSrc || img.src));
  assert.deepEqual(broken, [], `${label}: broken images ${broken.join(', ')}`);
}

async function getJson(request, path) {
  const response = await request.get(absolute(path));
  assert.equal(response.status(), 200, `${path} returned ${response.status()}`);
  return response.json();
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const pageErrors = [];
  const badSameOrigin = [];

  const context = await browser.newContext({ viewport: desktop, reducedMotion: 'no-preference' });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.on('pageerror', err => pageErrors.push(err.message));
  page.on('response', response => {
    const url = new URL(response.url());
    if (url.origin === new URL(BASE).origin && response.status() >= 400) {
      badSameOrigin.push(`${response.status()} ${url.pathname}`);
    }
  });

  // Runtime/readiness + security headers.
  for (const path of ['/healthz', '/readyz']) {
    const r = await context.request.get(absolute(path));
    assert.equal(r.status(), 200, `${path} returned ${r.status()}`);
  }
  const rootHeaders = await context.request.get(absolute('/'));
  assert.equal(rootHeaders.status(), 200);
  const headers = rootHeaders.headers();
  assert.equal(headers['x-content-type-options'], 'nosniff');
  assert.equal(headers['x-frame-options'], 'SAMEORIGIN');
  assert.equal(headers['referrer-policy'], 'strict-origin-when-cross-origin');
  assert.ok(headers['strict-transport-security']?.includes('max-age='), 'missing HSTS');
  if (!headers['content-security-policy']) console.log('QA-WARN: Content-Security-Policy header is not configured.');

  const robots = await context.request.get(absolute('/robots.txt'));
  assert.equal(robots.status(), 200);
  assert.match(await robots.text(), /Sitemap:\s*https:\/\/riburomtours\.com\/sitemap\.xml/i);
  const sitemap = await context.request.get(absolute('/sitemap.xml'));
  assert.equal(sitemap.status(), 200);
  const sitemapText = await sitemap.text();
  assert.match(sitemapText, /https:\/\/riburomtours\.com\/marketplace/);

  const media = await getJson(context.request, '/api/public-section-backgrounds');
  assert.ok(media && typeof media === 'object');
  assert.ok(media.backgrounds && media.galleries && media.styles, 'section media API contract incomplete');
  for (const key of ['home_gallery', 'home_about_gallery']) {
    assert.ok(Array.isArray(media.galleries[key]), `missing gallery array ${key}`);
    assert.ok(media.galleries[key].length <= 10, `${key} exceeds 10-image limit`);
  }

  // Desktop public routes.
  const publicRoutes = ['/', '/all_tours', '/marketplace', '/about'];
  for (const route of publicRoutes) {
    const response = await page.goto(absolute(route), { waitUntil: 'domcontentloaded' });
    assert.equal(response.status(), 200, `${route} returned ${response.status()}`);
    await waitForPublicReady(page);
    await assertNoHorizontalOverflow(page, `${route} desktop`);
    await assertBasicMetadata(page, route);
    await assertLoadedVisibleImages(page, route);
  }

  // Homepage interaction system.
  await page.goto(absolute('/'), { waitUntil: 'domcontentloaded' });
  await waitForPublicReady(page);
  const hero = page.locator('#rb-home-hero');
  await hero.waitFor();
  const film = page.locator('[data-rb-hero-animation-video]');
  if (await film.count()) {
    await page.waitForTimeout(500);
    const filmMetrics = await film.evaluate((el) => {
      const r = el.getBoundingClientRect();
      const h = document.querySelector('#rb-home-hero').getBoundingClientRect();
      return { width: r.width, height: r.height, heroWidth: h.width, cls: el.className };
    });
    assert.ok(String(filmMetrics.cls).includes('rb-hero-opening-film'), 'hero film not promoted to opening-film layer');
    assert.ok(Math.abs(filmMetrics.width - filmMetrics.heroWidth) < 3, `hero film is not full width: ${JSON.stringify(filmMetrics)}`);
    assert.ok(filmMetrics.height >= 280, `hero film too short: ${filmMetrics.height}`);
    await film.evaluate(el => el.dispatchEvent(new Event('ended')));
    await page.waitForTimeout(650);
  }
  const logoMetrics = await page.locator('.rb-hero-permanent-logo').evaluate(el => ({
    original: Number(el.dataset.rbOriginalHeroWidth || 0),
    width: parseFloat(getComputedStyle(el).width),
  }));
  if (logoMetrics.original) {
    assert.ok(Math.abs(logoMetrics.width - Math.min(logoMetrics.original * 2, 320)) < 3,
      `final hero logo is not doubled: ${JSON.stringify(logoMetrics)}`);
  }
  const gap = await page.evaluate(() => {
    const content = document.querySelector('#rb-home-hero .rb-hero-content')?.getBoundingClientRect();
    const landscape = document.querySelector('#rb-home-hero .rb-paper-landscape')?.getBoundingClientRect();
    return content && landscape ? landscape.top - content.bottom : 0;
  });
  assert.ok(gap >= 20, `hero-to-landscape breathing room too small: ${gap}px`);

  const whyVisual = await page.locator('#rb-home-why').evaluate(el => {
    const s = getComputedStyle(el);
    return { clipPath: s.clipPath, backgroundImage: s.backgroundImage, color: s.color };
  });
  assert.notEqual(whyVisual.clipPath, 'none', 'Why RI BUROM has no torn-paper silhouette');
  assert.match(whyVisual.backgroundImage, /gradient/i, 'Why RI BUROM is missing aged-paper texture');

  const experienceShell = page.locator('#rb-home-tours [data-rb-rail-shell]');
  if (await experienceShell.count()) {
    const track = experienceShell.locator('[data-rb-rail-track]');
    const cardCount = await track.locator('.rb-experience-card').count();
    if (cardCount > 1) {
      const before = await track.evaluate(el => el.scrollLeft);
      await experienceShell.locator('[data-rb-rail-next]').click();
      await page.waitForTimeout(500);
      const after = await track.evaluate(el => el.scrollLeft);
      assert.ok(after > before, `Signature Experiences next control did not scroll: ${before} -> ${after}`);
    }
  }

  const riverGallery = page.locator('[data-rb-river-gallery]');
  if ((media.galleries.home_gallery || []).length) {
    await page.waitForFunction(() => !document.querySelector('[data-rb-river-gallery]')?.hidden);
    assert.equal(await riverGallery.locator('.rb-river-gallery-slide').count(), Math.min(media.galleries.home_gallery.length, 10));
    if (media.galleries.home_gallery.length > 1) {
      const track = riverGallery.locator('[data-rb-rail-track]');
      const before = await track.evaluate(el => el.scrollLeft);
      await riverGallery.locator('[data-rb-rail-next]').click();
      await page.waitForTimeout(500);
      const after = await track.evaluate(el => el.scrollLeft);
      assert.ok(after > before, `river gallery next control did not scroll: ${before} -> ${after}`);
    }
  } else {
    assert.equal(await page.locator('[data-rb-river-gallery-fallback]').isVisible(), true, 'river gallery fallback is missing');
  }

  const aboutImages = (media.galleries.home_about_gallery || []).length || (media.backgrounds.home_about ? 1 : 0);
  if (aboutImages) {
    const flip = page.locator('[data-rb-about-flip]');
    await page.waitForFunction(() => !document.querySelector('[data-rb-about-flip]')?.hidden);
    assert.equal(await flip.isVisible(), true);
    if ((media.galleries.home_about_gallery || []).length > 1) {
      const counter = flip.locator('[data-rb-about-counter]');
      const before = await counter.textContent();
      await flip.locator('[data-rb-about-next]').click();
      await page.waitForTimeout(650);
      const after = await counter.textContent();
      assert.notEqual(after, before, 'About calendar-flip gallery did not advance');
    }
  } else {
    assert.equal(await page.locator('[data-rb-about-gallery-fallback]').isVisible(), true, 'About fallback artwork is missing');
  }

  assert.ok(await page.locator('#rb-home-contact form input[name="csrf_token"]').count(), 'homepage enquiry missing CSRF token');

  // Tour detail: separate, package-specific enquiry.
  await page.goto(absolute('/all_tours'), { waitUntil: 'domcontentloaded' });
  const tourHref = await page.locator('a[href^="/tours/"]').first().getAttribute('href').catch(() => null);
  if (tourHref) {
    const response = await page.goto(absolute(tourHref), { waitUntil: 'domcontentloaded' });
    assert.equal(response.status(), 200, `${tourHref} returned ${response.status()}`);
    await waitForPublicReady(page);
    await assertNoHorizontalOverflow(page, 'tour detail desktop');
    await assertBasicMetadata(page, 'tour detail');
    const enquiry = page.locator('#tour-enquiry form');
    assert.equal(await enquiry.count(), 1, 'tour-specific enquiry section missing');
    const interest = await enquiry.locator('input[name="tour_interest"]').getAttribute('value');
    const title = (await page.locator('h1').textContent()).trim();
    assert.equal(interest, title, 'tour enquiry is not tied to package title');
  }

  // Marketplace provider interaction, without submitting anything.
  await page.goto(absolute('/marketplace'), { waitUntil: 'domcontentloaded' });
  const providerHref = await page.locator('a[href^="/marketplace/providers/"]').first().getAttribute('href').catch(() => null);
  if (providerHref) {
    const response = await page.goto(absolute(providerHref), { waitUntil: 'domcontentloaded' });
    assert.equal(response.status(), 200, `${providerHref} returned ${response.status()}`);
    await waitForPublicReady(page);
    await assertNoHorizontalOverflow(page, 'provider detail desktop');
    const opener = page.locator('#openProviderInquiry');
    if (await opener.count()) {
      await opener.click();
      await page.locator('#providerInquiryOverlay.is-open').waitFor();
      assert.ok(await page.locator('#providerInquiryForm input[name="csrf_token"]').count(), 'provider enquiry missing CSRF token');
      await page.keyboard.press('Escape');
    }
  }

  // Mobile navigation and responsive overflow.
  const mobileContext = await browser.newContext({ viewport: mobile, reducedMotion: 'reduce' });
  const mobilePage = await mobileContext.newPage();
  mobilePage.on('pageerror', err => pageErrors.push(`mobile: ${err.message}`));
  for (const route of publicRoutes) {
    const response = await mobilePage.goto(absolute(route), { waitUntil: 'domcontentloaded' });
    assert.equal(response.status(), 200, `${route} mobile returned ${response.status()}`);
    await waitForPublicReady(mobilePage);
    await assertNoHorizontalOverflow(mobilePage, `${route} mobile`);
  }
  await mobilePage.goto(absolute('/'), { waitUntil: 'domcontentloaded' });
  await waitForPublicReady(mobilePage);
  await mobilePage.locator('#mobile-menu-button').click();
  assert.equal(await mobilePage.locator('#mobile-menu-button').getAttribute('aria-expanded'), 'true');
  assert.equal(await mobilePage.locator('#mobile-menu').getAttribute('aria-hidden'), 'false');
  await mobilePage.keyboard.press('Escape');
  assert.equal(await mobilePage.locator('#mobile-menu-button').getAttribute('aria-expanded'), 'false');

  const uniqueBad = [...new Set(badSameOrigin)].filter(x => !x.startsWith('404 /favicon'));
  assert.deepEqual(uniqueBad, [], `same-origin HTTP errors observed: ${uniqueBad.join(', ')}`);
  assert.deepEqual(pageErrors, [], `browser page errors: ${pageErrors.join(' | ')}`);

  console.log('Production smoke QA passed: runtime, security headers, SEO, desktop/mobile layout, galleries, experience rail, tour enquiry and marketplace interaction.');
  await mobileContext.close();
  await context.close();
  await browser.close();
})().catch(err => {
  console.error(err);
  process.exit(1);
});
