const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({headless:true});
  const context = await browser.newContext({viewport:{width:1440,height:900}, reducedMotion:'reduce'});
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    return url.hostname === '127.0.0.1' || url.protocol === 'data:' ? route.continue() : route.abort();
  });
  const page = await context.newPage();
  const response = await page.goto('http://127.0.0.1:5055/');
  assert.equal(response.status(), 200);
  await page.locator('#rb-page-loader').waitFor({state:'hidden'});
  await page.waitForTimeout(600);
  const diagnostic = await page.evaluate(() => {
    const root = document.querySelector('[data-rb-waterfall]');
    const canvas = root?.querySelector('[data-rb-water-canvas]');
    const protectedContent = root ? [...root.querySelectorAll('h1,h2,h3,p,form,button')].filter(el => {
      const r = el.getBoundingClientRect();
      return r.width && r.height;
    }) : [];
    return {
      canvasPointerEvents: canvas ? getComputedStyle(canvas).pointerEvents : null,
      totalProtected: protectedContent.length,
      unshielded: protectedContent.filter(el => !el.closest('[data-rb-water-shield]')).map(el => ({
        tag: el.tagName,
        id: el.id,
        cls: el.className,
        text: (el.textContent || '').trim().replace(/\s+/g,' ').slice(0,120),
        parent: el.parentElement?.className || '',
        ancestor: el.parentElement?.parentElement?.className || ''
      }))
    };
  });
  console.log('WATER-SHIELD-DIAGNOSTIC ' + JSON.stringify(diagnostic, null, 2));
  assert.equal(diagnostic.canvasPointerEvents, 'none');
  assert.deepEqual(diagnostic.unshielded, []);
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
