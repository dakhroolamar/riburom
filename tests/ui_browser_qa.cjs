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
        const waterRoot = document.querySelector('[data-rb-waterfall]');
        const canvas = waterRoot?.querySelector('[data-rb-water-canvas]');
        const protectedContent = waterRoot ? [...waterRoot.querySelectorAll('h1,h2,h3,p,form,button')].filter(el => {
          const r = el.getBoundingClientRect();
          return r.width && r.height;
        }) : [];
        let riverBlocked = 0;
        const route = waterRoot?.querySelector('.rb-water-route');
        if (route) {
          const matrix = route.getScreenCTM(), length = route.getTotalLength();
          const masks = [...waterRoot.querySelectorAll('[data-rb-water-shield]')].map(el => el.getBoundingClientRect());
          for (let i = 0; i < 600; i++) {
            const p = route.getPointAtLength(length * i / 600);
            const x = matrix.a * p.x + matrix.e, y = matrix.d * p.y + matrix.f;
            if (masks.some(r => x > r.left - 16 && x < r.right + 16 && y > r.top - 16 && y < r.bottom + 16)) riverBlocked++;
          }
        }
        return {riverBlocked, title: heading.textContent.trim(), overflow: document.documentElement.scrollWidth > innerWidth,
          headingOverflow: heading.scrollWidth > heading.clientWidth + 1,
          safe: rect.left >= 0 && rect.right <= innerWidth && rect.top >= nav.getBoundingClientRect().bottom,
          visible: getComputedStyle(heading).visibility !== 'hidden' && getComputedStyle(heading).opacity !== '0',
          streamClear: !waterRoot || (
            canvas && getComputedStyle(canvas).pointerEvents === 'none' &&
            protectedContent.every(el => !!el.closest('[data-rb-water-shield]'))
          )};
      });
      assert.ok(metrics.riverBlocked < 6, `disconnected river at ${width}px: ${metrics.riverBlocked} masked samples`);
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
  // Pointer interaction is a desktop/fine-pointer feature; run live-water QA
  // at the representative desktop viewport rather than the last mobile size.
  await page.setViewportSize({width:1440,height:900});
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.reload();
  await page.waitForTimeout(800);
  // The public UI intentionally uses smooth scrolling. Disable it only inside
  // browser QA so pointer assertions run after each programmatic scroll has
  // settled instead of racing the waterfall's scroll-reset interaction logic.
  await page.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; });
  assert.equal(await page.evaluate(() => gsap.version), '3.12.5');
  assert.ok(await page.evaluate(() => ScrollTrigger.getAll().length > 0));
  const waterLayers = await page.evaluate(() => {
    const section = document.querySelector('#rbHomeSections > header, #rbHomeSections > section');
    const canvas = document.querySelector('[data-rb-water-canvas]');
    const shield = document.querySelector('[data-rb-water-shield]');
    return {
      section: getComputedStyle(section).zIndex,
      canvas: Number(getComputedStyle(canvas).zIndex),
      shield: Number(getComputedStyle(shield).zIndex)
    };
  });
  assert.equal(waterLayers.section, 'auto', 'homepage section must not hide the water layer');
  assert.ok(waterLayers.canvas > 0 && waterLayers.shield > waterLayers.canvas,
    `invalid water stacking order: ${JSON.stringify(waterLayers)}`);
  const journey = page.locator('[data-rb-waterfall]');
  const source = await page.evaluate(() => {
    const river = document.querySelector('.rb-water-route');
    const matrix = river.getScreenCTM();
    const start = river.getPointAtLength(0);
    const hero = document.querySelector('[data-rb-water-source]').getBoundingClientRect();
    return {x:matrix.a * start.x + matrix.e, y:matrix.d * start.y + matrix.f,
      center:(hero.left + hero.right) / 2, top:hero.top, bottom:hero.bottom};
  });
  assert.ok(Math.abs(source.x - source.center) < 2 && source.y > source.top && source.y < source.bottom,
    'river source must be centred behind the hero artwork');

  // The route must fit the content, not rely on masks cutting it into fragments.
  const continuity = await page.evaluate(() => {
    const route = document.querySelector('.rb-water-route');
    const matrix = route.getScreenCTM(), length = route.getTotalLength();
    const shields = [...document.querySelectorAll('[data-rb-water-shield]')].map(el => el.getBoundingClientRect());
    let blocked = 0;
    for (let i = 0; i < 1000; i++) {
      const p = route.getPointAtLength(length * i / 1000);
      const x = matrix.a * p.x + matrix.e, y = matrix.d * p.y + matrix.f;
      if (shields.some(r => x > r.left - 16 && x < r.right + 16 && y > r.top - 16 && y < r.bottom + 16)) blocked++;
    }
    return blocked / 1000;
  });
  assert.ok(continuity < .01, `river is cut by content masks along ${continuity * 100}% of its route`);

  assert.ok(Number(await journey.getAttribute('data-water-width')) >= 100, 'desktop water must have substantial width');
  assert.ok(Number(await journey.getAttribute('data-water-band-count')) >= 6, 'water needs layered currents');
  const before = Number(await journey.getAttribute('data-water-progress') || 0);
  await page.evaluate(() => window.scrollTo({top:document.documentElement.scrollHeight, left:0, behavior:'instant'}));
  await page.waitForTimeout(1400);
  const after = Number(await journey.getAttribute('data-water-progress') || 0);
  assert.ok(after > before, `water progress did not advance: ${before} -> ${after}`);

  // The viewport canvas must continue rendering independently of scroll progress.
  const frameBefore = Number(await journey.getAttribute('data-water-frame') || 0);
  await page.waitForTimeout(450);
  const frameAfter = Number(await journey.getAttribute('data-water-frame') || 0);
  assert.ok(frameAfter > frameBefore, `water canvas stopped: ${frameBefore} -> ${frameAfter}`);

  // The route genuinely crosses the page rather than living in one side gutter.
  const routeSpread = await page.evaluate(() => {
    const route = document.querySelector('.rb-water-route');
    const ctm = route.getScreenCTM();
    const length = route.getTotalLength();
    const xs = [];
    for (let i = 0; i <= 40; i += 1) {
      const p = route.getPointAtLength(length * i / 40);
      xs.push(ctm.a * p.x + ctm.c * p.y + ctm.e);
    }
    return Math.max(...xs) - Math.min(...xs);
  });
  const viewportWidth = await page.evaluate(() => innerWidth);
  assert.ok(routeSpread > viewportWidth * .6, `water route spread too narrow: ${routeSpread}`);

  // Fine-pointer interaction adds a local ripple near a visible, already
  // revealed section of the stream. Search a few journey positions because
  // some crossings are intentionally hidden behind content shields.
  let interactionPoint = null;
  for (const fraction of [.16,.30,.44,.58,.72,.84]) {
    await page.evaluate(f => window.scrollTo({top:Math.round(document.documentElement.scrollHeight * f), left:0, behavior:'instant'}), fraction);
    await page.waitForTimeout(260);
    const revealed = Number(await journey.getAttribute('data-water-progress') || 0);
    interactionPoint = await page.evaluate(maxT => {
      const route = document.querySelector('.rb-water-route');
      const ctm = route.getScreenCTM();
      const length = route.getTotalLength();
      const shields = [...document.querySelectorAll('[data-rb-water-shield]')].map(el => {
        const r = el.getBoundingClientRect();
        return {left:r.left - 20,right:r.right + 20,top:r.top - 20,bottom:r.bottom + 20};
      });
      for (let i = 0; i <= 180; i += 1) {
        const t = i / 180;
        if (t > maxT + .01) break;
        const p = route.getPointAtLength(length * t);
        const x = ctm.a * p.x + ctm.c * p.y + ctm.e;
        const y = ctm.b * p.x + ctm.d * p.y + ctm.f;
        const shielded = shields.some(r => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom);
        if (y > 120 && y < innerHeight - 80 && !shielded) return {x,y};
      }
      return null;
    }, revealed);
    if (interactionPoint) break;
  }
  assert.ok(interactionPoint, 'no visible unshielded stream point found for pointer QA');
  await page.mouse.move(interactionPoint.x, interactionPoint.y);
  await page.waitForFunction(() =>
    document.querySelector('[data-rb-waterfall]')?.dataset.waterInteractive === 'true'
  );
  assert.equal(await journey.getAttribute('data-water-interactive'), 'true');
  const hoverSplashes = Number(await journey.getAttribute('data-water-splash-total'));
  assert.ok(hoverSplashes >= 2, 'pointer movement must emit a few gentle droplets');
  // At this settled scroll position the revealed front is visible within the viewport.
  await page.waitForTimeout(700);
  const front = await page.evaluate(() => {
    const root = document.querySelector('[data-rb-waterfall]');
    const route = root.querySelector('.rb-water-route'), matrix = route.getScreenCTM();
    const p = route.getPointAtLength(route.getTotalLength() * Number(root.dataset.waterProgress));
    return {y:matrix.d * p.y + matrix.f, height:innerHeight};
  });
  assert.ok(front.y > front.height * .65 && front.y < front.height * .92, 'scroll reveal should visibly advance within the viewport');

  const pixelsBefore = await page.locator('[data-rb-water-canvas]').evaluate(el => el.toDataURL());
  await page.waitForTimeout(350);
  const pixelsAfter = await page.locator('[data-rb-water-canvas]').evaluate(el => el.toDataURL());
  assert.notEqual(pixelsAfter, pixelsBefore, 'visible water pixels must animate without scrolling');
  await page.mouse.click(interactionPoint.x, interactionPoint.y);
  assert.ok(Number(await journey.getAttribute('data-water-splash-total')) >= hoverSplashes + 4,
    'click must produce a small touch response');
  await page.screenshot({path: path.join(output, 'live-water.png')});
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.waitForFunction(() => {
    const root = document.querySelector('[data-rb-waterfall]');
    return root?.dataset.waterProgress === '1.000' && !root.classList.contains('rb-water-live');
  });
  assert.equal(await page.locator('[data-rb-water-canvas]').evaluate(el => getComputedStyle(el).display), 'none');
  assert.equal(await journey.getAttribute('data-water-splash-count'), '0');
  assert.deepEqual(errors, []);
  fs.writeFileSync(path.join(output,'results.json'), JSON.stringify(results,null,2));
  await browser.close();
  console.log(`${results.length} responsive page checks passed; mobile menu, CSRF, scroll drawing and live reduced-motion switch passed. Screenshots: ${output}`);
})().catch(error => { console.error(error); process.exit(1); });
