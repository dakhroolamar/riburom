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
        const stream = document.querySelector('.rb-waterfall')?.getBoundingClientRect();
        return {title: heading.textContent.trim(), overflow: document.documentElement.scrollWidth > innerWidth,
          headingOverflow: heading.scrollWidth > heading.clientWidth + 1,
          safe: rect.left >= 0 && rect.right <= innerWidth && rect.top >= nav.getBoundingClientRect().bottom,
          visible: getComputedStyle(heading).visibility !== 'hidden' && getComputedStyle(heading).opacity !== '0',
          streamClear: !stream || [...document.querySelectorAll('h1,h2,p,form,button')].every(el => {
            const r = el.getBoundingClientRect(); return !r.width || !r.height || r.left >= stream.right || r.bottom < stream.top || r.top > stream.bottom;
          })};
      });
      assert.equal(metrics.overflow, false, `overflow ${route} ${width}`);
      assert.equal(metrics.headingOverflow, false, `title overflow ${route} ${width}`);
      assert.ok(metrics.safe && metrics.visible && metrics.streamClear, JSON.stringify({route,width,metrics}));
      results.push({route,width,height,...metrics});
      await page.screenshot({path: path.join(output, `${width}-${index}.png`), fullPage: true});
    }
  }
  await page.goto('http://127.0.0.1:5055/');
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
  await page.goto('http://127.0.0.1:5055/');
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.reload();
  await page.waitForTimeout(800);
  assert.equal(await page.evaluate(() => gsap.version), '3.12.5');
  assert.ok(await page.evaluate(() => ScrollTrigger.getAll().length > 0));
  const revealPath = page.locator('.rb-water-reveal');
  const before = await revealPath.evaluate(el => getComputedStyle(el).strokeDashoffset);
  await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
  await page.waitForTimeout(1400);
  const after = await revealPath.evaluate(el => getComputedStyle(el).strokeDashoffset);
  assert.notEqual(before, after);

  // The inner current must keep flowing independently of scroll progress.
  const currentPath = page.locator('.rb-water-current');
  const flowBefore = await currentPath.evaluate(el => getComputedStyle(el).strokeDashoffset);
  await page.waitForTimeout(450);
  const flowAfter = await currentPath.evaluate(el => getComputedStyle(el).strokeDashoffset);
  assert.notEqual(flowBefore, flowAfter);

  // Fine-pointer interaction should snap the ripple to a visible stream point.
  await page.evaluate(() => scrollTo(0, 0));
  await page.waitForTimeout(300);
  const interactionPoint = await page.evaluate(() => {
    const route = document.querySelector('.rb-water-base');
    const navBottom = document.querySelector('nav').getBoundingClientRect().bottom;
    const ctm = route.getScreenCTM();
    const length = route.getTotalLength();
    for (let i = 0; i <= 80; i += 1) {
      const point = route.getPointAtLength(length * i / 80);
      const screen = new DOMPoint(point.x, point.y).matrixTransform(ctm);
      if (screen.y > navBottom + 40 && screen.y < innerHeight - 40) return {x:screen.x,y:screen.y};
    }
    return null;
  });
  assert.ok(interactionPoint);
  await page.mouse.move(interactionPoint.x, interactionPoint.y);
  await page.waitForTimeout(180);
  assert.equal(await page.locator('[data-rb-water-cursor]').evaluate(el => el.classList.contains('is-active')), true);

  await page.emulateMedia({reducedMotion:'reduce'});
  await page.waitForFunction(() => {
    const path = document.querySelector('.rb-water-reveal');
    return path && getComputedStyle(path).strokeDashoffset === '0px';
  });
  assert.equal(await page.locator('.rb-water-reveal').evaluate(el => getComputedStyle(el).strokeDashoffset), '0px');
  assert.equal(await page.locator('[data-rb-water-cursor]').evaluate(el => getComputedStyle(el).display), 'none');
  assert.deepEqual(errors, []);
  fs.writeFileSync(path.join(output,'results.json'), JSON.stringify(results,null,2));
  await browser.close();
  console.log(`${results.length} responsive page checks passed; mobile menu, CSRF, scroll drawing and live reduced-motion switch passed. Screenshots: ${output}`);
})().catch(error => { console.error(error); process.exit(1); });
