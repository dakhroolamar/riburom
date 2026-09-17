const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({headless:true});
  const context = await browser.newContext({viewport:{width:1440,height:900}, reducedMotion:'no-preference'});
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    return url.hostname === '127.0.0.1' || url.protocol === 'data:' ? route.continue() : route.abort();
  });
  const page = await context.newPage();
  const response = await page.goto('http://127.0.0.1:5055/');
  assert.equal(response.status(), 200);
  await page.locator('#rb-page-loader').waitFor({state:'hidden'});
  await page.waitForTimeout(900);
  await page.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; });

  const before = await page.evaluate(() => {
    const root = document.querySelector('[data-rb-waterfall]');
    return {
      hoverHover: matchMedia('(hover: hover)').matches,
      pointerFine: matchMedia('(pointer: fine)').matches,
      combined: matchMedia('(hover: hover) and (pointer: fine)').matches,
      anyHover: matchMedia('(any-hover: hover)').matches,
      anyFine: matchMedia('(any-pointer: fine)').matches,
      dataset: {...root.dataset}
    };
  });
  console.log('POINTER-CAPABILITY-BEFORE ' + JSON.stringify(before, null, 2));

  let point = null;
  for (const fraction of [.16,.30,.44,.58,.72,.84]) {
    await page.evaluate(f => scrollTo(0, Math.round(document.documentElement.scrollHeight * f)), fraction);
    await page.waitForTimeout(350);
    point = await page.evaluate(() => {
      const root = document.querySelector('[data-rb-waterfall]');
      const route = root.querySelector('.rb-water-route');
      const ctm = route.getScreenCTM();
      const length = route.getTotalLength();
      const maxT = Number(root.dataset.waterProgress || 0);
      const shields = [...document.querySelectorAll('[data-rb-water-shield]')].map(el => {
        const r = el.getBoundingClientRect();
        return {left:r.left-20,right:r.right+20,top:r.top-20,bottom:r.bottom+20};
      });
      for (let i=0;i<=180;i++) {
        const t=i/180;
        if (t>maxT+.01) break;
        const p=route.getPointAtLength(length*t);
        const x=ctm.a*p.x+ctm.c*p.y+ctm.e;
        const y=ctm.b*p.x+ctm.d*p.y+ctm.f;
        const shielded=shields.some(r=>x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom);
        if (y>120&&y<innerHeight-80&&!shielded) return {x,y,t,maxT,target:document.elementFromPoint(x,y)?.className||document.elementFromPoint(x,y)?.tagName};
      }
      return null;
    });
    if (point) break;
  }
  console.log('POINTER-POINT ' + JSON.stringify(point));
  assert.ok(point, 'no visible unshielded stream point');

  await page.evaluate(() => {
    window.__rbPointerMoves = 0;
    document.querySelector('[data-rb-waterfall]').addEventListener('pointermove', () => window.__rbPointerMoves++);
  });
  await page.mouse.move(point.x, point.y);
  await page.waitForTimeout(700);
  const after = await page.evaluate(() => {
    const root = document.querySelector('[data-rb-waterfall]');
    return {
      pointerMoves: window.__rbPointerMoves,
      interactive: root.dataset.waterInteractive || null,
      splashTotal: root.dataset.waterSplashTotal || null,
      splashVisible: root.dataset.waterSplashVisible || null,
      pointer: root.dataset.waterPointer || null,
      mode: root.dataset.waterMode || null
    };
  });
  console.log('POINTER-CAPABILITY-AFTER ' + JSON.stringify(after, null, 2));
  await browser.close();
})().catch(error => { console.error(error.stack || error); process.exit(1); });
