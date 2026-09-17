/* Diagnostic only: identify which water shields intersect the 390px route. */
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('http://127.0.0.1:5055/', { waitUntil: 'domcontentloaded' });
  await page.locator('#rb-page-loader').waitFor({ state: 'hidden' }).catch(() => {});
  await page.waitForTimeout(400);
  const result = await page.evaluate(() => {
    const root = document.querySelector('[data-rb-waterfall]');
    const route = root?.querySelector('.rb-water-route');
    if (!route) return { error: 'route missing' };
    const matrix = route.getScreenCTM();
    const length = route.getTotalLength();
    const shields = [...root.querySelectorAll('[data-rb-water-shield]')].map((el, index) => {
      const r = el.getBoundingClientRect();
      return { index, el, rect: {left:r.left - 16, right:r.right + 16, top:r.top - 16, bottom:r.bottom + 16},
        label: `${el.tagName.toLowerCase()}#${el.id || ''}.${String(el.className || '').replace(/\s+/g,'.')}` };
    });
    const counts = new Map(shields.map(s => [s.index, 0]));
    const samples = [];
    for (let i = 0; i < 600; i++) {
      const p = route.getPointAtLength(length * i / 600);
      const x = matrix.a * p.x + matrix.c * p.y + matrix.e;
      const y = matrix.b * p.x + matrix.d * p.y + matrix.f;
      const hits = shields.filter(s => x > s.rect.left && x < s.rect.right && y > s.rect.top && y < s.rect.bottom);
      if (hits.length) {
        hits.forEach(s => counts.set(s.index, counts.get(s.index) + 1));
        if (samples.length < 30) samples.push({i,x:Math.round(x),y:Math.round(y),hits:hits.map(h=>h.label)});
      }
    }
    return {
      root: { width: root.clientWidth, height: root.offsetHeight, gutter: getComputedStyle(root).getPropertyValue('--rb-river-gutter') },
      routeD: route.getAttribute('d'),
      blockers: shields.map(s => ({label:s.label,count:counts.get(s.index),rect:s.rect})).filter(s=>s.count).sort((a,b)=>b.count-a.count),
      samples,
    };
  });
  console.log('MOBILE_WATER_DIAGNOSTIC ' + JSON.stringify(result, null, 2));
  await page.screenshot({ path: '/tmp/riburom-paper-qa/390-water-diagnostic.png', fullPage: true });
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
