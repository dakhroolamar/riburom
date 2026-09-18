/* Run against python -m tests.ui_preview. Requires Playwright externally.
   Only localhost is allowed; no submitted forms or external network traffic. */
const { chromium } = require('playwright');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const output = path.join(os.tmpdir(), 'riburom-paper-qa');
fs.mkdirSync(output, { recursive: true });
const routes = ['/', '/tours/visual-tour-0', '/tours/visual-tour-2', '/all_tours', '/marketplace', '/marketplace/providers/visual-provider', '/about', '/__visual/empty-marketplace'];
const sizes = [[1440,900], [1280,800], [1024,768], [768,1024], [390,844]];
(async () => {
  const browser = await chromium.launch({headless: true});
  const errors = [], results = [];
  const context = await browser.newContext({reducedMotion: 'reduce'});
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    return url.hostname === '127.0.0.1' || url.protocol === 'data:' ? route.continue() : route.abort();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  page.on('pageerror', error => errors.push(error.message));

  for (const [width,height] of sizes) {
    await page.setViewportSize({width,height});
    for (const [index, route] of routes.entries()) {
      const response = await page.goto('http://127.0.0.1:5055' + route);
      assert.equal(response.status(), 200, route);
      await page.locator('#rb-page-loader').waitFor({state: 'hidden'});
      const metrics = await page.evaluate(() => {
        const heading = document.querySelector('h1'), nav = document.querySelector('nav');
        const rect = heading.getBoundingClientRect();
        return {
          title: heading.textContent.trim(),
          overflow: document.documentElement.scrollWidth > innerWidth,
          headingOverflow: heading.scrollWidth > heading.clientWidth + 1,
          safe: rect.left >= 0 && rect.right <= innerWidth && rect.top >= nav.getBoundingClientRect().bottom,
          visible: getComputedStyle(heading).visibility !== 'hidden' && getComputedStyle(heading).opacity !== '0'
        };
      });
      assert.equal(metrics.overflow, false, `overflow ${route} ${width}`);
      assert.equal(metrics.headingOverflow, false, `title overflow ${route} ${width}`);
      assert.ok(metrics.safe && metrics.visible, JSON.stringify({route,width,metrics}));
      results.push({route,width,height,...metrics});
      await page.screenshot({path: path.join(output, `${width}-${index}.png`), fullPage: true});
    }
  }

  await page.goto('http://127.0.0.1:5055/');
  assert.equal(await page.locator('[data-rb-waterfall], [data-rb-water-canvas], .rb-waterfall, .rb-water-route').count(), 0,
    'homepage must not render river artwork or animation hooks');
  assert.equal(await page.locator('script[src*="ri-burom-waterfall"], script[src*="gsap"], script[src*="ScrollTrigger"]').count(), 0,
    'homepage must not load the removed river animation runtime');
  assert.ok(await page.locator('#rb-home-hero').count(), 'homepage hero missing');
  assert.ok(await page.locator('[data-rb-river-gallery]').count(), 'CMS homepage gallery missing');
  assert.ok(await page.locator('#rb-home-about').count(), 'About section missing');
  assert.ok(await page.locator('#rb-home-tours').count(), 'Signature Experiences section missing');
  assert.ok(await page.locator('#rb-home-why').count(), 'Why RI BUROM section missing');

  await page.locator('#mobile-menu-button').click();
  assert.equal(await page.locator('#mobile-menu-button').getAttribute('aria-expanded'), 'true');
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#mobile-menu-button').getAttribute('aria-expanded'), 'false');
  assert.ok(await page.locator('input[name="csrf_token"]').count());

  await page.goto('http://127.0.0.1:5055/marketplace/providers/visual-provider');
  await page.locator('#openProviderInquiry').click();
  await page.locator('#providerInquiryOverlay.is-open').waitFor();
  assert.ok(await page.locator('#providerInquiryForm input[name="csrf_token"]').count());
  await page.locator('#serviceMultiSelectToggle').click();
  await page.locator('input[name="service_ids"]').first().check();
  assert.equal(await page.locator('input[name="service_ids"]:checked').count(), 1);
  await page.keyboard.press('Escape');
  await page.locator('#providerInquiryOverlay').waitFor({state:'hidden'});

  assert.deepEqual(errors, []);
  fs.writeFileSync(path.join(output,'results.json'), JSON.stringify(results,null,2));
  await browser.close();
  console.log(`${results.length} responsive page checks passed; river runtime/artwork absent; homepage and marketplace interactions passed. Screenshots: ${output}`);
})().catch(error => { console.error(error); process.exit(1); });
